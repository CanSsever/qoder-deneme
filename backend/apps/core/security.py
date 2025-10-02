"""
Security utilities for Supabase authentication and authorization.
"""
from datetime import datetime
from typing import Optional
import jwt
from fastapi import Depends, HTTPException, status, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jwt import decode as jwt_decode, InvalidTokenError
from apps.core.settings import settings
from apps.core.supabase_client import supabase_client

# JWT token scheme
bearer_scheme = HTTPBearer()


class SupabaseUser:
    """User object extracted from Supabase JWT token."""
    
    def __init__(self, user_id: str, email: str, payload: dict):
        self.id = user_id
        self.email = email
        self.payload = payload
        self.raw_token_payload = payload
    
    def __str__(self):
        return f"SupabaseUser(id={self.id}, email={self.email})"
    
    def __repr__(self):
        return self.__str__()


class SecurityUtils:
    """Security utility functions for Supabase."""
    
    @staticmethod
    def verify_supabase_token(token: str) -> Optional[dict]:
        """Verify and decode Supabase JWT token."""
        try:
            # Decode token using Supabase JWT secret
            payload = jwt_decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated"
            )
            return payload
        except InvalidTokenError as e:
            print(f"JWT validation failed: {e}")  # For debugging
            return None
        except Exception as e:
            print(f"Unexpected error in JWT validation: {e}")  # For debugging
            return None
    
    @staticmethod
    def extract_user_from_token(payload: dict) -> Optional[SupabaseUser]:
        """Extract user information from JWT payload."""
        try:
            user_id = payload.get("sub")
            email = payload.get("email")
            
            if not user_id:
                return None
            
            return SupabaseUser(user_id=user_id, email=email, payload=payload)
        except Exception as e:
            print(f"Failed to extract user from token: {e}")  # For debugging
            return None


class AuthenticationDependency:
    """Authentication dependency for FastAPI routes using Supabase."""
    
    @staticmethod
    def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)
    ) -> SupabaseUser:
        """Get current authenticated user from Supabase JWT token."""
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
        # Verify Supabase token
        payload = SecurityUtils.verify_supabase_token(credentials.credentials)
        if payload is None:
            raise credentials_exception
        
        # Extract user from token payload
        user = SecurityUtils.extract_user_from_token(payload)
        if user is None:
            raise credentials_exception
        
        return user
    
    @staticmethod
    def get_current_active_user(
        current_user: SupabaseUser = Depends(get_current_user)
    ) -> SupabaseUser:
        """Get current active user (additional checks can be added here)."""
        # Add any additional user validation logic here
        # For example, check if user is active, verified, etc.
        return current_user
    
    @staticmethod
    def get_optional_user(
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
    ) -> Optional[SupabaseUser]:
        """Get current user if token is provided, otherwise return None."""
        if not credentials:
            return None
        
        try:
            payload = SecurityUtils.verify_supabase_token(credentials.credentials)
            if payload is None:
                return None
            
            return SecurityUtils.extract_user_from_token(payload)
        except Exception:
            return None


# Convenience functions for dependency injection
get_current_user = AuthenticationDependency.get_current_user
get_current_active_user = AuthenticationDependency.get_current_active_user
get_optional_user = AuthenticationDependency.get_optional_user


# Token extraction helpers for per-request client authentication
def require_token(authorization: str = Header(None)) -> str:
    """Extract and validate Authorization header token."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    return authorization.split()[1]


def get_current_user_id(authorization: str = Header(None)) -> str:
    """Extract user ID from Authorization header token."""
    token = require_token(authorization)
    try:
        payload = jwt_decode(token, settings.supabase_jwt_secret, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return user_id
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_raw_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> str:
    """Get raw JWT token for client authentication."""
    return credentials.credentials