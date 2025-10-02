import os
import time
import mimetypes
import io
import requests
from typing import Dict
from apps.core.supa_request import user_client, service_client
from apps.core.settings import settings

API = "https://api.replicate.com/v1/predictions"
TOK = os.getenv("REPLICATE_API_TOKEN")
M_RESTORE = os.getenv("REPLICATE_RESTORE_MODEL", "tencentarc/gfpgan")
M_UPSCALE = os.getenv("REPLICATE_UPSCALE_MODEL", "nightmareai/real-esrgan")
POLL = float(os.getenv("REPLICATE_POLL_INTERVAL_SEC", "1.5"))
TIMEOUT = float(os.getenv("REPLICATE_TIMEOUT_SEC", "120"))


def _headers():
    return {"Authorization": f"Token {TOK}", "Content-Type": "application/json"}


def _start(model: str, inputs: Dict) -> str:
    import json
    import requests
    r = requests.post(API, headers=_headers(), json={"version": None, "model": model, "input": inputs})
    r.raise_for_status()
    return r.json()["id"]


def _poll(pred_id: str) -> Dict:
    import requests
    import time
    url = f"{API}/{pred_id}"
    t0 = time.time()
    while True:
        r = requests.get(url, headers=_headers())
        r.raise_for_status()
        j = r.json()
        s = j["status"]
        if s in ("succeeded", "failed", "canceled"):
            return j
        if time.time() - t0 > TIMEOUT:
            raise TimeoutError("replicate timeout")
        time.sleep(POLL)


def _signed_input(path: str) -> str:
    # service role to make signed URL for Replicate to fetch
    sv = service_client()
    # assume bucket based on path prefix
    bucket = "uploads" if path.startswith("uploads/") else "outputs"
    return sv.storage.from_(bucket).create_signed_url(path, 3600)["signed_url"]


def _download(url: str) -> bytes:
    r = requests.get(url, stream=True, timeout=60)
    r.raise_for_status()
    return r.content


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