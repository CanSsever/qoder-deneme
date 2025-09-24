"""
Billing service for receipt validation and credit management.
"""
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID
from sqlmodel import Session
from apps.db.models.subscription import Subscription, ReceiptValidationResponse
from apps.db.models.user import User
from apps.core.config import SubscriptionStatus
from apps.api.services.auth import AuthService
import json
import requests


class BillingService:
    """Billing service for receipt validation and credit management."""
    
    @staticmethod
    def validate_receipt(session: Session, user: User, receipt_data: 'ReceiptValidation') -> ReceiptValidationResponse:
        """Validate Superwall receipt and add credits."""
        try:
            # Check if transaction already processed
            existing_subscription = session.query(Subscription).filter(
                Subscription.transaction_id == receipt_data.transaction_id
            ).first()
            
            if existing_subscription:
                return ReceiptValidationResponse(
                    valid=False,
                    credits_added=0,
                    subscription_status=user.subscription_status,
                    error_message="Transaction already processed"
                )
            
            # Validate receipt with Superwall/Apple/Google (simplified)
            # In production, this would make actual API calls to validate receipts
            is_valid = BillingService._validate_receipt_with_provider(receipt_data)
            
            if not is_valid:
                return ReceiptValidationResponse(
                    valid=False,
                    credits_added=0,
                    subscription_status=user.subscription_status,
                    error_message="Invalid receipt"
                )
            
            # Determine credits based on product ID
            credits_to_add = BillingService._get_credits_for_product(receipt_data.product_id)
            subscription_expires_at = datetime.utcnow() + timedelta(days=30)  # Default 30 days
            
            # Create subscription record
            subscription = Subscription(
                user_id=user.id,
                product_id=receipt_data.product_id,
                transaction_id=receipt_data.transaction_id,
                receipt_data=receipt_data.receipt_data,
                status=SubscriptionStatus.ACTIVE,
                credits_included=credits_to_add,
                expires_at=subscription_expires_at
            )
            
            session.add(subscription)
            
            # Add credits to user
            AuthService.update_user_credits(
                session,
                user.id,
                credits_to_add,
                "purchase",
                receipt_data.transaction_id
            )
            
            # Update user subscription status
            user.subscription_status = SubscriptionStatus.ACTIVE
            user.subscription_expires_at = subscription_expires_at
            user.updated_at = datetime.utcnow()
            session.add(user)
            
            session.commit()
            
            return ReceiptValidationResponse(
                valid=True,
                credits_added=credits_to_add,
                subscription_status=SubscriptionStatus.ACTIVE,
                expires_at=subscription_expires_at
            )
            
        except Exception as e:
            session.rollback()
            return ReceiptValidationResponse(
                valid=False,
                credits_added=0,
                subscription_status=user.subscription_status,
                error_message=f"Validation error: {str(e)}"
            )
    
    @staticmethod
    def _validate_receipt_with_provider(receipt_data: 'ReceiptValidation') -> bool:
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