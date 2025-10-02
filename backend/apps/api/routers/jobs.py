"""
Jobs router with Supabase authentication and enhanced validation.
"""
import structlog
from uuid import UUID
from typing import List, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from pydantic import BaseModel, validator
from apps.api.services import JobService
from apps.core.security import get_current_active_user, get_raw_token, SupabaseUser, require_token
from apps.core.exceptions import ValidationError, InsufficientCreditsError
from apps.worker.providers import get_provider

logger = structlog.get_logger()
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobCreateRequest(BaseModel):
    """Job creation request schema."""
    job_type: str
    input_image_url: str
    target_image_url: str = None
    parameters: Dict[str, Any] = {}
    
    @validator('job_type')
    def validate_job_type(cls, v):
        valid_types = ["face_restoration", "face_swap", "upscale", "restore"]
        if v not in valid_types:
            raise ValueError(f"Invalid job type. Must be one of: {valid_types}")
        return v
    
    @validator('input_image_url')
    def validate_input_url(cls, v):
        if not v or not v.startswith(('http://', 'https://')):
            raise ValueError("Invalid input image URL")
        return v
    
    @validator('target_image_url')
    def validate_target_url(cls, v, values):
        if values.get('job_type') == "face_swap" and not v:
            raise ValueError("Target image URL is required for face swap jobs")
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError("Invalid target image URL")
        return v


@router.post("")
@limiter.limit("30/minute")  # Rate limit: 30 jobs per minute
async def create_job(
    request: Request,
    job_data: JobCreateRequest,
    current_user: SupabaseUser = Depends(get_current_active_user),
    user_token: str = Depends(get_raw_token)
) -> Dict[str, Any]:
    """Create a new AI processing job with Supabase authentication."""
    
    logger.info("Job creation request", 
               user_id=current_user.id,
               job_type=job_data.job_type,
               parameters=job_data.parameters,
               remote_addr=get_remote_address(request))
    
    try:
        # Create job using Supabase service with user JWT
        job = JobService.create_job(current_user, job_data.dict(), user_token)
        
        if not job:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create job"
            )
        
        logger.info("Job created successfully", 
                   user_id=current_user.id,
                   job_id=job.get("id"),
                   job_type=job_data.job_type)
        
        # Here you would typically queue the job for processing
        # process_ai_job.delay(job["id"])
        
        return {
            "job": job,
            "message": "Job created successfully"
        }
        
    except InsufficientCreditsError as e:
        logger.warning("Insufficient credits", 
                      user_id=current_user.id,
                      error=str(e))
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "code": "INSUFFICIENT_CREDITS",
                "message": str(e)
            }
        )
        
    except ValidationError as e:
        logger.warning("Validation error", 
                      user_id=current_user.id,
                      error=str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
        
    except Exception as e:
        logger.error("Job creation failed", 
                    user_id=current_user.id,
                    error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create job"
        )


@router.get("/{job_id}")
async def get_job_status(
    request: Request,
    job_id: str,
    current_user: SupabaseUser = Depends(get_current_active_user),
    user_token: str = Depends(get_raw_token)
) -> Dict[str, Any]:
    """Get job status and progress with detailed information."""
    
    logger.info("Job status request", 
               job_id=job_id,
               user_id=current_user.id)
    
    job = JobService.get_job(job_id, user_token)
    if not job:
        logger.warning("Job not found", 
                      job_id=job_id,
                      user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "JOB_NOT_FOUND",
                "message": "Job not found"
            }
        )
    
    return {
        "job": job
    }


@router.get("")
async def list_jobs(
    request: Request,
    limit: int = 50,
    offset: int = 0,
    current_user: SupabaseUser = Depends(get_current_active_user),
    user_token: str = Depends(get_raw_token)
) -> Dict[str, Any]:
    """List user's jobs with pagination."""
    
    logger.info("Job list request", 
               user_id=current_user.id,
               limit=limit,
               offset=offset)
    
    jobs = JobService.get_user_jobs(user_token, limit, offset)
    
    return {
        "jobs": jobs,
        "pagination": {
            "limit": limit,
            "offset": offset,
            "count": len(jobs)
        }
    }


@router.post("/{job_id}/run")
def run_job(job_id: str, token: str = Depends(require_token)):
    """Run a job with the configured provider (idempotent)."""
    from apps.core.supa_request import user_client
    
    cli = user_client(token)
    job = cli.table("jobs").select("*").eq("id", job_id).single().execute().data
    if not job:
        raise HTTPException(404, "Job not found")
    if job.get("status") == "succeeded" and job.get("output_image_url"):
        return {"status": "succeeded", "job": job}  # idempotent

    cli.table("jobs").update({"status": "running"}).eq("id", job_id).execute()
    provider = get_provider()
    try:
        if job["job_type"] == "restore":
            result = provider.restore(token=token, job=job)
        elif job["job_type"] == "upscale":
            result = provider.upscale(token=token, job=job)
        else:
            raise HTTPException(400, "Unsupported job_type")
        upd = {"status": "succeeded", "progress": 1.0, "output_image_url": result["output_path"]}
        job2 = cli.table("jobs").update(upd).eq("id", job_id).execute().data[0]
        return {"status": "succeeded", "job": job2}
    except Exception as e:
        job2 = cli.table("jobs").update({"status": "failed", "error_message": str(e)}).eq("id", job_id).execute().data[0]
        raise HTTPException(500, f"Processing failed: {e}")
