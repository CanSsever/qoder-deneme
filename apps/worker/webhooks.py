"""
Webhook system with HMAC signatures for job status notifications.
"""
import hmac
import hashlib
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
import aiohttp
import structlog

from apps.core.settings import settings
from apps.db.models.job import Job

logger = structlog.get_logger(__name__)


class WebhookEvent(str, Enum):
    """Webhook event types."""
    JOB_STARTED = "job.started"
    JOB_SUCCEEDED = "job.succeeded"
    JOB_FAILED = "job.failed"
    JOB_CANCELLED = "job.cancelled"


@dataclass
class WebhookRetryConfig:
    """Webhook retry configuration."""
    max_retries: int = 4
    retry_delays: List[int] = None  # [1m, 5m, 30m, 2h] in seconds
    
    def __post_init__(self):
        if self.retry_delays is None:
            self.retry_delays = [60, 300, 1800, 7200]  # 1m, 5m, 30m, 2h


@dataclass
class WebhookPayload:
    """Webhook payload structure."""
    event: WebhookEvent
    job_id: str
    user_id: str
    timestamp: str
    data: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        \"\"\"Convert to dictionary for JSON serialization.\"\"\"
        return {
            \"event\": self.event.value,
            \"job_id\": self.job_id,
            \"user_id\": self.user_id,
            \"timestamp\": self.timestamp,
            \"data\": self.data
        }


