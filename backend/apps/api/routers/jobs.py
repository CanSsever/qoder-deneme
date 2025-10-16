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
    """Run a job with the configured provider (idempotent with credit protection)."""
    from apps.core.supa_request import user_client, service_client
    import jwt
    from apps.core.settings import settings
    
    # Get job with user authentication (RLS enforced)
    cli = user_client(token)
    job = cli.table("jobs").select("*").eq("id", job_id).single().execute().data
    if not job:
        raise HTTPException(404, "Job not found")
    
    # IDEMPOTENCY CHECK: If job already succeeded with output, return existing result
    if job.get("status") == "succeeded" and job.get("output_image_url"):
        logger.info(
            "Job already completed, returning cached result (idempotent)",
            job_id=job_id,
            status=job["status"]
        )
        return {"status": "succeeded", "job": job}
    
    # CREDIT PROTECTION: Only charge credits on first execution
    credits_charged = False
    service_cli = service_client()
    
    # Get credit cost for job type
    credit_costs = {
        "restore": 1,
        "upscale": 1,
        "face_swap": 2,
        "face_restoration": 1
    }
    credits_required = credit_costs.get(job["job_type"], 1)
    
    # Check if this is the first run (no previous credit transaction for this job)
    existing_transaction = service_cli.table("credit_transactions").select("id").eq("reference_id", job_id).limit(1).execute()
    
    if not existing_transaction.data:
        # First run - validate and debit credits
        uid = jwt.decode(token, settings.supabase_jwt_secret, algorithms=["HS256"])["sub"]
        
        logger.info(
            "First execution, validating and debiting credits",
            job_id=job_id,
            user_id=uid,
            credits_required=credits_required
        )
        
        # Atomic credit validation and debit
        has_sufficient_credits = service_cli.rpc("validate_and_debit_credits", {
            "target_user_id": uid,
            "credit_amount": credits_required,
            "job_ref_id": job_id
        }).execute()
        
        if not has_sufficient_credits.data:
            logger.warning(
                "Insufficient credits for job execution",
                job_id=job_id,
                user_id=uid,
                credits_required=credits_required
            )
            raise HTTPException(402, f"Insufficient credits. Required: {credits_required}")
        
        credits_charged = True
        logger.info(
            "Credits debited successfully",
            job_id=job_id,
            user_id=uid,
            credits_required=credits_required
        )
    else:
        logger.info(
            "Subsequent execution, credits already charged",
            job_id=job_id,
            existing_transaction_id=existing_transaction.data[0]["id"]
        )

    # Update job status to running
    cli.table("jobs").update({"status": "running"}).eq("id", job_id).execute()
    
    provider = get_provider()
    try:
        logger.info(
            "Starting job processing",
            job_id=job_id,
            job_type=job["job_type"],
            provider=provider.__class__.__name__
        )
        
        # Execute the job based on type
        if job["job_type"] == "restore":
            result = provider.restore(token=token, job=job)
        elif job["job_type"] == "upscale":
            result = provider.upscale(token=token, job=job)
        else:
            raise HTTPException(400, f"Unsupported job_type: {job['job_type']}")
        
        # Update job with success status and output
        upd = {
            "status": "succeeded", 
            "progress": 1.0, 
            "output_image_url": result["output_path"]
        }
        job2 = cli.table("jobs").update(upd).eq("id", job_id).execute().data[0]
        
        logger.info(
            "Job completed successfully",
            job_id=job_id,
            output_path=result["output_path"]
        )
        
        return {"status": "succeeded", "job": job2}
        
    except Exception as e:
        logger.error(
            "Job processing failed",
            job_id=job_id,
            error=str(e),
            credits_charged=credits_charged
        )
        
        # Update job with failure status
        job2 = cli.table("jobs").update({
            "status": "failed", 
            "error_message": str(e)
        }).eq("id", job_id).execute().data[0]
        
        # CREDIT REFUND: If credits were charged and job failed, refund them
        if credits_charged:
            uid = jwt.decode(token, settings.supabase_jwt_secret, algorithms=["HS256"])["sub"]
            logger.info(
                "Refunding credits due to job failure",
                job_id=job_id,
                user_id=uid,
                credits_refunded=credits_required
            )
            
            # Refund credits
            service_cli.rpc("increment_credits", {
                "target_user_id": uid,
                "credit_amount": credits_required
            }).execute()
            
            # Create refund transaction record
            service_cli.table("credit_transactions").insert({
                "user_id": uid,
                "amount": credits_required,
                "transaction_type": "refund",
                "reference_id": job_id,
                "metadata": {"reason": "job_failed", "error": str(e)}
            }).execute()
        
        raise HTTPException(500, f"Processing failed: {e}")
