"""
Billing service for receipt validation and credit management using Supabase.
Migrated from SQLModel to use Supabase authentication and RLS enforcement.
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import UUID
import structlog
from apps.core.exceptions import ValidationError
from apps.core.supa_request import user_client, service_client
from apps.core.settings import settings
import json
import requests


logger = structlog.get_logger(__name__)


class BillingService:
    """Billing service for receipt validation and credit management using Supabase."""
    
    @staticmethod
    def validate_receipt(user_jwt: str, user_id: str, receipt_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate Superwall receipt and add credits using Supabase."""
        try:
            # Use user client for RLS enforcement
            client = user_client(user_jwt)
            
            # Check if transaction already processed
            existing_subscription = client.table("subscriptions").select("id").eq(
                "transaction_id", receipt_data["transaction_id"]
            ).execute()
            
            if existing_subscription.data:
                return {
                    "valid": False,
                    "credits_added": 0,
                    "error_message": "Transaction already processed"
                }
            
            # Validate receipt with provider
            is_valid = BillingService._validate_receipt_with_provider(receipt_data)
            
            if not is_valid:
                return {
                    "valid": False,
                    "credits_added": 0,
                    "error_message": "Invalid receipt"
                }
            
            # Determine credits based on product ID
            credits_to_add = BillingService._get_credits_for_product(receipt_data["product_id"])
            subscription_expires_at = datetime.utcnow() + timedelta(days=30)
            
            # Create subscription record
            subscription_data = {
                "user_id": user_id,
                "product_id": receipt_data["product_id"],
                "transaction_id": receipt_data["transaction_id"],
                "receipt_data": receipt_data.get("receipt_data", ""),
                "status": "active",
                "credits_included": credits_to_add,
                "expires_at": subscription_expires_at.isoformat()
            }
            
            subscription_result = client.table("subscriptions").insert(subscription_data).execute()
            
            if not subscription_result.data:
                raise ValidationError("Failed to create subscription record")
            
            # Add credits using service client RPC
            service_cli = service_client()
            credit_result = service_cli.rpc("increment_credits", {
                "target_user_id": user_id,
                "credit_amount": credits_to_add
            }).execute()
            
            if not credit_result.data:
                # Roll back subscription if credit addition failed
                client.table("subscriptions").delete().eq("id", subscription_result.data[0]["id"]).execute()
                raise ValidationError("Failed to add credits")
            
            # Create credit transaction record
            transaction_data = {
                "user_id": user_id,
                "amount": credits_to_add,
                "transaction_type": "purchase",
                "reference_id": receipt_data["transaction_id"],
                "metadata": {"product_id": receipt_data["product_id"]}
            }
            
            service_cli.table("credit_transactions").insert(transaction_data).execute()
            
            logger.info(
                "Receipt validated and credits added",
                user_id=user_id,
                transaction_id=receipt_data["transaction_id"],
                credits_added=credits_to_add
            )
            
            return {
                "valid": True,
                "credits_added": credits_to_add,
                "subscription_status": "active",
                "expires_at": subscription_expires_at.isoformat()
            }
            
        except Exception as e:
            logger.error(f"Receipt validation failed: {e}")
            return {
                "valid": False,
                "credits_added": 0,
                "error_message": f"Validation error: {str(e)}"
            }
    
    @staticmethod
    def _validate_receipt_with_provider(receipt_data: Dict[str, Any]) -> bool:
        """Validate receipt with payment provider (placeholder implementation)."""
        # In production, this would make actual API calls to Apple/Google/Superwall
        # For now, return True for development
        return True
    
    @staticmethod
    def _get_credits_for_product(product_id: str) -> int:
        """Get credit amount based on product ID."""
        # Define product mappings
        product_credits = {
            "credits_10": 10,
            "credits_50": 50,
            "credits_100": 100,
            "subscription_monthly": 100,
            "subscription_yearly": 1200
        }
        return product_credits.get(product_id, 10)  # Default to 10 credits