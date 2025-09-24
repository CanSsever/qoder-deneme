"""
Enhanced Celery tasks with GPU provider integration, idempotency, retry logic, and caching.
"""
import asyncio
import hashlib
import json
import tempfile
import os
from datetime import datetime
from typing import Dict, Any, Optional, List
import aiohttp
from celery import Celery
from sqlmodel import Session, select
import structlog

from apps.core.settings import settings
from apps.db.session import engine
from apps.db.models.job import Job
from apps.db.models.artifact import Artifact
from apps.api.services.uploads import UploadService
from apps.worker.pipelines import pipeline_manager, PipelineType, OutputFormat
from apps.worker.providers.base import ProviderError, ProviderTimeoutError, ProviderStatus
from apps.worker.providers.comfy_local import ComfyUILocalProvider
from apps.worker.providers.runpod import RunPodProvider
from apps.worker.security import SecurityValidator, OutputSecurity, generate_secure_output_filename
from apps.worker.webhooks import WebhookManager

# Initialize Celery app
celery_app = Celery("oneshot_worker")
celery_app.conf.broker_url = settings.redis_url
celery_app.conf.result_backend = settings.redis_url
celery_app.conf.task_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.result_serializer = "json"
celery_app.conf.timezone = "UTC"
celery_app.conf.enable_utc = True

# Configure structured logging
logger = structlog.get_logger(__name__)

# Initialize providers
PROVIDERS = {
    "comfy_local": ComfyUILocalProvider(),
    "runpod": RunPodProvider()
}

# Initialize services
s3_service = UploadService()
security_validator = SecurityValidator(max_size_mb=settings.max_input_mb)
webhook_manager = WebhookManager()


class JobProcessingError(Exception):
    """Job processing error."""
    pass


class IdempotencyManager:
    """Manages idempotency for job processing."""
    
    @staticmethod
    def generate_cache_key(job: Job) -> str:
        """Generate cache key for idempotency checking."""
        content = {
            "job_type": job.job_type,
            "source_url": getattr(job, 'source_url', ''),
            "target_url": getattr(job, 'target_url', ''),
            "params": job.params or {}
        }
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()
    
    @staticmethod
    def check_cache_hit(session: Session, cache_key: str) -> Optional[Artifact]:
        """Check if we have a cached result for this job."""
        try:
            statement = select(Artifact).join(Job).where(
                Job.status == "succeeded",
                Artifact.extra_data.like(f'%"cache_key":"{cache_key}"%')
            )
            return session.exec(statement).first()
        except Exception:
            return None


class RetryManager:
    """Manages retry logic with exponential backoff."""
    
    MAX_RETRIES = 2
    RETRY_DELAYS = [15, 60]  # 15s, 60s
    
    @staticmethod
    def should_retry(attempt: int, error: Exception) -> bool:
        """Determine if we should retry."""
        if attempt >= RetryManager.MAX_RETRIES:
            return False
        
        retry_errors = (ProviderTimeoutError, ConnectionError, aiohttp.ClientError)
        return isinstance(error, retry_errors)
    
    @staticmethod
    def get_retry_delay(attempt: int) -> int:
        """Get retry delay for given attempt."""
        if attempt < len(RetryManager.RETRY_DELAYS):
            return RetryManager.RETRY_DELAYS[attempt]
        return RetryManager.RETRY_DELAYS[-1]


@celery_app.task(bind=True, max_retries=RetryManager.MAX_RETRIES)
def process_ai_job(self, job_id: str):
    """Enhanced job processing with providers, idempotency, and retry logic."""
    start_time = datetime.utcnow()
    
    try:
        result = asyncio.run(_process_ai_job_async(job_id, self.request.retries))
        
        processing_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        logger.info(
            "Job processing completed",
            job_id=job_id,
            result=result,
            processing_time_ms=processing_time,
            retries=self.request.retries
        )
        
        return result
        
    except Exception as e:
        if RetryManager.should_retry(self.request.retries, e):
            retry_delay = RetryManager.get_retry_delay(self.request.retries)
            
            logger.warning(
                "Job processing failed, retrying",
                job_id=job_id,
                error=str(e),
                retry_attempt=self.request.retries + 1,
                retry_delay_seconds=retry_delay
            )
            
            _update_job_status(job_id, "pending", f"Retrying: {str(e)}")
            raise self.retry(countdown=retry_delay, exc=e)
        
        logger.error(
            "Job processing failed permanently",
            job_id=job_id,
            error=str(e),
            retries=self.request.retries
        )
        
        _update_job_status(job_id, "failed", f"Processing failed: {str(e)}")
        return {"status": "failed", "error": str(e)}


