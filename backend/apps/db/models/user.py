"""
User model for authentication and user management.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import Field, SQLModel
from pydantic import EmailStr
from apps.core.config import SubscriptionStatus


class UserBase(SQLModel):
    """Base user model with shared fields."""
    email: EmailStr = Field(unique=True, index=True)
    credits: int = Field(default=10)
    subscription_status: str = Field(default=SubscriptionStatus.INACTIVE)
    subscription_expires_at: Optional[datetime] = None


class User(UserBase, table=True):
    """User database model."""
    __tablename__ = "users"
    
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class UserCreate(UserBase):
    """User creation schema."""
    password: str


class UserUpdate(SQLModel):
    """User update schema."""
    email: Optional[str] = None
    credits: Optional[int] = None
    subscription_status: Optional[str] = None
    subscription_expires_at: Optional[datetime] = None


class UserRead(UserBase):
    """User read schema (for API responses)."""
    id: UUID
    created_at: datetime
    updated_at: datetime


class UserLogin(SQLModel):
    """User login schema."""
    email: EmailStr
    password: str


class UserResponse(SQLModel):
    """User response with token."""
    access_token: str
    token_type: str = "bearer"
    user: UserRead