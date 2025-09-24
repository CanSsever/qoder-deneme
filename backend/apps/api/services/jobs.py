"""
Job service for managing AI processing jobs.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID
from sqlmodel import Session, select
from apps.db.models.job import Job, JobCreate
from apps.core.config import CREDIT_COSTS, JobType
from apps.core.exceptions import InsufficientCreditsError
from apps.api.services.auth import AuthService
from apps.db.models.user import User


class JobService:
    """Job processing service for managing AI tasks."""
    
    @staticmethod
    def create_job(session: Session, user: User, job_data: JobCreate) -> Job:
        """Create a new AI processing job."""
        from apps.core.config import CREDIT_COSTS, JOB_TIMEOUTS, JobType
        
        # Check if user has enough credits
        credits_required = CREDIT_COSTS.get(JobType(job_data.job_type), 1)
        if user.credits < credits_required:
            from apps.core.exceptions import InsufficientCreditsError
            raise InsufficientCreditsError(credits_required, user.credits)
        
        # Create job record
        # Ensure user.id is not None
        if user.id is None:
            raise ValueError("User ID is required")
            
        job = Job(
            user_id=user.id,
            job_type=job_data.job_type,
            input_image_url=job_data.input_image_url,
            target_image_url=job_data.target_image_url,
            parameters=job_data.parameters,
            credits_cost=credits_required
        )
        
        session.add(job)
        session.commit()
        session.refresh(job)
        
        # Deduct credits from user
        AuthService.update_user_credits(
            session, 
            user.id,
            -credits_required, 
            "usage",
            str(job.id)
        )
        
        # Queue background job (placeholder - would integrate with Celery)
        # queue_ai_processing_task.delay(str(job.id))
        
        return job
    
    @staticmethod
    def get_job(session: Session, job_id: UUID, user_id: UUID) -> Optional[Job]:
        """Get job by ID and user ID."""
        statement = select(Job).where(Job.id == job_id, Job.user_id == user_id)
        return session.exec(statement).first()
    
    @staticmethod
    def update_job_status(session: Session, job_id: UUID, status: str, progress: Optional[float] = None, result_url: Optional[str] = None, error_message: Optional[str] = None) -> Optional[Job]:
        """Update job status and progress."""
        job = session.get(Job, job_id)
        if not job:
            return None
        
        job.status = status
        if progress is not None:
            job.progress = progress
        if result_url:
            job.result_image_url = result_url
        if error_message:
            job.error_message = error_message
        if status in ['completed', 'failed']:
            job.completed_at = datetime.utcnow()
        
        session.add(job)
        session.commit()
        session.refresh(job)
        return job
    
    @staticmethod
    def get_user_jobs(session: Session, user_id: UUID, skip: int = 0, limit: int = 10) -> list:
        """Get user's jobs with pagination."""
        statement = select(Job).where(Job.user_id == user_id).offset(skip).limit(limit)
        return list(session.exec(statement).all())