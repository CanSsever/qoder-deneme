"""
Supabase-based services for user management, jobs, and billing.
Replaces SQLModel-based services with PostgREST API calls.

These services now support per-request user JWT authentication for proper RLS enforcement.
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4
import structlog
import time
import os
from apps.core.security import SupabaseUser
from apps.core.exceptions import AuthenticationError, NotFoundError, ValidationError
from apps.core.settings import settings
from apps.core.supabase_client import supabase_client
from apps.core.supa_request import user_client, service_client

# Initialize structured logger
logger = structlog.get_logger()


class ProfileService:
    """Profile service for user management using Supabase."""
    
    @staticmethod
    def get_or_create_profile(user: SupabaseUser) -> Optional[Dict[str, Any]]:
        """Get or create user profile from Supabase."""
        try:
            # Try to get existing profile
            profile = supabase_client.get_profile(user.id)
            
            if profile is None:
                # Create new profile using RPC function
                response = supabase_client.client.rpc(
                    "bootstrap_user_profile",
                    {
                        "user_id": user.id,
                        "user_email": user.email,
                        "initial_credits": settings.default_credits
                    }
                ).execute()
                
                if response.data:
                    # Get the created profile
                    profile = supabase_client.get_profile(user.id)
                
            return profile
            
        except Exception as e:
            logger.error(f"Failed to get or create profile for user {user.id}: {e}")
            return None
    
    @staticmethod
    def update_profile(user_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update user profile."""
        return supabase_client.update_profile(user_id, updates)
    
    @staticmethod
    def get_profile(user_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile by ID."""
        return supabase_client.get_profile(user_id)


class UploadService:
    """Supabase Storage service for handling file uploads."""
    
    @staticmethod
    def get_upload_instructions(
        user_id: str,
        filename: str, 
        content_type: str, 
        file_size: int
    ) -> Dict[str, Any]:
        """Get upload instructions for Supabase Storage."""
        # Validate file size
        max_size = settings.max_file_size_mb * 1024 * 1024  # Convert to bytes
        if file_size > max_size:
            raise ValidationError(f"File size exceeds maximum allowed size of {settings.max_file_size_mb}MB")
        
        # Validate content type
        if not content_type.startswith('image/'):
            raise ValidationError("Only image files are allowed")
        
        # Generate unique file path
        file_extension = os.path.splitext(filename)[1]
        unique_filename = f"{uuid4()}{file_extension}"
        file_path = f"{user_id}/{unique_filename}"
        
        return {
            "bucket": "uploads",
            "file_path": file_path,
            "upload_url": f"{settings.supabase_url}/storage/v1/object/uploads/{file_path}",
            "headers": {
                "Authorization": f"Bearer {settings.supabase_anon_key}",
                "Content-Type": content_type
            },
            "method": "POST"
        }
    
    @staticmethod
    def get_download_url(file_path: str, expires_in: int = 3600) -> Optional[str]:
        """Get signed download URL for uploaded file."""
        return supabase_client.get_download_url("uploads", file_path, expires_in)
    
    @staticmethod
    def get_public_url(bucket: str, file_path: str) -> str:
        """Get public URL for file in Supabase Storage."""
        return f"{settings.supabase_url}/storage/v1/object/public/{bucket}/{file_path}"


class JobService:
    """Job processing service using Supabase with per-request authentication."""
    
    # Define credit costs for different job types
    CREDIT_COSTS = {
        "face_swap": 2,
        "face_restore": 1,
        "upscale": 1
    }
    
    @staticmethod
    def create_job(user: SupabaseUser, job_data: Dict[str, Any], user_jwt: str) -> Optional[Dict[str, Any]]:
        """Create a new AI processing job with user-scoped authentication."""
        try:
            # Get credit cost for job type
            credits_required = JobService.CREDIT_COSTS.get(job_data.get("job_type"), 1)
            
            # Validate and debit credits atomically using service client
            # (RPC functions are SECURITY DEFINER and validate auth.uid() internally)
            service_cli = service_client()
            has_sufficient_credits = service_cli.rpc("validate_and_debit_credits", {
                "target_user_id": user.id,
                "credit_amount": credits_required,
                "job_ref_id": None  # Will be updated after job creation
            }).execute()
            
            if not has_sufficient_credits.data:
                from apps.core.exceptions import InsufficientCreditsError
                raise InsufficientCreditsError(credits_required, 0)
            
            # Prepare job data
            job_payload = {
                "user_id": user.id,
                "job_type": job_data.get("job_type"),
                "input_image_url": job_data.get("input_image_url"),
                "target_image_url": job_data.get("target_image_url"),
                "parameters": job_data.get("parameters", {}),
                "status": "pending",
                "progress": 0.0
            }
            
            # Create job record using user client (RLS enforced)
            user_cli = user_client(user_jwt)
            response = user_cli.table("jobs").insert(job_payload).execute()
            
            if not response.data:
                # Refund credits if job creation failed
                service_cli.rpc("increment_credits", {
                    "target_user_id": user.id,
                    "credit_amount": credits_required
                }).execute()
                raise ValidationError("Failed to create job")
            
            job = response.data[0]
            logger.info(f"Job created successfully: {job['id']} for user {user.id}")
            return job
            
        except Exception as e:
            logger.error(f"Failed to create job for user {user.id}: {e}")
            raise
    
    @staticmethod
    def get_job(job_id: str, user_jwt: str) -> Optional[Dict[str, Any]]:
        """Get job by ID using user authentication (RLS enforced)."""
        try:
            user_cli = user_client(user_jwt)
            response = user_cli.table("jobs").select("*").eq("id", job_id).single().execute()
            return response.data if response.data else None
        except Exception as e:
            logger.error(f"Failed to get job {job_id}: {e}")
            return None
    
    @staticmethod
    def get_user_jobs(user_jwt: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Get user's jobs with pagination using user authentication (RLS enforced)."""
        try:
            user_cli = user_client(user_jwt)
            response = (user_cli.table("jobs")
                       .select("*")
                       .order("created_at", desc=True)
                       .range(offset, offset + limit - 1)
                       .execute())
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to get user jobs: {e}")
            return []
    
    @staticmethod
    def update_job_status(
        job_id: str, 
        status: str, 
        user_jwt: str = None,
        progress: float = None, 
        result_url: str = None, 
        error_message: str = None
    ) -> Optional[Dict[str, Any]]:
        """Update job status and progress.
        
        If user_jwt is provided, uses user client (for user updates).
        Otherwise uses service client (for system updates).
        """
        updates = {"status": status}
        
        if progress is not None:
            updates["progress"] = progress
        if result_url:
            updates["result_image_url"] = result_url
        if error_message:
            updates["error_message"] = error_message
        if status in ["completed", "failed"]:
            updates["completed_at"] = datetime.utcnow().isoformat()
        if status == "processing" and not updates.get("started_at"):
            updates["started_at"] = datetime.utcnow().isoformat()
        
        try:
            if user_jwt:
                # User-initiated update (RLS enforced)
                client = user_client(user_jwt)
            else:
                # System update (service role)
                client = service_client()
            
            response = client.table("jobs").update(updates).eq("id", job_id).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to update job {job_id}: {e}")
            return None


class CreditService:
    """Credit management service using Supabase with proper authentication."""
    
    @staticmethod
    def get_credit_transactions(user_jwt: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get credit transactions for a user using user authentication (RLS enforced)."""
        try:
            user_cli = user_client(user_jwt)
            response = (user_cli.table("credit_transactions")
                       .select("*")
                       .order("created_at", desc=True)
                       .limit(limit)
                       .execute())
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to get credit transactions: {e}")
            return []
    
    @staticmethod
    def add_credits(user_id: str, amount: int, transaction_type: str = "credit", metadata: Dict[str, Any] = None) -> bool:
        """Add credits to user account using service role (admin operation)."""
        try:
            service_cli = service_client()
            response = service_cli.rpc("increment_credits", {
                "target_user_id": user_id,
                "credit_amount": amount
            }).execute()
            
            success = response.data if response.data is not None else False
            
            if success and metadata:
                # Create additional transaction record with metadata
                transaction_data = {
                    "user_id": user_id,
                    "amount": amount,
                    "transaction_type": transaction_type,
                    "metadata": metadata or {}
                }
                service_cli.table("credit_transactions").insert(transaction_data).execute()
            
            return success
        except Exception as e:
            logger.error(f"Failed to add credits for user {user_id}: {e}")
            return False
    
    @staticmethod
    def get_user_credits(user_jwt: str) -> int:
        """Get current user credit balance using user authentication (RLS enforced)."""
        try:
            user_cli = user_client(user_jwt)
            response = user_cli.table("profiles").select("credits").single().execute()
            return response.data.get("credits", 0) if response.data else 0
        except Exception as e:
            logger.error(f"Failed to get user credits: {e}")
            return 0