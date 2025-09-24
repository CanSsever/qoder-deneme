"""
Authentication service for user management and JWT handling.
"""
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
from sqlmodel import Session, select
from apps.core.security import SecurityUtils
from apps.core.exceptions import AuthenticationError, NotFoundError, ValidationError
from apps.core.settings import settings
from apps.db.models.user import User, UserCreate, UserLogin, UserResponse, UserRead
from apps.db.models.credit import CreditTransaction, CreditTransactionCreate
from apps.core.config import TransactionType


class AuthService:
    """Authentication service for user management."""
    
    @staticmethod
    def create_user(session: Session, user_data: UserCreate) -> User:
        """Create a new user with hashed password."""
        # Check if user already exists
        statement = select(User).where(User.email == user_data.email)
        existing_user = session.exec(statement).first()
        if existing_user:
            raise ValidationError("Email already registered")
        
        # Create user with hashed password
        hashed_password = SecurityUtils.get_password_hash(user_data.password)
        user = User(
            email=user_data.email,
            hashed_password=hashed_password,
            credits=settings.default_credits,
            subscription_status=user_data.subscription_status,
            subscription_expires_at=user_data.subscription_expires_at
        )
        
        session.add(user)
        session.commit()
        session.refresh(user)
        
        # Create initial credit transaction
        credit_transaction = CreditTransaction(
            user_id=user.id,
            amount=settings.default_credits,
            transaction_type=TransactionType.BONUS,
            description="Welcome bonus credits"
        )
        session.add(credit_transaction)
        session.commit()
        
        return user
    
    @staticmethod
    def authenticate_user(session: Session, email: str, password: str) -> Optional[User]:
        """Authenticate user with email and password."""
        statement = select(User).where(User.email == email)
        user = session.exec(statement).first()
        
        if not user:
            return None
        
        if not SecurityUtils.verify_password(password, user.hashed_password):
            return None
        
        return user
    
    @staticmethod
    def login_user(session: Session, login_data: UserLogin) -> UserResponse:
        """Login user and return JWT token."""
        user = AuthService.authenticate_user(
            session, 
            login_data.email, 
            login_data.password
        )
        
        if not user:
            raise AuthenticationError("Invalid email or password")
        
        # Create access token
        access_token = SecurityUtils.create_access_token(
            data={"sub": str(user.id)}
        )
        
        # Update last login time
        user.updated_at = datetime.utcnow()
        session.add(user)
        session.commit()
        session.refresh(user)
        
        return UserResponse(
            access_token=access_token,
            user=UserRead(
                id=user.id,
                email=user.email,
                credits=user.credits,
                subscription_status=user.subscription_status,
                subscription_expires_at=user.subscription_expires_at,
                created_at=user.created_at,
                updated_at=user.updated_at
            )
        )
    
    @staticmethod
    def get_user_by_id(session: Session, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        return session.get(User, user_id)
    
    @staticmethod
    def get_user_by_email(session: Session, email: str) -> Optional[User]:
        """Get user by email."""
        statement = select(User).where(User.email == email)
        return session.exec(statement).first()
    
    @staticmethod
    def update_user_credits(session: Session, user_id: UUID, credits_change: int, transaction_type: str, reference_id: Optional[str] = None) -> User:
        """Update user credits and create transaction record."""
        user = AuthService.get_user_by_id(session, user_id)
        if not user:
            raise NotFoundError("User", str(user_id))
        
        # Update user credits
        user.credits += credits_change
        user.updated_at = datetime.utcnow()
        session.add(user)
        
        # Create credit transaction
        credit_transaction = CreditTransaction(
            user_id=user_id,
            amount=credits_change,
            transaction_type=transaction_type,
            reference_id=reference_id
        )
        session.add(credit_transaction)
        
        session.commit()
        session.refresh(user)
        return user