class HMACSignatureGenerator:
    \"\"\"HMAC signature generator for webhooks.\"\"\"
    
    @staticmethod
    def generate_signature(payload: str, secret: str) -> str:
        \"\"\"Generate HMAC-SHA256 signature for payload.\"\"\"
        if not secret:
            raise ValueError(\"HMAC secret is required\")
        
        signature = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return f\"sha256={signature}\"
    
    @staticmethod
    def verify_signature(payload: str, signature: str, secret: str) -> bool:
        \"\"\"Verify HMAC signature.\"\"\"
        try:
            expected_signature = HMACSignatureGenerator.generate_signature(payload, secret)
            return hmac.compare_digest(signature, expected_signature)
        except Exception:
            return False


class WebhookDelivery:
    \"\"\"Handles webhook delivery with retries.\"\"\"
    
    def __init__(self, retry_config: WebhookRetryConfig = None):
        self.retry_config = retry_config or WebhookRetryConfig()
    
    async def deliver_webhook(
        self, 
        url: str, 
        payload: WebhookPayload, 
        secret: str = None
    ) -> Dict[str, Any]:
        \"\"\"Deliver webhook with retry logic.\"\"\"
        
        if not url:
            logger.warning(\"No webhook URL provided, skipping delivery\")
            return {\"status\": \"skipped\", \"reason\": \"no_url\"}
        
        payload_json = json.dumps(payload.to_dict())
        headers = {
            \"Content-Type\": \"application/json\",
            \"User-Agent\": \"OneShot-Webhook/1.0\"
        }
        
        # Add HMAC signature if secret provided
        if secret:
            signature = HMACSignatureGenerator.generate_signature(payload_json, secret)
            headers[\"X-Signature\"] = signature
        
        delivery_result = {
            \"url\": url,
            \"event\": payload.event.value,
            \"job_id\": payload.job_id,
            \"attempts\": [],
            \"final_status\": \"pending\"
        }
        
        # Attempt delivery with retries
        for attempt in range(self.retry_config.max_retries + 1):
            try:
                result = await self._attempt_delivery(
                    url, payload_json, headers, attempt
                )
                
                delivery_result[\"attempts\"].append(result)
                
                if result[\"success\"]:
                    delivery_result[\"final_status\"] = \"delivered\"
                    logger.info(
                        \"Webhook delivered successfully\",
                        url=url,
                        job_id=payload.job_id,
                        event=payload.event.value,
                        attempt=attempt + 1
                    )
                    break
                
                # Check if we should retry
                if attempt < self.retry_config.max_retries:
                    retry_delay = self.retry_config.retry_delays[min(attempt, len(self.retry_config.retry_delays) - 1)]
                    
                    logger.warning(
                        \"Webhook delivery failed, will retry\",
                        url=url,
                        job_id=payload.job_id,
                        attempt=attempt + 1,
                        retry_delay_seconds=retry_delay,
                        error=result.get(\"error\")
                    )
                    
                    await asyncio.sleep(retry_delay)
                else:
                    delivery_result[\"final_status\"] = \"failed\"
                    logger.error(
                        \"Webhook delivery failed permanently\",
                        url=url,
                        job_id=payload.job_id,
                        total_attempts=attempt + 1
                    )
                    
            except Exception as e:
                error_result = {
                    \"attempt\": attempt + 1,
                    \"success\": False,
                    \"error\": str(e),
                    \"timestamp\": datetime.utcnow().isoformat()
                }
                
                delivery_result[\"attempts\"].append(error_result)
                
                if attempt >= self.retry_config.max_retries:
                    delivery_result[\"final_status\"] = \"failed\"
                    logger.error(
                        \"Webhook delivery exception\",
                        url=url,
                        job_id=payload.job_id,
                        error=str(e)
                    )
                    break
        
        return delivery_result
    
    async def _attempt_delivery(
        self, 
        url: str, 
        payload: str, 
        headers: Dict[str, str], 
        attempt: int
    ) -> Dict[str, Any]:
        \"\"\"Attempt single webhook delivery.\"\"\"
        
        start_time = datetime.utcnow()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    data=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    
                    response_text = await response.text()
                    end_time = datetime.utcnow()
                    
                    result = {
                        \"attempt\": attempt + 1,
                        \"success\": 200 <= response.status < 300,
                        \"status_code\": response.status,
                        \"response_body\": response_text[:500],  # Limit response size
                        \"duration_ms\": int((end_time - start_time).total_seconds() * 1000),
                        \"timestamp\": start_time.isoformat()
                    }
                    
                    if not result[\"success\"]:
                        result[\"error\"] = f\"HTTP {response.status}: {response_text[:200]}\"
                    
                    return result
                    
        except asyncio.TimeoutError:
            return {
                \"attempt\": attempt + 1,
                \"success\": False,
                \"error\": \"Request timeout\",
                \"timestamp\": start_time.isoformat()
            }
        except Exception as e:
            return {
                \"attempt\": attempt + 1,
                \"success\": False,
                \"error\": str(e),
                \"timestamp\": start_time.isoformat()
            }


class WebhookManager:
    \"\"\"Main webhook management class.\"\"\"
    
    def __init__(self):
        self.delivery = WebhookDelivery()
        self.secret = settings.hmac_secret
    
    async def send_job_webhook(
        self, 
        job: Job, 
        event: WebhookEvent, 
        webhook_url: Optional[str] = None,
        additional_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        \"\"\"Send webhook for job event.\"\"\"
        
        # Use provided webhook URL or get from job/user settings
        url = webhook_url or getattr(job, 'webhook_url', None)
        
        if not url:
            logger.debug(
                \"No webhook URL configured for job\",
                job_id=str(job.id),
                event=event.value
            )
            return {\"status\": \"skipped\", \"reason\": \"no_webhook_url\"}
        
        # Prepare webhook payload
        payload_data = {
            \"job_type\": job.job_type,
            \"status\": job.status,
            \"progress\": job.progress,
            \"created_at\": job.created_at.isoformat() if job.created_at else None,
            \"started_at\": job.started_at.isoformat() if job.started_at else None,
            \"finished_at\": job.finished_at.isoformat() if job.finished_at else None
        }
        
        # Add additional data
        if additional_data:
            payload_data.update(additional_data)
        
        # Add event-specific data
        if event == WebhookEvent.JOB_SUCCEEDED and hasattr(job, 'artifacts'):
            # Add artifact URLs if available
            payload_data[\"artifacts\"] = [
                {
                    \"id\": str(artifact.id),
                    \"type\": artifact.artifact_type,
                    \"url\": artifact.output_url,
                    \"size\": artifact.file_size
                }
                for artifact in job.artifacts
            ]
        
        payload = WebhookPayload(
            event=event,
            job_id=str(job.id),
            user_id=str(job.user_id),
            timestamp=datetime.utcnow().isoformat(),
            data=payload_data
        )
        
        logger.info(
            \"Sending webhook\",
            job_id=str(job.id),
            event=event.value,
            url=url,
            has_signature=bool(self.secret)
        )
        
        # Deliver webhook
        result = await self.delivery.deliver_webhook(url, payload, self.secret)
        
        logger.info(
            \"Webhook delivery completed\",
            job_id=str(job.id),
            event=event.value,
            final_status=result.get(\"final_status\"),
            total_attempts=len(result.get(\"attempts\", []))
        )
        
        return result
    
    async def send_job_started_webhook(self, job: Job, webhook_url: str = None) -> Dict[str, Any]:
        \"\"\"Send job started webhook.\"\"\"
        return await self.send_job_webhook(job, WebhookEvent.JOB_STARTED, webhook_url)
    
    async def send_job_succeeded_webhook(self, job: Job, webhook_url: str = None) -> Dict[str, Any]:
        \"\"\"Send job succeeded webhook.\"\"\"
        return await self.send_job_webhook(job, WebhookEvent.JOB_SUCCEEDED, webhook_url)
    
    async def send_job_failed_webhook(
        self, 
        job: Job, 
        error_message: str = None, 
        webhook_url: str = None
    ) -> Dict[str, Any]:
        \"\"\"Send job failed webhook.\"\"\"
        additional_data = {}
        if error_message:
            additional_data[\"error_message\"] = error_message
        
        return await self.send_job_webhook(
            job, 
            WebhookEvent.JOB_FAILED, 
            webhook_url, 
            additional_data
        )
    
    async def send_job_cancelled_webhook(self, job: Job, webhook_url: str = None) -> Dict[str, Any]:
        \"\"\"Send job cancelled webhook.\"\"\"
        return await self.send_job_webhook(job, WebhookEvent.JOB_CANCELLED, webhook_url)


# Global webhook manager instance
webhook_manager = WebhookManager()", "original_text": "test", "replace_all": true}]