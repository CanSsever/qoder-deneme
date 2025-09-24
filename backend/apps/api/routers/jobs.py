"""
Advanced job router with entitlements-based rate limiting, validation, and comprehensive monitoring.
"""
import structlog
from uuid import UUID
from typing import List, Dict, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlmodel import Session, select
from slowapi import Limiter
from slowapi.util import get_remote_address
from pydantic import BaseModel, validator
from apps.db.session import get_session
from apps.db.models.job import JobCreate, JobResponse, JobStatusResponse, JobRead, Job
from apps.db.models.user import User
from apps.db.models.credit import CreditTransaction
from apps.api.services import JobService
from apps.api.services.entitlements import EntitlementsService
from apps.core.security import get_current_active_user
from apps.core.exceptions import ValidationError, InsufficientCreditsError
from apps.core.config import JobType, CREDIT_COSTS
from apps.core.privacy import FaceConsentService
from apps.worker.tasks import process_ai_job

logger = structlog.get_logger()
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobCreateAdvanced(BaseModel):
    """Advanced job creation schema with validation."""
    job_type: str
    input_image_url: str
    target_image_url: str = None
    parameters: Dict[str, Any] = {}
    
    @validator('job_type')
    def validate_job_type(cls, v):
        valid_types = [JobType.FACE_RESTORATION, JobType.FACE_SWAP, JobType.UPSCALE]
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
        if values.get('job_type') == JobType.FACE_SWAP and not v:
            raise ValueError("Target image URL is required for face swap jobs")
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError("Invalid target image URL")
        return v
    
    @validator('parameters')
    def validate_parameters(cls, v, values):
        job_type = values.get('job_type')
        
        # Validate max_side parameter exists in params for all job types
        # This will be checked against user's plan limits later
        if 'max_side' not in v:
            v['max_side'] = 512  # Default value
        
        if job_type == JobType.FACE_RESTORATION:
            valid_models = ['gfpgan', 'codeformer']
            if 'model' in v and v['model'] not in valid_models:
                raise ValueError(f"Invalid model for face restoration. Must be one of: {valid_models}")
            if 'scale_factor' in v and not (1 <= v['scale_factor'] <= 4):
                raise ValueError("Scale factor must be between 1 and 4")
                
        elif job_type == JobType.UPSCALE:
            if 'scale_factor' in v and not (2 <= v['scale_factor'] <= 8):
                raise ValueError("Upscale factor must be between 2 and 8")
                
        elif job_type == JobType.FACE_SWAP:
            if 'blend_ratio' in v and not (0.0 <= v['blend_ratio'] <= 1.0):
                raise ValueError("Blend ratio must be between 0.0 and 1.0")
        
        return v


