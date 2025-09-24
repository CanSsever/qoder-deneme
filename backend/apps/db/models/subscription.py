"""
Subscription model for payment processing and billing management.

This model tracks user subscriptions from payment providers like Superwall,
including subscription status, expiration dates, and raw event data for
audit and debugging purposes.
"""

from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Column, JSON, Text
import uuid


class Subscription(SQLModel, table=True):
    """
    User subscription tracking from payment providers.
    
    Stores subscription data from Superwall or other payment providers,
    including active status, expiration dates, and event metadata.
    """
    __tablename__ = "subscriptions"
    
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
        description="Unique subscription identifier"
    )
    
    user_id: str = Field(
        foreign_key="users.id",
        index=True,
        description="Reference to the user who owns this subscription"
    )
    
    product_id: str = Field(
        index=True,
        description="Product identifier from payment provider (e.g., 'pro_monthly', 'premium_annual')"
    )
    
    status: str = Field(
        index=True,
        description="Subscription status: active, expired, cancelled, pending, trialing"
    )
    
    expires_at: Optional[datetime] = Field(
        default=None,
        description="When the subscription expires (null for lifetime subscriptions)"
    )
    
    event_id: str = Field(
        unique=True,
        index=True,
        description="Unique event ID from payment provider for idempotency"
    )
    
    raw_payload_json: str = Field(
        sa_column=Column(Text),
        description="Raw JSON payload from payment provider webhook for debugging"
    )
    
    # Metadata
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this subscription record was created"
    )
    
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this subscription record was last updated"
    )
    
    # Provider metadata
    provider: str = Field(
        default="superwall",
        description="Payment provider name (superwall, stripe, apple, google)"
    )
    
    provider_subscription_id: Optional[str] = Field(
        default=None,
        description="Provider's internal subscription ID"
    )
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def is_active(self) -> bool:
        """Check if subscription is currently active."""
        if self.status not in ["active", "trialing"]:
            return False
        
        if self.expires_at is None:
            return True  # Lifetime subscription
        
        return datetime.utcnow() < self.expires_at
    
    def days_remaining(self) -> Optional[int]:
        """Get number of days remaining in subscription."""
        if self.expires_at is None:
            return None  # Lifetime subscription
        
        if not self.is_active():
            return 0
        
        delta = self.expires_at - datetime.utcnow()
        return max(0, delta.days)
    
    def to_dict(self) -> dict:
        """Convert subscription to dictionary for API responses."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "product_id": self.product_id,
            "status": self.status,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active(),
            "days_remaining": self.days_remaining(),
            "provider": self.provider,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class UserEntitlement(SQLModel, table=True):
    """
    User entitlements and plan limits.
    
    Defines what a user is entitled to based on their subscription,
    including job limits, parameter restrictions, and feature access.
    """
    __tablename__ = "user_entitlements"
    
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
        description="Unique entitlement identifier"
    )
    
    user_id: str = Field(
        foreign_key="users.id",
        index=True,
        description="Reference to the user who has this entitlement"
    )
    
    plan_code: str = Field(
        index=True,
        description="Plan code (free, pro, premium, enterprise)"
    )
    
    limits_json: str = Field(
        sa_column=Column(Text),
        description="JSON object containing plan limits and restrictions"
    )
    
    effective_from: datetime = Field(
        description="When this entitlement becomes effective"
    )
    
    effective_to: Optional[datetime] = Field(
        default=None,
        description="When this entitlement expires (null for active entitlements)"
    )
    
    # Metadata
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this entitlement was created"
    )
    
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this entitlement was last updated"
    )
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    def is_active(self) -> bool:
        """Check if entitlement is currently active."""
        now = datetime.utcnow()
        
        if now < self.effective_from:
            return False
        
        if self.effective_to is not None and now >= self.effective_to:
            return False
        
        return True
    
    def get_limits(self) -> dict:
        """Parse and return limits as dictionary."""
        import json
        try:
            return json.loads(self.limits_json)
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def get_daily_job_limit(self) -> int:
        """Get daily job creation limit."""
        limits = self.get_limits()
        return limits.get("daily_jobs", 0)
    
    def get_concurrent_job_limit(self) -> int:
        """Get concurrent job limit."""
        limits = self.get_limits()
        return limits.get("concurrent_jobs", 1)
    
    def get_max_side_limit(self) -> int:
        """Get maximum image side dimension limit."""
        limits = self.get_limits()
        return limits.get("max_side", 512)
    
    def get_features(self) -> list:
        """Get list of enabled features."""
        limits = self.get_limits()
        return limits.get("features", [])
    
    def has_feature(self, feature: str) -> bool:
        """Check if user has access to specific feature."""
        return feature in self.get_features()
    
    def to_dict(self) -> dict:
        """Convert entitlement to dictionary for API responses."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "plan_code": self.plan_code,
            "limits": self.get_limits(),
            "effective_from": self.effective_from.isoformat(),
            "effective_to": self.effective_to.isoformat() if self.effective_to else None,
            "is_active": self.is_active(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class UsageAggregate(SQLModel, table=True):
    """
    Daily usage aggregates for rate limiting and analytics.
    
    Tracks user usage patterns to enforce daily limits and provide
    usage analytics for billing and capacity planning.
    """
    __tablename__ = "usage_aggregates"
    
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
        description="Unique usage record identifier"
    )
    
    user_id: str = Field(
        foreign_key="users.id",
        index=True,
        description="Reference to the user this usage belongs to"
    )
    
    date: datetime = Field(
        index=True,
        description="Date for this usage aggregate (date only, time should be 00:00:00)"
    )
    
    jobs_created: int = Field(
        default=0,
        description="Number of jobs created on this date"
    )
    
    jobs_completed: int = Field(
        default=0,
        description="Number of jobs completed on this date"
    )
    
    jobs_failed: int = Field(
        default=0,
        description="Number of jobs that failed on this date"
    )
    
    total_processing_time_seconds: int = Field(
        default=0,
        description="Total processing time in seconds for all jobs"
    )
    
    total_credits_consumed: int = Field(
        default=0,
        description="Total credits consumed on this date"
    )
    
    # Metadata
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this usage record was created"
    )
    
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When this usage record was last updated"
    )
    
    class Config:
        # Ensure unique constraint on user_id + date
        indexes = [
            ("user_id", "date")
        ]
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
    
    @staticmethod
    def get_date_key(date: datetime = None) -> datetime:
        """Get normalized date key for aggregation (midnight UTC)."""
        if date is None:
            date = datetime.utcnow()
        return datetime(date.year, date.month, date.day)
    
    def to_dict(self) -> dict:
        """Convert usage aggregate to dictionary for API responses."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "date": self.date.isoformat(),
            "jobs_created": self.jobs_created,
            "jobs_completed": self.jobs_completed,
            "jobs_failed": self.jobs_failed,
            "total_processing_time_seconds": self.total_processing_time_seconds,
            "total_credits_consumed": self.total_credits_consumed,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


# Plan templates for bootstrap
PLAN_TEMPLATES = {
    "free": {
        "plan_code": "free",
        "limits": {
            "daily_jobs": 5,
            "concurrent_jobs": 1,
            "max_side": 512,
            "features": ["face_restore", "basic_upscale"]
        }
    },
    "pro": {
        "plan_code": "pro",
        "limits": {
            "daily_jobs": 50,
            "concurrent_jobs": 3,
            "max_side": 1024,
            "features": ["face_restore", "face_swap", "upscale", "batch_processing"]
        }
    },
    "premium": {
        "plan_code": "premium",
        "limits": {
            "daily_jobs": 200,
            "concurrent_jobs": 5,
            "max_side": 2048,
            "features": ["face_restore", "face_swap", "upscale", "batch_processing", "priority_queue", "api_access"]
        }
    }
}


# Pydantic models for API
class SubscriptionBase(SQLModel):
    """Base subscription model for shared fields."""
    product_id: str
    status: str
    provider: str = "superwall"


class SubscriptionCreate(SubscriptionBase):
    """Subscription creation model."""
    user_id: str
    event_id: str
    raw_payload_json: str
    expires_at: Optional[datetime] = None
    provider_subscription_id: Optional[str] = None


class SubscriptionUpdate(SQLModel):
    """Subscription update model."""
    status: Optional[str] = None
    expires_at: Optional[datetime] = None
    raw_payload_json: Optional[str] = None


class SubscriptionRead(SubscriptionBase):
    """Subscription read model."""
    id: str
    user_id: str
    expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    is_active: bool
    days_remaining: Optional[int]


# Receipt validation models (for legacy compatibility)
class ReceiptValidation(SQLModel):
    """Receipt validation model."""
    receipt_data: str
    platform: str  # "ios" or "android"


class ReceiptValidationResponse(SQLModel):
    """Receipt validation response model."""
    valid: bool
    product_id: Optional[str] = None
    transaction_id: Optional[str] = None
    credits_awarded: int = 0
    message: str