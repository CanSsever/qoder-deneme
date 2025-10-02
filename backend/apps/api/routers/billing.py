"""
Billing router for payment and subscription management.
Migrated to use Supabase with proper JWT authentication and RLS enforcement.
"""
import json
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
import aiohttp
from apps.core.security import get_current_active_user, SupabaseUser, require_token
from apps.core.supa_request import user_client, service_client
from apps.core.settings import settings
import structlog

router = APIRouter(prefix="/billing", tags=["billing"])
logger = structlog.get_logger(__name__)


@router.post("/validate")
async def validate_receipt(
    receipt_data: dict,
    current_user: SupabaseUser = Depends(get_current_active_user),
    token: str = Depends(require_token)
):
    """Validate Superwall receipt and add credits using Supabase."""
    try:
        # Use user client for RLS enforcement
        client = user_client(token)
        
        # Validate receipt structure
        required_fields = ["product_id", "transaction_id", "receipt_data"]
        for field in required_fields:
            if field not in receipt_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")
        
        # Check if transaction already processed
        existing = client.table("subscriptions").select("id").eq("transaction_id", receipt_data["transaction_id"]).execute()
        if existing.data:
            return {
                "valid": False,
                "credits_added": 0,
                "error_message": "Transaction already processed"
            }
        
        # Validate receipt with provider (placeholder)
        # In production, this would make actual API calls
        is_valid = True  # Simplified for now
        
        if not is_valid:
            return {
                "valid": False,
                "credits_added": 0,
                "error_message": "Invalid receipt"
            }
        
        # Determine credits based on product ID
        credits_map = {
            "credits_10": 10,
            "credits_50": 50,
            "credits_100": 100,
            "subscription_monthly": 100,
            "subscription_yearly": 1200
        }
        credits_to_add = credits_map.get(receipt_data["product_id"], 10)
        
        # Create subscription record
        subscription_data = {
            "user_id": current_user.id,
            "product_id": receipt_data["product_id"],
            "transaction_id": receipt_data["transaction_id"],
            "receipt_data": receipt_data["receipt_data"],
            "status": "active",
            "credits_included": credits_to_add,
            "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat()
        }
        
        subscription_result = client.table("subscriptions").insert(subscription_data).execute()
        
        if not subscription_result.data:
            raise HTTPException(status_code=500, detail="Failed to create subscription record")
        
        # Add credits using service client RPC
        service_cli = service_client()
        credit_result = service_cli.rpc("increment_credits", {
            "target_user_id": current_user.id,
            "credit_amount": credits_to_add
        }).execute()
        
        if not credit_result.data:
            # Roll back subscription if credit addition failed
            client.table("subscriptions").delete().eq("id", subscription_result.data[0]["id"]).execute()
            raise HTTPException(status_code=500, detail="Failed to add credits")
        
        return {
            "valid": True,
            "credits_added": credits_to_add,
            "subscription_status": "active",
            "expires_at": subscription_data["expires_at"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Receipt validation failed: {e}")
        raise HTTPException(status_code=500, detail="Validation error")


# Mock billing event models for development
class MockBillingEvent(BaseModel):
    """Mock billing event for development testing."""
    user_id: str
    product_id: str
    event_type: str = "subscription_start"  # subscription_start, subscription_end, subscription_update
    subscription_id: Optional[str] = None
    expires_at: Optional[str] = None  # ISO datetime string
    status: str = "active"


class MockBillingResponse(BaseModel):
    """Response from mock billing event."""
    success: bool
    event_id: str
    webhook_sent: bool
    webhook_response: Optional[Dict[str, Any]] = None
    message: str


@router.post("/mock_event")
async def create_mock_billing_event(
    event: MockBillingEvent,
    request: Request
):
    """
    Create mock billing event for development testing.
    
    This endpoint is only available in development mode and allows
    testing the webhook flow by generating fake Superwall events.
    
    Example usage:
    ```bash
    curl -X POST "http://localhost:8000/api/v1/billing/mock_event" \
         -H "Content-Type: application/json" \
         -d '{
           "user_id": "user_123",
           "product_id": "pro_monthly",
           "event_type": "subscription_start",
           "expires_at": "2024-02-15T12:00:00Z"
         }'
    ```
    """
    # Only allow in development or mock mode
    if not settings.is_development and settings.dev_billing_mode != "mock":
        raise HTTPException(
            status_code=403, 
            detail="Mock billing events only available in development mode"
        )
    
    # Validate user exists using service client
    service_cli = service_client()
    user_check = service_cli.table("profiles").select("id").eq("id", event.user_id).execute()
    if not user_check.data:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Generate event ID
    event_id = str(uuid.uuid4())
    
    # Set default expiration if not provided
    expires_at = event.expires_at
    if not expires_at and event.event_type in ["subscription_start", "subscription_update"]:
        # Default to 30 days from now
        expiry_date = datetime.utcnow() + timedelta(days=30)
        expires_at = expiry_date.isoformat() + "Z"
    
    # Create mock Superwall event payload
    webhook_payload = {
        "event": event.event_type,
        "event_id": event_id,
        "user_id": event.user_id,
        "product_id": event.product_id,
        "subscription_id": event.subscription_id or f"sub_{uuid.uuid4().hex[:8]}",
        "expires_at": expires_at,
        "status": event.status,
        "created_at": datetime.utcnow().isoformat() + "Z"
    }
    
    logger.info(
        "Creating mock billing event",
        user_id=event.user_id,
        product_id=event.product_id,
        event_type=event.event_type,
        event_id=event_id
    )
    
    # Send webhook to our own endpoint
    webhook_sent = False
    webhook_response = None
    
    try:
        # Get base URL from request
        base_url = str(request.url).replace(str(request.url.path), "")
        webhook_url = f"{base_url}/api/v1/webhooks/superwall"
        
        # Generate HMAC signature if secret is configured
        headers = {"Content-Type": "application/json"}
        payload_bytes = json.dumps(webhook_payload).encode('utf-8')
        
        if settings.superwall_signing_secret:
            import hmac
            import hashlib
            signature = hmac.new(
                settings.superwall_signing_secret.encode('utf-8'),
                payload_bytes,
                hashlib.sha256
            ).hexdigest()
            headers["X-Superwall-Signature"] = f"sha256={signature}"
        
        # Send webhook
        async with aiohttp.ClientSession() as client_session:
            async with client_session.post(
                webhook_url,
                data=payload_bytes,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                webhook_response = {
                    "status_code": response.status,
                    "response": await response.json() if response.content_type == "application/json" else await response.text()
                }
                webhook_sent = True
                
                logger.info(
                    "Mock webhook sent successfully",
                    event_id=event_id,
                    webhook_url=webhook_url,
                    status_code=response.status
                )
    
    except Exception as e:
        logger.error(
            "Failed to send mock webhook",
            event_id=event_id,
            error=str(e)
        )
        webhook_response = {"error": str(e)}
    
    return MockBillingResponse(
        success=True,
        event_id=event_id,
        webhook_sent=webhook_sent,
        webhook_response=webhook_response,
        message=f"Mock {event.event_type} event created and webhook {'sent' if webhook_sent else 'failed'}"
    )