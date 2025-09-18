"""
Credit transaction model for tracking credit usage and purchases.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import Field, SQLModel
from apps.core.config import TransactionType


class CreditTransactionBase(SQLModel):
    """Base credit transaction model with shared fields."""
    amount: int = Field(description="Credit amount (positive for additions, negative for usage)")
    transaction_type: str = Field(description="Type of transaction")
    reference_id: Optional[str] = Field(default=None, description="Reference to job ID or receipt ID")
    description: Optional[str] = Field(default=None, description="Human-readable description")


class CreditTransaction(CreditTransactionBase, table=True):
    """Credit transaction database model."""
    __tablename__ = "credit_transactions"
    
    id: Optional[UUID] = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CreditTransactionCreate(CreditTransactionBase):
    """Credit transaction creation schema."""
    user_id: UUID


class CreditTransactionRead(CreditTransactionBase):
    """Credit transaction read schema (for API responses)."""
    id: UUID
    user_id: UUID
    created_at: datetime


class CreditBalance(SQLModel):
    """User credit balance summary."""
    user_id: UUID
    current_balance: int
    total_earned: int
    total_spent: int
    last_transaction_at: Optional[datetime] = None