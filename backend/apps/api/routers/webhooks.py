"""
Webhooks router for payment provider integrations.

Handles incoming webhooks from payment providers like Superwall,
with HMAC signature verification and idempotent event processing.
Migrated to use Supabase with proper RLS enforcement.
"""

import hashlib
import hmac
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from fastapi import APIRouter, Request, HTTPException, Depends, Header
import structlog

from apps.core.settings import settings
from apps.core.exceptions import ValidationError
from apps.core.supa_request import service_client
from apps.api.services.entitlements import EntitlementsService

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = structlog.get_logger(__name__)


def verify_superwall_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify Superwall webhook signature using HMAC-SHA256.
    
    Args:
        payload: Raw request body bytes
        signature: Signature from X-Superwall-Signature header
        secret: Superwall signing secret
        
    Returns:
        True if signature is valid, False otherwise
    """
    if not signature or not secret:
        return False
    
    try:
        # Remove any prefix from signature (like "sha256=")
        if "=" in signature:
            signature = signature.split("=", 1)[1]
        
        # Compute expected signature
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(signature, expected_signature)
        
    except Exception as e:
        logger.error("Failed to verify signature", error=str(e))
        return False


@router.post("/superwall")
async def superwall_webhook(
    request: Request,
    x_superwall_signature: Optional[str] = Header(None)
):
    """
    Handle Superwall webhook events.
    
    Processes subscription events from Superwall with HMAC signature verification
    and idempotent event handling to prevent duplicate processing.
    
    Expected Superwall event format:
    {
        "event": "subscription_start|subscription_end|subscription_update",
        "event_id": "unique_event_identifier",
        "user_id": "user_identifier", 
        "product_id": "product_identifier",
        "subscription_id": "subscription_identifier",
        "expires_at": "ISO_datetime_string",
        "status": "active|expired|cancelled",
        "created_at": "ISO_datetime_string"
    }
    """
    try:
        # Read raw payload for signature verification
        payload = await request.body()
        
        # Verify signature if not in development mode
        if not settings.is_development or settings.superwall_signing_secret:
            if not x_superwall_signature:
                logger.warning("Missing Superwall signature header")
                raise HTTPException(status_code=400, detail="Missing signature header")
            
            if not verify_superwall_signature(payload, x_superwall_signature, settings.superwall_signing_secret):
                logger.warning("Invalid Superwall signature", signature=x_superwall_signature[:20] + "...")
                raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parse JSON payload
        try:
            event_data = json.loads(payload.decode('utf-8'))
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON payload", error=str(e))
            raise HTTPException(status_code=400, detail="Invalid JSON payload")
        
        # Validate required fields
        required_fields = ["event", "event_id", "user_id", "product_id"]
        missing_fields = [field for field in required_fields if field not in event_data]
        if missing_fields:
            logger.error("Missing required fields", missing=missing_fields)
            raise HTTPException(status_code=400, detail=f"Missing required fields: {missing_fields}")
        
        event_type = event_data["event"]
        event_id = event_data["event_id"]
        user_id = event_data["user_id"]
        
        logger.info(
            "Received Superwall webhook",
            event_type=event_type,
            event_id=event_id,
            user_id=user_id,
            product_id=event_data.get("product_id")
        )
        
        # Check for idempotency - has this event been processed already?
        service_cli = service_client()
        existing_subscription = service_cli.table("subscriptions").select("id").eq("event_id", event_id).execute()
        
        if existing_subscription.data:
            logger.info(
                "Event already processed (idempotent)",
                event_id=event_id,
                existing_subscription_id=existing_subscription.data[0]["id"]
            )
            return {
                "status": "success",
                "message": "Event already processed",
                "subscription_id": existing_subscription.data[0]["id"]
            }
        
        # Validate that user exists
        user_check = service_cli.table("profiles").select("id").eq("id", user_id).execute()
        if not user_check.data:
            logger.error("User not found", user_id=user_id)
            raise HTTPException(status_code=404, detail="User not found")
        
        # Process the event based on type
        result = await process_superwall_event(event_data)
        
        return {
            "status": "success",
            "message": "Event processed successfully",
            **result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to process Superwall webhook", error=str(e))
        raise HTTPException(status_code=500, detail="Internal server error")


async def process_superwall_event(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """    
    Process Superwall event and update subscription/entitlements.
    
    Args:
        event_data: Parsed webhook event data
        
    Returns:
        Dictionary with processing results
    """
    event_type = event_data["event"]
    event_id = event_data["event_id"]
    user_id = event_data["user_id"]
    product_id = event_data["product_id"]
    
    # Parse dates
    expires_at = None
    if "expires_at" in event_data and event_data["expires_at"]:
        try:
            expires_at = datetime.fromisoformat(event_data["expires_at"].replace("Z", "+00:00"))
        except (ValueError, AttributeError) as e:
            logger.warning("Failed to parse expires_at", expires_at=event_data.get("expires_at"), error=str(e))
    
    # Map product_id to plan_code
    plan_code = map_product_to_plan(product_id)
    
    # Create subscription record using service client
    service_cli = service_client()
    subscription_data = {
        "user_id": user_id,
        "product_id": product_id,
        "status": event_data.get("status", "active"),
        "expires_at": expires_at.isoformat() if expires_at else None,
        "event_id": event_id,
        "raw_payload_json": json.dumps(event_data),
        "provider": "superwall",
        "provider_subscription_id": event_data.get("subscription_id")
    }
    
    subscription_result = service_cli.table("subscriptions").insert(subscription_data).execute()
    
    if not subscription_result.data:
        raise HTTPException(status_code=500, detail="Failed to create subscription record")
    
    subscription = subscription_result.data[0]
    
    # Process based on event type
    if event_type in ["subscription_start", "subscription_update"]:
        result = await handle_subscription_activation(user_id, plan_code, subscription, expires_at)
    elif event_type == "subscription_end":
        result = await handle_subscription_deactivation(user_id, subscription)
    else:
        logger.warning("Unknown event type", event_type=event_type)
        result = {"action": "logged", "note": f"Unknown event type: {event_type}"}
    
    logger.info(
        "Processed Superwall event",
        event_type=event_type,
        event_id=event_id,
        user_id=user_id,
        subscription_id=subscription.id,
        result=result
    )
    
    return {"subscription_id": subscription["id"], **result}


async def handle_subscription_activation(
    user_id: str, 
    plan_code: str, 
    subscription: Dict[str, Any],
    expires_at: Optional[datetime]
) -> Dict[str, Any]:
    """    
    Handle subscription activation or update.
    
    Args:
        user_id: User identifier
        plan_code: Plan code (free, pro, premium)
        subscription: Subscription record
        expires_at: When subscription expires
        
    Returns:
        Dictionary with activation results
    """
    # Create new entitlement using Supabase
    effective_from = datetime.utcnow()
    effective_to = expires_at if expires_at else None
    
    service_cli = service_client()
    
    # End current entitlements for user
    if effective_to:
        service_cli.table("user_entitlements").update({
            "effective_to": effective_from.isoformat()
        }).eq("user_id", user_id).is_("effective_to", "null").execute()
    
    # Get plan template for limits
    plan_templates = {
        "free": {"limits": {"daily_jobs": 3, "concurrent_jobs": 1, "max_side": 512, "features": ["face_restore"]}},
        "pro": {"limits": {"daily_jobs": 50, "concurrent_jobs": 3, "max_side": 1024, "features": ["face_restore", "face_swap"]}},
        "premium": {"limits": {"daily_jobs": 200, "concurrent_jobs": 5, "max_side": 2048, "features": ["face_restore", "face_swap", "upscale"]}}
    }
    
    limits = plan_templates.get(plan_code, plan_templates["free"])["limits"]
    
    entitlement_data = {
        "user_id": user_id,
        "plan_code": plan_code,
        "limits_json": json.dumps(limits),
        "effective_from": effective_from.isoformat(),
        "effective_to": effective_to.isoformat() if effective_to else None
    }
    
    entitlement_result = service_cli.table("user_entitlements").insert(entitlement_data).execute()
    
    if not entitlement_result.data:
        raise HTTPException(status_code=500, detail="Failed to create entitlement")
    
    entitlement = entitlement_result.data[0]
        
    logger.info(
        "Activated subscription",
        user_id=user_id,
        plan_code=plan_code,
        entitlement_id=entitlement["id"],
        daily_jobs=limits.get("daily_jobs"),
        features=limits.get("features")
    )
    
    return {
        "action": "activated",
        "plan_code": plan_code,
        "entitlement_id": entitlement["id"],
        "limits": limits
    }


async def handle_subscription_deactivation(
    user_id: str, 
    subscription: Dict[str, Any]
) -> Dict[str, Any]:
    """    
    Handle subscription deactivation/cancellation.
    
    Args:
        user_id: User identifier
        subscription: Subscription record
        
    Returns:
        Dictionary with deactivation results
    """
    service_cli = service_client()
    
    # End current entitlements
    now = datetime.utcnow()
    service_cli.table("user_entitlements").update({
        "effective_to": now.isoformat()
    }).eq("user_id", user_id).is_("effective_to", "null").execute()
    
    # Create free plan entitlement
    default_plan = settings.entitlements_default_plan or "free"
    limits = {"daily_jobs": 3, "concurrent_jobs": 1, "max_side": 512, "features": ["face_restore"]}
    
    entitlement_data = {
        "user_id": user_id,
        "plan_code": default_plan,
        "limits_json": json.dumps(limits),
        "effective_from": now.isoformat()
    }
    
    entitlement_result = service_cli.table("user_entitlements").insert(entitlement_data).execute()
    
    if not entitlement_result.data:
        raise HTTPException(status_code=500, detail="Failed to create default entitlement")
    
    entitlement = entitlement_result.data[0]
        
    logger.info(
        "Deactivated subscription",
        user_id=user_id,
        reverted_to_plan=default_plan,
        entitlement_id=entitlement["id"]
    )
    
    return {
        "action": "deactivated",
        "reverted_to_plan": default_plan,
        "entitlement_id": entitlement["id"]
    }


def map_product_to_plan(product_id: str) -> str:
    """
    Map Superwall product ID to internal plan code.
    
    Args:
        product_id: Product identifier from Superwall
        
    Returns:
        Internal plan code
    """
    # Define product mapping
    product_mapping = {
        # Example Superwall product IDs
        "pro_monthly": "pro",
        "pro_annual": "pro", 
        "premium_monthly": "premium",
        "premium_annual": "premium",
        "pro_weekly": "pro",
        "premium_weekly": "premium",
        # Add more mappings as needed
    }
    
    plan_code = product_mapping.get(product_id, "free")
    
    # Validate plan code exists
    plan_templates = {
        "free": True,
        "pro": True, 
        "premium": True
    }
    
    if plan_code not in plan_templates:
        logger.warning("Unknown plan code mapped from product", product_id=product_id, plan_code=plan_code)
        plan_code = settings.entitlements_default_plan or "free"
    
    return plan_code


# Health check endpoint for webhook monitoring
@router.get("/health")
async def webhook_health():
    """Health check for webhook endpoints."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "signature_verification": "enabled" if settings.superwall_signing_secret else "disabled"
    }