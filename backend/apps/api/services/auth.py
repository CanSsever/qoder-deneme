"""
Authentication service for user management using Supabase.
Migrated from SQLModel to use Supabase authentication and RLS enforcement.
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import UUID
import structlog
from apps.core.security import SecurityUtils, SupabaseUser
from apps.core.exceptions import AuthenticationError, NotFoundError, ValidationError
from apps.core.settings import settings
from apps.core.supa_request import user_client, service_client


logger = structlog.get_logger(__name__)


class AuthService:
    """Authentication service for user management using Supabase."""
    
    @staticmethod
    def create_user(user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new user using Supabase Auth."""
        try:
            # Use service client for user creation (admin operation)
            service_cli = service_client()
            
            # Create user in Supabase Auth
            auth_response = service_cli.auth.admin.create_user({
                "email": user_data["email"],
                "password": user_data["password"],
                "email_confirm": True  # Auto-confirm for now
            })
            
            if not auth_response.user:
                raise ValidationError("Failed to create user")
            
            user_id = auth_response.user.id
            
            # Create profile using RPC function
            profile_response = service_cli.rpc(
                "bootstrap_user_profile",
                {
                    "user_id": user_id,
                    "user_email": user_data["email"],
                    "initial_credits": settings.default_credits
                }
            ).execute()
            
            if not profile_response.data:
                # If profile creation fails, clean up auth user
                service_cli.auth.admin.delete_user(user_id)
                raise ValidationError("Failed to create user profile")
            
            logger.info(
                "User created successfully",
                user_id=user_id,
                email=user_data["email"]
            )
            
            return {
                "id": user_id,
                "email": user_data["email"],
                "credits": settings.default_credits
            }
            
        except Exception as e:
            logger.error(f"Failed to create user: {e}")
            if "email" in str(e).lower() and "already" in str(e).lower():
                raise ValidationError("Email already registered")
            raise ValidationError(f"User creation failed: {str(e)}")
    
    @staticmethod
    def authenticate_user(email: str, password: str) -> Optional[Dict[str, Any]]:
        """Authenticate user with email and password using Supabase Auth."""
        try:
            service_cli = service_client()
            
            # Sign in with Supabase Auth
            auth_response = service_cli.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if not auth_response.user or not auth_response.session:
                return None
            
            # Get user profile
            profile_response = service_cli.table("profiles").select("*").eq("id", auth_response.user.id).execute()
            
            if not profile_response.data:
                logger.warning(f"User authenticated but no profile found: {auth_response.user.id}")
                return None
            
            profile = profile_response.data[0]
            
            return {
                "id": auth_response.user.id,
                "email": auth_response.user.email,
                "access_token": auth_response.session.access_token,
                "profile": profile
            }
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return None
    
    @staticmethod
    def login_user(login_data: Dict[str, str]) -> Dict[str, Any]:
        """Login user and return JWT token using Supabase Auth."""
        auth_result = AuthService.authenticate_user(
            login_data["email"], 
            login_data["password"]
        )
        
        if not auth_result:
            raise AuthenticationError("Invalid email or password")
        
        return {
            "access_token": auth_result["access_token"],
            "user": {
                "id": auth_result["id"],
                "email": auth_result["email"],
                "credits": auth_result["profile"].get("credits", 0)
            }
        }
    
    @staticmethod
    def get_user_by_id(user_jwt: str, user_id: str = None) -> Optional[Dict[str, Any]]:
        """Get user by ID using user-scoped client."""
        try:
            client = user_client(user_jwt)
            
            if user_id:
                # Admin operation - ensure current user has permission
                response = client.table("profiles").select("*").eq("id", user_id).execute()
            else:
                # Get current user's profile
                response = client.table("profiles").select("*").execute()
            
            return response.data[0] if response.data else None
            
        except Exception as e:
            logger.error(f"Failed to get user: {e}")
            return None
    
    @staticmethod
    def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
        """Get user by email using service client (admin operation)."""
        try:
            service_cli = service_client()
            response = service_cli.table("profiles").select("*").eq("email", email).execute()
            return response.data[0] if response.data else None
        except Exception as e:
            logger.error(f"Failed to get user by email: {e}")
            return None
    
    @staticmethod
    def update_user_credits(user_id: str, credits_change: int, transaction_type: str, reference_id: Optional[str] = None) -> bool:
        """Update user credits using service client RPC function."""
        try:
            service_cli = service_client()
            
            # Use RPC function for atomic credit update
            if credits_change > 0:
                response = service_cli.rpc("increment_credits", {
                    "target_user_id": user_id,
                    "credit_amount": credits_change
                }).execute()
            else:
                response = service_cli.rpc("decrement_credits", {
                    "target_user_id": user_id,
                    "credit_amount": abs(credits_change)
                }).execute()
            
            if response.data:
                # Create transaction record
                transaction_data = {
                    "user_id": user_id,
                    "amount": credits_change,
                    "transaction_type": transaction_type,
                    "reference_id": reference_id,
                    "metadata": {"reference_id": reference_id} if reference_id else {}
                }
                
                service_cli.table("credit_transactions").insert(transaction_data).execute()
                logger.info(f"Updated credits for user {user_id}: {credits_change}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to update user credits: {e}")
            return False