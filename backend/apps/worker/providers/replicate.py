import os
import time
import mimetypes
import io
import requests
import random
from typing import Dict, Optional
from apps.core.supa_request import user_client, service_client
from apps.core.settings import settings
import structlog

logger = structlog.get_logger(__name__)

API = "https://api.replicate.com/v1/predictions"
TOK = os.getenv("REPLICATE_API_TOKEN")
M_RESTORE = os.getenv("REPLICATE_RESTORE_MODEL", "tencentarc/gfpgan")
M_UPSCALE = os.getenv("REPLICATE_UPSCALE_MODEL", "nightmareai/real-esrgan")
POLL = float(os.getenv("REPLICATE_POLL_INTERVAL_SEC", "1.5"))
TIMEOUT = float(os.getenv("REPLICATE_TIMEOUT_SEC", "120"))

# Retry configuration
MAX_RETRIES = 5
BASE_DELAY = 1.0  # Base delay in seconds
MAX_JITTER = 0.2  # ±20% jitter
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}  # HTTP codes that trigger retry


def _headers():
    return {"Authorization": f"Token {TOK}", "Content-Type": "application/json"}


def _calculate_delay(attempt: int, base_delay: float = BASE_DELAY, max_jitter: float = MAX_JITTER) -> float:
    """Calculate exponential backoff delay with jitter."""
    exponential_delay = base_delay * (2 ** attempt)
    jitter = random.uniform(-max_jitter, max_jitter) * exponential_delay
    return max(0, exponential_delay + jitter)


def _http_with_retry(method: str, url: str, **kwargs) -> requests.Response:
    """HTTP request with exponential backoff retry logic."""
    last_exception = None
    
    for attempt in range(MAX_RETRIES):
        try:
            logger.debug(
                "Making HTTP request",
                method=method,
                url=url,
                attempt=attempt + 1,
                max_retries=MAX_RETRIES
            )
            
            response = requests.request(method, url, **kwargs)
            
            # Success (2xx status codes)
            if 200 <= response.status_code < 300:
                return response
            
            # Check if we should retry this status code
            if response.status_code in RETRY_STATUS_CODES:
                logger.warning(
                    "HTTP request failed, will retry",
                    method=method,
                    url=url,
                    status_code=response.status_code,
                    attempt=attempt + 1,
                    max_retries=MAX_RETRIES
                )
                
                # Don't sleep on the last attempt
                if attempt < MAX_RETRIES - 1:
                    delay = _calculate_delay(attempt)
                    logger.debug("Sleeping before retry", delay=delay)
                    time.sleep(delay)
                continue
            else:
                # Non-retryable status code, raise immediately
                response.raise_for_status()
                return response
        
        except requests.exceptions.RequestException as e:
            last_exception = e
            logger.warning(
                "HTTP request exception, will retry",
                method=method,
                url=url,
                error=str(e),
                attempt=attempt + 1,
                max_retries=MAX_RETRIES
            )
            
            # Don't sleep on the last attempt
            if attempt < MAX_RETRIES - 1:
                delay = _calculate_delay(attempt)
                logger.debug("Sleeping before retry", delay=delay)
                time.sleep(delay)
    
    # All retries exhausted
    logger.error(
        "HTTP request failed after all retries",
        method=method,
        url=url,
        max_retries=MAX_RETRIES
    )
    
    if last_exception:
        raise last_exception
    else:
        # This shouldn't happen, but just in case
        raise RuntimeError(f"HTTP {method} {url} failed after {MAX_RETRIES} attempts")


def _start(model: str, inputs: Dict) -> str:
    """Start a Replicate prediction with retry logic."""
    logger.info("Starting Replicate prediction", model=model, inputs=list(inputs.keys()))
    
    response = _http_with_retry(
        "POST",
        API,
        headers=_headers(),
        json={"version": None, "model": model, "input": inputs}
    )
    
    prediction_id = response.json()["id"]
    logger.info("Replicate prediction started", prediction_id=prediction_id)
    return prediction_id


