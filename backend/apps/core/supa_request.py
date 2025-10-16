"""
Per-request Supabase client management for proper RLS enforcement.

This module provides request-scoped Supabase clients that use user JWT tokens
for RLS enforcement and service role clients for controlled admin operations.

Key principles:
- User operations use user JWT tokens (RLS enforced)
- Admin operations use service role only when necessary
- Credits RPC uses service role with SECURITY DEFINER functions
"""

from typing import Optional, Tuple
from supabase import create_client, Client
import logging

from apps.core.settings import settings

logger = logging.getLogger(__name__)


def _get_supabase_config() -> Tuple[str, str, str]:
    """
    Retrieve Supabase connection details from settings and ensure they exist.
    """
    url = settings.supabase_url
    anon = settings.supabase_anon_key
    service_key = settings.supabase_service_role_key

    missing = [
        name
        for name, value in (
            ("SUPABASE_URL", url),
            ("SUPABASE_ANON_KEY", anon),
            ("SUPABASE_SERVICE_ROLE_KEY", service_key),
        )
        if not value
    ]

    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(
            f"Supabase configuration missing required values: {joined}. "
            "Ensure backend/.env is populated or environment variables are set."
        )

    return url, anon, service_key


def user_client(user_jwt: str) -> Client:
    """
    Create a request-scoped Supabase client using user JWT token.
    
    This client will enforce Row Level Security (RLS) policies based on the
    authenticated user. Use this for all user-scoped operations like:
    - Reading user's jobs
    - Creating user's content
    - Accessing user's files
    
    Args:
        user_jwt: The Supabase JWT token from the Authorization header
        
    Returns:
        Supabase client configured with user authentication
        
    Example:
        token = require_token()  # From FastAPI dependency
        client = user_client(token)
        jobs = client.table("jobs").select("*").execute()  # RLS enforced
    """
    url, anon_key, _ = _get_supabase_config()
    
    # Create client with anon key
    client = create_client(url, anon_key)
    
    # Set the user JWT token for PostgREST authentication
    client.postgrest.auth(user_jwt)
    
    # Set auth token for storage and other Supabase services
    client.auth.set_auth(user_jwt)
    
    logger.debug("Created user-scoped Supabase client")
    return client


def service_client() -> Client:
    """
    Create a service role Supabase client for admin operations.
    
    This client bypasses RLS and has full access to all data. Use sparingly
    and only for controlled operations like:
    - Credit system RPC functions (with SECURITY DEFINER)
    - User invitations and admin tasks
    - System maintenance operations
    
    SECURITY WARNING: This client can access all user data. Only use for
    operations that require system-level access and ensure proper validation.
    
    Returns:
        Supabase client with service role permissions
        
    Example:
        client = service_client()
        # Only for controlled admin operations
        result = client.rpc("increment_credits", {"user_id": user_id, "amount": 10})
    """
    url, _, service_key = _get_supabase_config()

    client = create_client(url, service_key)
    
    logger.debug("Created service role Supabase client")
    return client


class SupabaseClientManager:
    """
    Context manager for Supabase clients with proper error handling.
    
    This class provides a clean interface for managing Supabase client
    lifecycle and ensures proper cleanup and error handling.
    """
    
    def __init__(self, user_jwt: Optional[str] = None, use_service_role: bool = False):
        """
        Initialize client manager.
        
        Args:
            user_jwt: User JWT token for user-scoped operations
            use_service_role: If True, use service role client
        """
        self.user_jwt = user_jwt
        self.use_service_role = use_service_role
        self._client: Optional[Client] = None
    
    def __enter__(self) -> Client:
        """Create and return the appropriate Supabase client."""
        try:
            if self.use_service_role:
                self._client = service_client()
            elif self.user_jwt:
                self._client = user_client(self.user_jwt)
            else:
                raise ValueError("Either user_jwt or use_service_role=True must be provided")
            
            return self._client
        except Exception as e:
            logger.error(f"Failed to create Supabase client: {e}")
            raise
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up client resources."""
        if self._client:
            try:
                # Perform any necessary cleanup
                # Supabase client doesn't require explicit cleanup, but we can log
                if exc_type:
                    logger.error(f"Supabase operation failed: {exc_val}")
                else:
                    logger.debug("Supabase operation completed successfully")
            except Exception as e:
                logger.warning(f"Error during client cleanup: {e}")
        
        self._client = None


# Convenience functions for common patterns
def with_user_client(user_jwt: str):
    """
    Decorator/context manager for user-scoped operations.
    
    Example:
        with with_user_client(token) as client:
            jobs = client.table("jobs").select("*").execute()
    """
    return SupabaseClientManager(user_jwt=user_jwt)


def with_service_client():
    """
    Decorator/context manager for service role operations.
    
    Example:
        with with_service_client() as client:
            result = client.rpc("increment_credits", params)
    """
    return SupabaseClientManager(use_service_role=True)


# Legacy support - maintain compatibility with existing code
def get_user_scoped_client(user_jwt: str) -> Client:
    """
    Legacy function for backward compatibility.
    
    Deprecated: Use user_client() instead.
    """
    logger.warning("get_user_scoped_client is deprecated, use user_client() instead")
    return user_client(user_jwt)


def get_service_role_client() -> Client:
    """
    Legacy function for backward compatibility.
    
    Deprecated: Use service_client() instead.
    """
    logger.warning("get_service_role_client is deprecated, use service_client() instead")
    return service_client()