@router.post("", response_model=JobResponse)
@limiter.limit("30/minute")  # Rate limit: 30 jobs per minute
async def create_job(
    request: Request,
    job_data: JobCreateAdvanced,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    """Create a new AI processing job with entitlements-based validation and privacy/safety enforcement."""
    
    logger.info("Job creation request", 
               user_id=str(current_user.id),
               job_type=job_data.job_type,
               parameters=job_data.parameters,
               remote_addr=get_remote_address(request))
    
    try:
        # Use entitlements service to check limits
        with EntitlementsService(session) as entitlements:
            # Get user's plan for privacy/safety checks
            user_plan = entitlements.get_user_plan(str(current_user.id))
            
            # Privacy and Safety Enforcement
            consent_service = FaceConsentService()
            
            # Check face consent requirements for face swap jobs
            consent_validation = consent_service.validate_face_swap_consent(
                job_data.parameters, 
                user_plan, 
                job_data.job_type
            )
            
            # Enforce consent violations
            if not consent_validation["consent_valid"]:
                logger.warning("Consent validation failed", 
                              user_id=str(current_user.id),
                              violations=consent_validation["violations"])
                
                # Return structured error for consent violations
                violation_details = consent_validation["violations"][0] if consent_validation["violations"] else {}
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "nsfw_blocked" if "nsfw" in violation_details.get("type", "") else "consent_required",
                        "message": violation_details.get("message", "Consent validation failed"),
                        "required_consents": consent_validation["required_consents"],
                        "missing_consents": consent_validation["missing_consents"],
                        "violations": consent_validation["violations"]
                    }
                )
            
            # Log consent warnings (for non-blocking issues)
            if consent_validation["warnings"]:
                logger.info("Consent warnings detected", 
                           user_id=str(current_user.id),
                           warnings=consent_validation["warnings"])
            
            # Prepare job parameters for validation
            job_params = {
                "job_type": job_data.job_type,
                **job_data.parameters
            }
            
            # Check if user can create job based on entitlements
            can_create, error_message = entitlements.check_job_creation_limits(str(current_user.id), job_params)
            
            if not can_create:
                logger.warning("Job creation limit check failed", 
                              user_id=str(current_user.id),
                              error=error_message)
                
                # Determine appropriate HTTP status code
                if "daily job limit" in error_message.lower():
                    status_code = 429  # Too Many Requests
                elif "concurrent job limit" in error_message.lower():
                    status_code = 429  # Too Many Requests
                elif "exceeds limit" in error_message.lower() or "parameter" in error_message.lower():
                    status_code = 422  # Unprocessable Entity
                elif "not available" in error_message.lower():
                    status_code = 402  # Payment Required
                else:
                    status_code = 400  # Bad Request
                
                raise HTTPException(
                    status_code=status_code,
                    detail={
                        "code": "ENTITLEMENT_LIMIT_EXCEEDED",
                        "message": error_message,
                        "type": "daily_limit" if "daily" in error_message.lower() else 
                                "concurrent_limit" if "concurrent" in error_message.lower() else
                                "parameter_limit" if "parameter" in error_message.lower() else
                                "feature_unavailable" if "not available" in error_message.lower() else
                                "limit_exceeded"
                    }
                )
            
            # Check credit balance (keep existing credit system)
            credits_required = CREDIT_COSTS.get(job_data.job_type, 1)
            if current_user.credits < credits_required:
                logger.warning("Insufficient credits", 
                              user_id=str(current_user.id),
                              required=credits_required,
                              available=current_user.credits)
                raise HTTPException(
                    status_code=402,
                    detail={
                        "code": "INSUFFICIENT_CREDITS",
                        "message": f"Insufficient credits. Required: {credits_required}, Available: {current_user.credits}",
                        "required_credits": credits_required,
                        "available_credits": current_user.credits
                    }
                )
            
            # Create job
            job_create = JobCreate(
                job_type=job_data.job_type,
                input_image_url=job_data.input_image_url,
                target_image_url=job_data.target_image_url,
                parameters=job_data.parameters
            )
            
            job = JobService.create_job(session, current_user, job_create)
            
            # Increment usage counter
            entitlements.increment_job_usage(str(current_user.id), job_data.job_type)
            
            # Queue background processing
            task = process_ai_job.delay(str(job.id))
            
            logger.info("Job created successfully", 
                       job_id=str(job.id),
                       user_id=str(current_user.id),
                       task_id=task.id,
                       credits_cost=job.credits_cost)
            
            # Get estimated processing time
            from apps.core.config import JOB_TIMEOUTS
            estimated_time = JOB_TIMEOUTS.get(job_data.job_type, 300)
            
            return JobResponse(
                job_id=job.id,
                status=job.status,
                estimated_time=estimated_time,
                credits_cost=job.credits_cost
            )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Job creation failed", 
                    user_id=str(current_user.id),
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "code": "JOB_CREATION_FAILED",
                "message": "Failed to create job. Please try again."
            }
        )


@router.get("/{job_id}", response_model=JobStatusResponse)
@limiter.limit("100/minute")
async def get_job_status(
    request: Request,
    job_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    """Get job status and progress with detailed information."""
    
    logger.info("Job status request", 
               job_id=str(job_id),
               user_id=str(current_user.id))
    
    job = JobService.get_job(session, job_id, current_user.id)
    if not job:
        logger.warning("Job not found", 
                      job_id=str(job_id),
                      user_id=str(current_user.id))
        raise HTTPException(
            status_code=404,
            detail={
                "code": "JOB_NOT_FOUND",
                "message": "Job not found"
            }
        )
    
    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        result_url=job.result_image_url,
        error_message=job.error_message,
        created_at=job.created_at,
        completed_at=job.completed_at
    )


@router.get("/limits", response_model=Dict[str, Any])
@limiter.limit("60/minute")
async def get_user_limits(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    """Get user's current plan limits and usage summary."""
    
    logger.info("User limits request", user_id=str(current_user.id))
    
    with EntitlementsService(session) as entitlements:
        # Get usage summary
        usage_summary = entitlements.get_usage_summary(str(current_user.id), days=7)
        
        return {
            "user_id": str(current_user.id),
            **usage_summary
        }


@router.get("", response_model=List[JobRead])
@limiter.limit("60/minute")
async def get_user_jobs(
    request: Request,
    skip: int = 0,
    limit: int = 10,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    """Get user's job history with pagination."""
    
    logger.info("Job history request", 
               user_id=str(current_user.id),
               skip=skip,
               limit=limit)
    
    if limit > 50:
        limit = 50  # Max 50 jobs per request
    
    jobs = JobService.get_user_jobs(session, current_user.id, skip, limit)
    return [
        JobRead(
            id=job.id,
            user_id=job.user_id,
            job_type=job.job_type,
            status=job.status,
            progress=job.progress,
            input_image_url=job.input_image_url,
            target_image_url=job.target_image_url,
            result_image_url=job.result_image_url,
            parameters=job.parameters,
            credits_cost=job.credits_cost,
            error_message=job.error_message,
            created_at=job.created_at,
            completed_at=job.completed_at
        )
        for job in jobs
    ]