def _poll(pred_id: str) -> Dict:
    """Poll a Replicate prediction with retry logic."""
    logger.info("Starting to poll Replicate prediction", prediction_id=pred_id)
    
    url = f"{API}/{pred_id}"
    t0 = time.time()
    
    while True:
        response = _http_with_retry("GET", url, headers=_headers())
        result = response.json()
        status = result["status"]
        
        logger.debug(
            "Polling Replicate prediction",
            prediction_id=pred_id,
            status=status,
            elapsed=time.time() - t0
        )
        
        if status in ("succeeded", "failed", "canceled"):
            logger.info(
                "Replicate prediction completed",
                prediction_id=pred_id,
                status=status,
                elapsed=time.time() - t0
            )
            return result
        
        if time.time() - t0 > TIMEOUT:
            logger.error(
                "Replicate prediction timeout",
                prediction_id=pred_id,
                timeout=TIMEOUT,
                elapsed=time.time() - t0
            )
            raise TimeoutError(f"Replicate prediction {pred_id} timed out after {TIMEOUT}s")
        
        time.sleep(POLL)


def _signed_input(path: str) -> str:
    # service role to make signed URL for Replicate to fetch
    sv = service_client()
    # assume bucket based on path prefix
    bucket = "uploads" if path.startswith("uploads/") else "outputs"
    return sv.storage.from_(bucket).create_signed_url(path, 3600)["signed_url"]


def _download(url: str) -> bytes:
    """Download content from URL with retry logic."""
    logger.info("Downloading content", url=url)
    
    response = _http_with_retry("GET", url, stream=True, timeout=60)
    content = response.content
    
    logger.info("Download completed", url=url, size=len(content))
    return content


def _upload_output(uid: str, src_url: str, filename_hint: str = "result.png") -> str:
    from uuid import uuid4
    sv = service_client()
    # Generate output path: outputs/{user_id}/{unique_filename}
    file_extension = filename_hint.split('.')[-1] if '.' in filename_hint else 'png'
    unique_filename = f"{uuid4()}.{file_extension}"
    object_path = f"{uid}/{unique_filename}"
    
    data = _download(src_url)
    ctype = mimetypes.guess_type(filename_hint)[0] or "image/png"
    sv.storage.from_("outputs").upload(object_path, data, {'content-type': ctype})
    return f"outputs/{object_path}"


class ReplicateProvider:
    def restore(self, *, token: str, job: Dict) -> Dict:
        # token -> user client for job updates; service client for storage ops
        import jwt
        uid = jwt.decode(token, settings.supabase_jwt_secret, algorithms=["HS256"])["sub"]
        in_path = job["input_image_url"]  # e.g., uploads/<uid>/...
        signed = _signed_input(in_path)
        # GFPGAN common inputs: {"img": url, "version": "1.4" ... } — keep minimal
        pred = _start(M_RESTORE, {"img": signed})
        res = _poll(pred)
        if res["status"] != "succeeded":
            raise RuntimeError(f"replicate failed: {res.get('error')}")
        out = res["output"]
        out_url = out[0] if isinstance(out, list) else out
        stored = _upload_output(uid, out_url, "restore.png")
        return {"output_path": stored}

    def upscale(self, *, token: str, job: Dict) -> Dict:
        import jwt
        uid = jwt.decode(token, settings.supabase_jwt_secret, algorithms=["HS256"])["sub"]
        in_path = job["input_image_url"]
        signed = _signed_input(in_path)
        # Real-ESRGAN typical inputs: {"image": url, "scale": 4}
        scale = int((job.get("parameters") or {}).get("scale", 4))
        pred = _start(M_UPSCALE, {"image": signed, "scale": scale})
        res = _poll(pred)
        if res["status"] != "succeeded":
            raise RuntimeError(f"replicate failed: {res.get('error')}")
        out = res["output"]
        out_url = out[0] if isinstance(out, list) else out
        stored = _upload_output(uid, out_url, f"upscale_x{scale}.png")
        return {"output_path": stored}