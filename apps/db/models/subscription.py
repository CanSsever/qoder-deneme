"""
Subscription model for managing user subscriptions and payments.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import Field, SQLModel
from apps.core.config import SubscriptionStatus


class SubscriptionBase(SQLModel):
    """Base subscription model with shared fields."""
    product_id: str = Field(description="Product ID from payment provider")
    transaction_id: str = Field(unique=True, description="Unique transaction ID from payment provider")
    receipt_data: str = Field(description="Raw receipt data from payment provider")
    status: str = Field(default=SubscriptionStatus.ACTIVE)
    credits_included: int = Field(description="Number of credits included in subscription")
    expires_at: datetime = Field(description="Subscription expiration date")


class Subscription(SubscriptionBase, table=True):
    """Subscription database model."""
    __tablename__ = "subscriptions"
    
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SubscriptionCreate(SubscriptionBase):
    """Subscription creation schema."""
    user_id: UUID


class SubscriptionUpdate(SQLModel):
    """Subscription update schema."""
    status: Optional[str] = None
    expires_at: Optional[datetime] = None


class SubscriptionRead(SubscriptionBase):
    """Subscription read schema (for API responses)."""
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime


class ReceiptValidation(SQLModel):
    """Receipt validation request schema."""
    receipt_data: str
    product_id: str
    transaction_id: str


class ReceiptValidationResponse(SQLModel):
    """Receipt validation response schema."""
    valid: bool
    credits_added: int
    subscription_status: str
    expires_at: Optional[datetime] = None
    error_message: Optional[str] = None