async def _process_ai_job_async(job_id: str, retry_count: int = 0) -> Dict[str, Any]:
    """Async job processing implementation."""
    with Session(engine) as session:
        statement = select(Job).where(Job.id == job_id)
        job = session.exec(statement).first()
        
        if not job:
            raise JobProcessingError(f"Job not found: {job_id}")
        
        try:
            # Check for idempotency (cache hit)
            cache_key = IdempotencyManager.generate_cache_key(job)
            cached_artifact = IdempotencyManager.check_cache_hit(session, cache_key)
            
            if cached_artifact:
                logger.info(
                    "Cache hit - reusing existing result",
                    job_id=job_id,
                    cache_key=cache_key
                )
                
                # Create new artifact referencing cached result
                new_artifact = Artifact(
                    job_id=job.id,
                    artifact_type="image",
                    output_url=cached_artifact.output_url,
                    file_size=cached_artifact.file_size,
                    mime_type=cached_artifact.mime_type,
                    extra_data=json.dumps({
                        "cache_key": cache_key,
                        "cached_from": str(cached_artifact.id),
                        "processing_type": "cache_hit"
                    })
                )
                
                session.add(new_artifact)
                job.status = "succeeded"
                job.progress = 100
                job.finished_at = datetime.utcnow()
                session.commit()
                
                return {
                    "status": "succeeded",
                    "message": "Result retrieved from cache",
                    "output_url": cached_artifact.output_url,
                    "cache_hit": True
                }
            
            # No cache hit - process with provider
            result = await _process_job_with_provider(job, session, cache_key)
            return result
            
        except Exception as e:
            logger.error("Job processing error", job_id=job_id, error=str(e))
            raise


async def _process_job_with_provider(job: Job, session: Session, cache_key: str) -> Dict[str, Any]:
    """Process job using the configured GPU provider."""
    
    # Validate input images for security
    await _validate_job_inputs(job)
    
    # Get pipeline configuration
    try:
        pipeline_type = PipelineType(job.job_type)
        pipeline_config = pipeline_manager.get_pipeline_config(pipeline_type)
    except ValueError as e:
        raise JobProcessingError(f"Invalid pipeline type {job.job_type}: {e}")
    
    # Get provider
    provider = PROVIDERS.get(settings.gpu_provider)
    if not provider:
        raise JobProcessingError(f"Unknown provider: {settings.gpu_provider}")
    
    # Update job status
    job.status = "running"
    job.started_at = datetime.utcnow()
    job.progress = 10
    session.commit()
    
    # Send started webhook
    await _send_job_webhook(job, "started", {
        "provider": provider.name,
        "pipeline_type": job.job_type
    })
    
    try:
        # Submit to provider
        submit_response = await provider.submit(job, pipeline_config)
        
        job.remote_id = submit_response.remote_id
        job.progress = 20
        session.commit()
        
        # Poll for completion
        result = await _poll_job_completion(job, provider, session)
        
        if result.status == ProviderStatus.SUCCEEDED:
            # Process outputs
            artifacts = await _process_job_outputs(job, provider, result, session, cache_key)
            
            job.status = "succeeded"
            job.progress = 100
            job.finished_at = datetime.utcnow()
            session.commit()
            
            # Send success webhook
            await _send_job_webhook(job, "succeeded", {
                "artifacts": [str(a.id) for a in artifacts],
                "output_urls": [a.output_url for a in artifacts],
                "processing_time_ms": (datetime.utcnow() - job.started_at).total_seconds() * 1000
            })
            
            return {
                "status": "succeeded",
                "message": "Job completed successfully",
                "artifacts": [str(a.id) for a in artifacts],
                "output_urls": [a.output_url for a in artifacts]
            }
        
        else:
            job.status = "failed"
            job.finished_at = datetime.utcnow()
            session.commit()
            
            # Send failure webhook
            await _send_job_webhook(job, "failed", {
                "error_message": result.message,
                "provider": provider.name
            })
            
            raise JobProcessingError(f"Provider job failed: {result.message}")
            
    except ProviderError as e:
        raise JobProcessingError(f"Provider error: {e}")


async def _poll_job_completion(job: Job, provider, session: Session):
    """Poll provider until job completion."""
    max_polls = 300
    poll_count = 0
    
    while poll_count < max_polls:
        try:
            result = await provider.poll(job, job.remote_id)
            
            if result.progress != job.progress:
                job.progress = min(result.progress, 90)
                session.commit()
            
            if result.status in [ProviderStatus.SUCCEEDED, ProviderStatus.FAILED, ProviderStatus.CANCELLED]:
                return result
            
            await asyncio.sleep(1)
            poll_count += 1
            
        except Exception as e:
            if poll_count >= max_polls - 5:
                raise
            await asyncio.sleep(2)
            poll_count += 1
    
    raise ProviderTimeoutError(f"Job polling timeout", provider.name, job.remote_id)


