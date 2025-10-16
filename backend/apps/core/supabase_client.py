"""
Supabase client wrapper for connection management and operations.
"""
import os
from typing import Optional, Dict, Any, List
from supabase import create_client, Client, ClientOptions
from postgrest import APIResponse
import logging
from .settings import settings

logger = logging.getLogger(__name__)


class SupabaseClient:
    """Wrapper class for Supabase client with connection management and error handling."""
    
    def __init__(self):
        self._client: Optional[Client] = None
        if not (getattr(settings, "supabase_url", None) and getattr(settings, "supabase_anon_key", None)):
            logger.warning("Supabase configuration not found; client will initialize on first use")
    
    def _initialize_client(self):
        """Initialize the Supabase client with configuration."""
        try:
            if not settings.supabase_url or not settings.supabase_anon_key:
                raise ValueError("Supabase URL and anon key must be configured")
            
            options = ClientOptions(
                auto_refresh_token=True,
                persist_session=True
            )

            self._client = create_client(
                supabase_url=settings.supabase_url,
                supabase_key=settings.supabase_anon_key,
                options=options
            )
            logger.info("Supabase client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            raise
    
    @property
    def client(self) -> Client:
        """Get the Supabase client instance."""
        if self._client is None:
            self._initialize_client()
        return self._client
    
    def health_check(self) -> bool:
        """Check if Supabase connection is healthy."""
        try:
            # Simple health check by querying the profiles table
            response = self.client.table("profiles").select("id").limit(1).execute()
            return True
        except Exception as e:
            logger.error(f"Supabase health check failed: {e}")
            return False
    
    # Profile operations
    def get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile by user ID."""
        try:
            response = self.client.table("profiles").select("*").eq("id", user_id).single().execute()
            return response.data if response.data else None
        except Exception as e:
            logger.error(f"Failed to get profile for user {user_id}: {e}")
            return None
    
    def create_profile(self, user_id: str, email: str, credits: int = None) -> Optional[Dict[str, Any]]:
        """Create a new user profile."""
        try:
            profile_data = {
                "id": user_id,
                "email": email,
                "credits": credits or settings.default_credits,
                "subscription_status": "inactive"
            }
            response = self.client.table("profiles").insert(profile_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to create profile for user {user_id}: {e}")
            return None
    
    def update_profile(self, user_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update user profile."""
        try:
            response = self.client.table("profiles").update(updates).eq("id", user_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to update profile for user {user_id}: {e}")
            return None
    
    # Job operations
    def create_job(self, job_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new job record."""
        try:
            response = self.client.table("jobs").insert(job_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to create job: {e}")
            return None
    
    def get_job(self, job_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """Get job by ID for specific user."""
        try:
            response = (
                self.client.table("jobs")
                .select("*")
                .eq("id", job_id)
                .eq("user_id", user_id)
                .single()
                .execute()
            )
            return response.data if response.data else None
        except Exception as e:
            logger.error(f"Failed to get job {job_id} for user {user_id}: {e}")
            return None
    
    def get_user_jobs(self, user_id: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get jobs for a specific user with pagination."""
        try:
            response = (
                self.client.table("jobs")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .range(offset, offset + limit - 1)
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to get jobs for user {user_id}: {e}")
            return []
    
    def update_job(self, job_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update job status and details."""
        try:
            response = self.client.table("jobs").update(updates).eq("id", job_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to update job {job_id}: {e}")
            return None
    
    # Credit operations
    def get_credit_transactions(self, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get credit transactions for a user."""
        try:
            response = (
                self.client.table("credit_transactions")
                .select("*")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to get credit transactions for user {user_id}: {e}")
            return []
    
    def create_credit_transaction(self, transaction_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a credit transaction record."""
        try:
            response = self.client.table("credit_transactions").insert(transaction_data).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to create credit transaction: {e}")
            return None
    
    # RPC function calls for atomic operations
    def increment_credits(self, user_id: str, amount: int) -> bool:
        """Atomically increment user credits using RPC function."""
        try:
            response = self.client.rpc("increment_credits", {
                "target_user_id": user_id,
                "credit_amount": amount
            }).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to increment credits for user {user_id}: {e}")
            return False
    
    def validate_and_debit_credits(self, user_id: str, amount: int, job_id: str) -> bool:
        """Validate sufficient credits and debit them atomically."""
        try:
            response = self.client.rpc("validate_and_debit_credits", {
                "target_user_id": user_id,
                "credit_amount": amount,
                "job_ref_id": job_id
            }).execute()
            return response.data if response.data is not None else False
        except Exception as e:
            logger.error(f"Failed to validate and debit credits for user {user_id}: {e}")
            return False
    
    # Storage operations
    def get_upload_url(self, bucket: str, file_path: str) -> Optional[str]:
        """Get a signed upload URL for Supabase Storage."""
        try:
            response = self.client.storage.from_(bucket).create_signed_upload_url(file_path)
            return response.get("signedURL") if response else None
        except Exception as e:
            logger.error(f"Failed to get upload URL for {file_path}: {e}")
            return None
    
    def get_download_url(self, bucket: str, file_path: str, expires_in: int = 3600) -> Optional[str]:
        """Get a signed download URL for Supabase Storage."""
        try:
            response = self.client.storage.from_(bucket).create_signed_url(file_path, expires_in)
            return response.get("signedURL") if response else None
        except Exception as e:
            logger.error(f"Failed to get download URL for {file_path}: {e}")
            return None
    
    def upload_file(self, bucket: str, file_path: str, file_data: bytes) -> bool:
        """Upload file to Supabase Storage."""
        try:
            response = self.client.storage.from_(bucket).upload(file_path, file_data)
            return True
        except Exception as e:
            logger.error(f"Failed to upload file {file_path}: {e}")
            return False
    
    def delete_file(self, bucket: str, file_path: str) -> bool:
        """Delete file from Supabase Storage."""
        try:
            response = self.client.storage.from_(bucket).remove([file_path])
            return True
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            return False


# Global Supabase client instance
supabase_client = SupabaseClient()
