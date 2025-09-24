"""
Entitlements service for managing user plans, limits, and usage tracking.

This service handles:
- User entitlement validation and retrieval
- Usage tracking and daily limit enforcement
- Plan upgrades and downgrades
- Feature access control
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from sqlmodel import Session, select, func
import structlog

from apps.core.settings import settings
from apps.core.exceptions import ValidationError, PermissionError
from apps.db.session import engine
from apps.db.models.subscription import Subscription, UserEntitlement, UsageAggregate, PLAN_TEMPLATES
from apps.db.models.job import Job

logger = structlog.get_logger(__name__)


class EntitlementsService:
    """
    Service for managing user entitlements and usage limits.
    
    Provides functionality for:
    - Retrieving active user entitlements
    - Validating job creation against limits
    - Tracking usage and enforcing daily caps
    - Managing plan transitions
    """
    
    def __init__(self, session: Session = None):
        """
        Initialize entitlements service.
        
        Args:
            session: Database session (optional, will create if not provided)
        """
        self.session = session
        self._should_close_session = session is None
        
        if self.session is None:
            self.session = Session(engine)
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self._should_close_session and self.session:
            self.session.close()
    
    def get_user_entitlement(self, user_id: str) -> Optional[UserEntitlement]:
        """
        Get active entitlement for user.
        
        Args:
            user_id: User identifier
            
        Returns:
            Active UserEntitlement or None if not found
        """
        try:
            now = datetime.utcnow()
            
            statement = select(UserEntitlement).where(
                UserEntitlement.user_id == user_id,
                UserEntitlement.effective_from <= now,
                (UserEntitlement.effective_to.is_(None)) | (UserEntitlement.effective_to > now)
            ).order_by(UserEntitlement.created_at.desc())
            
            entitlement = self.session.exec(statement).first()
            
            if entitlement:
                logger.info(
                    "Retrieved user entitlement",
                    user_id=user_id,
                    plan_code=entitlement.plan_code,
                    effective_from=entitlement.effective_from.isoformat(),
                    effective_to=entitlement.effective_to.isoformat() if entitlement.effective_to else None
                )
            
            return entitlement
            
        except Exception as e:
            logger.error("Failed to get user entitlement", user_id=user_id, error=str(e))
            return None
    
    def get_user_limits(self, user_id: str) -> Dict[str, any]:
        """
        Get user limits with fallback to default values.
        
        Args:
            user_id: User identifier
            
        Returns:
            Dictionary containing user limits
        """
        entitlement = self.get_user_entitlement(user_id)
        
        if entitlement and entitlement.is_active():
            limits = entitlement.get_limits()
            plan_code = entitlement.plan_code
        else:
            # Fallback to default plan or settings
            default_plan = settings.entitlements_default_plan
            if default_plan in PLAN_TEMPLATES:
                limits = PLAN_TEMPLATES[default_plan]["limits"].copy()
                plan_code = default_plan
            else:
                limits = {
                    "daily_jobs": settings.fallback_daily_job_limit,
                    "concurrent_jobs": settings.fallback_concurrent_job_limit,
                    "max_side": settings.fallback_max_side_limit,
                    "features": ["face_restore"]
                }
                plan_code = "fallback"
        
        logger.info(
            "Retrieved user limits",
            user_id=user_id,
            plan_code=plan_code,
            daily_jobs=limits.get("daily_jobs"),
            concurrent_jobs=limits.get("concurrent_jobs"),
            max_side=limits.get("max_side")
        )
        
        return {
            "plan_code": plan_code,
            "daily_jobs": limits.get("daily_jobs", 0),
            "concurrent_jobs": limits.get("concurrent_jobs", 1),
            "max_side": limits.get("max_side", 512),
            "features": limits.get("features", [])
        }
    
    def get_daily_usage(self, user_id: str, date: datetime = None) -> UsageAggregate:
        """
        Get or create daily usage aggregate for user.
        
        Args:
            user_id: User identifier
            date: Date for usage (defaults to today)
            
        Returns:
            UsageAggregate for the specified date
        """
        if date is None:
            date = datetime.utcnow()
        
        date_key = UsageAggregate.get_date_key(date)
        
        # Try to get existing aggregate
        statement = select(UsageAggregate).where(
            UsageAggregate.user_id == user_id,
            UsageAggregate.date == date_key
        )
        
        usage = self.session.exec(statement).first()
        
        if not usage:
            # Create new aggregate
            usage = UsageAggregate(
                user_id=user_id,
                date=date_key,
                jobs_created=0,
                jobs_completed=0,
                jobs_failed=0,
                total_processing_time_seconds=0,
                total_credits_consumed=0
            )
            self.session.add(usage)
            self.session.commit()
            self.session.refresh(usage)
            
            logger.info(
                "Created new usage aggregate",
                user_id=user_id,
                date=date_key.isoformat()
            )
        
        return usage
    
    def check_job_creation_limits(self, user_id: str, job_params: Dict[str, any]) -> Tuple[bool, str]:
        """
        Check if user can create a new job based on limits.
        
        Args:
            user_id: User identifier
            job_params: Job parameters to validate
            
        Returns:
            Tuple of (can_create: bool, error_message: str)
        """
        try:
            limits = self.get_user_limits(user_id)
            
            # Check daily job limit
            daily_usage = self.get_daily_usage(user_id)
            if daily_usage.jobs_created >= limits["daily_jobs"]:
                return False, f"Daily job limit exceeded ({limits['daily_jobs']} jobs per day)"
            
            # Check concurrent job limit
            concurrent_jobs = self.session.exec(
                select(func.count(Job.id)).where(
                    Job.user_id == user_id,
                    Job.status.in_(["pending", "running"])
                )
            ).one()
            
            if concurrent_jobs >= limits["concurrent_jobs"]:
                return False, f"Concurrent job limit exceeded ({limits['concurrent_jobs']} concurrent jobs)"
            
            # Check max_side parameter
            max_side_limit = limits["max_side"]
            for param_name in ["max_side", "max_width", "max_height"]:
                if param_name in job_params:
                    param_value = job_params[param_name]
                    if isinstance(param_value, int) and param_value > max_side_limit:
                        return False, f"Parameter {param_name}={param_value} exceeds limit of {max_side_limit}"
            
            # Check feature access
            job_type = job_params.get("job_type", "")
            available_features = limits["features"]
            
            feature_mapping = {
                "face_restore": ["face_restore", "basic_upscale"],
                "face_swap": ["face_swap"],
                "upscale": ["upscale", "basic_upscale"]
            }
            
            required_features = feature_mapping.get(job_type, [job_type])
            for feature in required_features:
                if feature not in available_features:
                    return False, f"Feature '{feature}' not available in {limits['plan_code']} plan"
            
            logger.info(
                "Job creation limits check passed",
                user_id=user_id,
                plan_code=limits["plan_code"],
                daily_usage=daily_usage.jobs_created,
                daily_limit=limits["daily_jobs"],
                concurrent_jobs=concurrent_jobs,
                concurrent_limit=limits["concurrent_jobs"]
            )
            
            return True, ""
            
        except Exception as e:
            logger.error("Failed to check job creation limits", user_id=user_id, error=str(e))
            return False, f"Failed to validate limits: {str(e)}"
    
    def increment_job_usage(self, user_id: str, job_type: str = None) -> None:
        """
        Increment job creation count for user.
        
        Args:
            user_id: User identifier
            job_type: Type of job created (for analytics)
        """
        try:
            usage = self.get_daily_usage(user_id)
            usage.jobs_created += 1
            usage.updated_at = datetime.utcnow()
            
            self.session.commit()
            
            logger.info(
                "Incremented job usage",
                user_id=user_id,
                job_type=job_type,
                total_jobs_today=usage.jobs_created
            )
            
        except Exception as e:
            logger.error("Failed to increment job usage", user_id=user_id, error=str(e))
    
    def update_job_completion(self, user_id: str, job_status: str, processing_time_seconds: int = 0) -> None:
        """
        Update job completion statistics.
        
        Args:
            user_id: User identifier
            job_status: Final job status (succeeded, failed, cancelled)
            processing_time_seconds: Time taken to process job
        """
        try:
            usage = self.get_daily_usage(user_id)
            
            if job_status == "succeeded":
                usage.jobs_completed += 1
            elif job_status == "failed":
                usage.jobs_failed += 1
            
            usage.total_processing_time_seconds += processing_time_seconds
            usage.updated_at = datetime.utcnow()
            
            self.session.commit()
            
            logger.info(
                "Updated job completion statistics",
                user_id=user_id,
                job_status=job_status,
                processing_time_seconds=processing_time_seconds,
                total_completed=usage.jobs_completed,
                total_failed=usage.jobs_failed
            )
            
        except Exception as e:
            logger.error("Failed to update job completion", user_id=user_id, error=str(e))
    
    def create_entitlement(self, user_id: str, plan_code: str, effective_from: datetime = None, 
                          effective_to: datetime = None) -> UserEntitlement:
        """
        Create new entitlement for user.
        
        Args:
            user_id: User identifier
            plan_code: Plan code (free, pro, premium)
            effective_from: When entitlement starts (defaults to now)
            effective_to: When entitlement ends (optional)
            
        Returns:
            Created UserEntitlement
            
        Raises:
            ValidationError: If plan_code is invalid
        """
        if plan_code not in PLAN_TEMPLATES:
            raise ValidationError(f"Invalid plan code: {plan_code}")
        
        if effective_from is None:
            effective_from = datetime.utcnow()
        
        # End any existing active entitlements
        self._end_active_entitlements(user_id, effective_from)
        
        # Create new entitlement
        limits = PLAN_TEMPLATES[plan_code]["limits"]
        entitlement = UserEntitlement(
            user_id=user_id,
            plan_code=plan_code,
            limits_json=json.dumps(limits),
            effective_from=effective_from,
            effective_to=effective_to
        )
        
        self.session.add(entitlement)
        self.session.commit()
        self.session.refresh(entitlement)
        
        logger.info(
            "Created user entitlement",
            user_id=user_id,
            plan_code=plan_code,
            entitlement_id=entitlement.id,
            effective_from=effective_from.isoformat(),
            effective_to=effective_to.isoformat() if effective_to else None
        )
        
        return entitlement
    
    def _end_active_entitlements(self, user_id: str, end_time: datetime) -> None:
        """
        End all active entitlements for user.
        
        Args:
            user_id: User identifier
            end_time: When to end the entitlements
        """
        statement = select(UserEntitlement).where(
            UserEntitlement.user_id == user_id,
            UserEntitlement.effective_to.is_(None)
        )
        
        active_entitlements = self.session.exec(statement).all()
        
        for entitlement in active_entitlements:
            entitlement.effective_to = end_time
            entitlement.updated_at = datetime.utcnow()
        
        if active_entitlements:
            self.session.commit()
            logger.info(
                "Ended active entitlements",
                user_id=user_id,
                count=len(active_entitlements),
                end_time=end_time.isoformat()
            )
    
    def get_usage_summary(self, user_id: str, days: int = 7) -> Dict[str, any]:
        """
        Get usage summary for user over specified period.
        
        Args:
            user_id: User identifier
            days: Number of days to include in summary
            
        Returns:
            Usage summary dictionary
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        start_date = UsageAggregate.get_date_key(start_date)
        
        statement = select(UsageAggregate).where(
            UsageAggregate.user_id == user_id,
            UsageAggregate.date >= start_date
        ).order_by(UsageAggregate.date.desc())
        
        usage_records = self.session.exec(statement).all()
        
        total_jobs = sum(record.jobs_created for record in usage_records)
        total_completed = sum(record.jobs_completed for record in usage_records)
        total_failed = sum(record.jobs_failed for record in usage_records)
        total_processing_time = sum(record.total_processing_time_seconds for record in usage_records)
        
        # Get current limits
        limits = self.get_user_limits(user_id)
        
        # Get today's usage
        today_usage = self.get_daily_usage(user_id)
        
        return {
            "user_id": user_id,
            "period_days": days,
            "current_plan": limits["plan_code"],
            "current_limits": limits,
            "today": {
                "jobs_created": today_usage.jobs_created,
                "daily_limit": limits["daily_jobs"],
                "remaining_today": max(0, limits["daily_jobs"] - today_usage.jobs_created)
            },
            "period_summary": {
                "total_jobs_created": total_jobs,
                "total_jobs_completed": total_completed,
                "total_jobs_failed": total_failed,
                "total_processing_time_seconds": total_processing_time,
                "success_rate": (total_completed / total_jobs * 100) if total_jobs > 0 else 0
            },
            "daily_usage": [
                {
                    "date": record.date.isoformat(),
                    "jobs_created": record.jobs_created,
                    "jobs_completed": record.jobs_completed,
                    "jobs_failed": record.jobs_failed
                }
                for record in usage_records
            ]
        }


# Helper functions for easy import
def get_user_limits(user_id: str) -> Dict[str, any]:
    """Get user limits (convenience function)."""
    with EntitlementsService() as service:
        return service.get_user_limits(user_id)


def check_job_limits(user_id: str, job_params: Dict[str, any]) -> Tuple[bool, str]:
    """Check job creation limits (convenience function)."""
    with EntitlementsService() as service:
        return service.check_job_creation_limits(user_id, job_params)


def increment_job_usage(user_id: str, job_type: str = None) -> None:
    """Increment job usage (convenience function)."""
    with EntitlementsService() as service:
        service.increment_job_usage(user_id, job_type)