async def _process_job_outputs(job: Job, provider, result, session: Session, cache_key: str) -> List[Artifact]:
    """Download outputs and upload to S3 with security processing."""
    if not result.output_urls:
        raise JobProcessingError("No output URLs provided")
    
    artifacts = []
    output_files = await provider.download_outputs(job.remote_id, result.output_urls)
    
    for output_name, file_content in output_files.items():
        # Validate output content security
        try:
            validation_result = await security_validator.validate_image_content(
                file_content, 
                f"provider_output_{job.id}_{output_name}"
            )
        except Exception as e:
            logger.error("Output validation failed", job_id=job.id, output_name=output_name, error=str(e))
            raise JobProcessingError(f"Output validation failed: {e}")
        
        # Generate secure filename
        file_ext = "png" if settings.output_format == "png" else "jpg"
        secure_filename = generate_secure_output_filename(
            f"{output_name}.{file_ext}", 
            str(job.id), 
            output_name
        )
        
        # Process and save output securely
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = os.path.join(temp_dir, secure_filename)
            
            # Save with security controls
            save_result = await OutputSecurity.save_output_securely(
                file_content,
                temp_path,
                format_type=settings.output_format.upper(),
                quality=settings.output_quality if hasattr(settings, 'output_quality') else 95
            )
            
            # Upload to S3
            s3_url = await _upload_to_s3(secure_filename, temp_path)
            
            artifact = Artifact(
                job_id=job.id,
                artifact_type="image",
                output_url=s3_url,
                file_size=save_result['size'],
                mime_type=f"image/{file_ext}",
                extra_data=json.dumps({
                    "cache_key": cache_key,
                    "provider": provider.name,
                    "remote_id": job.remote_id,
                    "output_name": output_name,
                    "validation_hash": validation_result['content_hash'],
                    "original_dimensions": validation_result['dimensions'],
                    "output_dimensions": save_result['dimensions'],
                    "security_validated": True
                })
            )
            
            session.add(artifact)
            artifacts.append(artifact)
    
    session.commit()
    return artifacts


async def _upload_to_s3(filename: str, file_path: str) -> str:
    """Upload file to S3 and return URL."""
    try:
        s3_key = f"outputs/{filename}"
        s3_url = await s3_service.upload_file_async(file_path, s3_key)
        return s3_url
    except Exception as e:
        logger.error("S3 upload failed", filename=filename, error=str(e))
        raise JobProcessingError(f"Upload failed: {e}")


def _update_job_status(job_id: str, status: str, message: str = None) -> None:
    """Update job status in database."""
    try:
        with Session(engine) as session:
            statement = select(Job).where(Job.id == job_id)
            job = session.exec(statement).first()
            
            if job:
                job.status = status
                if status == "failed":
                    job.finished_at = datetime.utcnow()
                session.commit()
                
    except Exception as e:
        logger.error("Failed to update job status", job_id=job_id, error=str(e))


async def _validate_job_inputs(job: Job) -> None:
    """Validate all input images for security."""
    urls_to_validate = []
    
    # Collect URLs based on job type
    if hasattr(job, 'source_url') and job.source_url:
        urls_to_validate.append(("source", job.source_url))
    
    if hasattr(job, 'target_url') and job.target_url:
        urls_to_validate.append(("target", job.target_url))
    
    # Check params for additional URLs
    if job.params:
        if 'input_url' in job.params:
            urls_to_validate.append(("input", job.params['input_url']))
        if 'src_face_url' in job.params:
            urls_to_validate.append(("src_face", job.params['src_face_url']))
        if 'target_url' in job.params:
            urls_to_validate.append(("target", job.params['target_url']))
    
    # Validate each URL
    for url_type, url in urls_to_validate:
        try:
            validation_result = await security_validator.validate_image_url(url)
            logger.info(
                "Input image validated",
                job_id=job.id,
                url_type=url_type,
                file_size=validation_result['file_size'],
                mime_type=validation_result['mime_type'],
                dimensions=validation_result['dimensions']
            )
        except Exception as e:
            logger.error(
                "Input validation failed",
                job_id=job.id,
                url_type=url_type,
                url=url,
                error=str(e)
            )
            raise JobProcessingError(f"Input validation failed for {url_type}: {e}")


async def _send_job_webhook(job: Job, status: str, extra_data: Dict[str, Any] = None) -> None:
    """Send webhook notification for job status change."""
    try:
        await webhook_manager.send_job_webhook(job, status, extra_data)
    except Exception as e:
        logger.warning("Webhook delivery failed", job_id=job.id, status=status, error=str(e))


@celery_app.task
def cancel_ai_job(job_id: str):
    """Cancel a running AI job."""
    try:
        with Session(engine) as session:
            statement = select(Job).where(Job.id == job_id)
            job = session.exec(statement).first()
            
            if not job:
                return {"status": "not_found"}
            
            if job.status in ["succeeded", "failed", "cancelled"]:
                return {"status": job.status}
            
            # Try to cancel with provider
            if job.remote_id and settings.gpu_provider in PROVIDERS:
                provider = PROVIDERS[settings.gpu_provider]
                try:
                    asyncio.run(provider.cancel(job, job.remote_id))
                except Exception as e:
                    logger.warning("Provider cancellation failed", error=str(e))
            
            job.status = "cancelled"
            job.finished_at = datetime.utcnow()
            session.commit()
            
            return {"status": "cancelled"}
            
    except Exception as e:
        logger.error("Job cancellation failed", job_id=job_id, error=str(e))
        return {"status": "error", "error": str(e)}