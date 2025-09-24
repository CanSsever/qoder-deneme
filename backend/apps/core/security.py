"""
Security utilities for authentication and authorization.
"""
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlmodel import Session, select
from apps.core.settings import settings
from apps.db.session import get_session
from apps.db.models.user import User

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT token scheme
bearer_scheme = HTTPBearer()


class SecurityUtils:
    """Security utility functions."""
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """Generate password hash."""
        return pwd_context.hash(password)
    
    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(hours=settings.jwt_expiration_hours)
        
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(
            to_encode, 
            settings.jwt_secret, 
            algorithm=settings.jwt_algorithm
        )
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str) -> Optional[dict]:
        """Verify and decode JWT token."""
        try:
            payload = jwt.decode(
                token, 
                settings.jwt_secret, 
                algorithms=[settings.jwt_algorithm]
            )
            return payload
        except JWTError:
            return None


class AuthenticationDependency:
    """Authentication dependency for FastAPI routes."""
    
    @staticmethod
    def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
        session: Session = Depends(get_session)
    ) -> User:
        """Get current authenticated user from JWT token."""
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        # Verify token
        payload = SecurityUtils.verify_token(credentials.credentials)
        if payload is None:
            raise credentials_exception
        
        # Extract user ID from token
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        
        # Get user from database
        try:
            user_uuid = UUID(user_id)
            statement = select(User).where(User.id == user_uuid)
            user = session.exec(statement).first()
            if user is None:
                raise credentials_exception
            return user
        except (ValueError, Exception):
            raise credentials_exception
    
    @staticmethod
    def get_current_active_user(
        current_user: User = Depends(get_current_user)
    ) -> User:
        """Get current active user (additional checks can be added here)."""
        # Add any additional user validation logic here
        # For example, check if user is active, verified, etc.
        return current_user


# Convenience functions for dependency injection
get_current_user = AuthenticationDependency.get_current_user
get_current_active_user = AuthenticationDependency.get_current_active_user