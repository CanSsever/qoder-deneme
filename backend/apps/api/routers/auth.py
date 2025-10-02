"""
Authentication router for Supabase-based user profile management.
Authentication is handled by Supabase Auth directly from the client.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any
import time
import structlog
from apps.api.services import ProfileService, CreditService
from apps.core.security import get_current_active_user, get_optional_user, SupabaseUser
from apps.core.exceptions import ValidationError

# Initialize structured logger
logger = structlog.get_logger()

router = APIRouter(tags=["authentication"])


@router.post("/bootstrap-profile")
async def bootstrap_profile(
    request: Request,
    current_user: SupabaseUser = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Bootstrap user profile after Supabase authentication.
    
    This endpoint should be called after a user successfully authenticates
    with Supabase to ensure their profile exists in our database.
    """
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    
    logger.info(
        "Profile bootstrap started",
        user_id=current_user.id,
        email=current_user.email,
        client_ip=client_ip
    )
    
    try:
        # Get or create profile
        profile = ProfileService.get_or_create_profile(current_user)
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user profile"
            )
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Profile bootstrap completed",
            user_id=current_user.id,
            email=current_user.email,
            client_ip=client_ip,
            duration_ms=duration_ms
        )
        
        return {
            "profile": profile,
            "message": "Profile ready"
        }
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.error(
            "Profile bootstrap failed",
            user_id=current_user.id,
            email=current_user.email,
            client_ip=client_ip,
            error=str(e),
            duration_ms=duration_ms
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to bootstrap user profile"
        )


@router.get("/profile")
async def get_current_user_profile(
    request: Request,
    current_user: SupabaseUser = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Get current user profile information."""
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    
    try:
        # Get profile from Supabase
        profile = ProfileService.get_profile(current_user.id)
        
        if not profile:
            # Try to bootstrap profile if it doesn't exist
            profile = ProfileService.get_or_create_profile(current_user)
        
        if not profile:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Profile not found"
            )
        
        # Get recent credit transactions
        credit_transactions = CreditService.get_credit_transactions(current_user.id, limit=10)
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Profile retrieved successfully",
            user_id=current_user.id,
            client_ip=client_ip,
            duration_ms=duration_ms
        )
        
        return {
            "profile": profile,
            "recent_transactions": credit_transactions
        }
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.error(
            "Profile retrieval failed",
            user_id=current_user.id,
            client_ip=client_ip,
            error=str(e),
            duration_ms=duration_ms
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve profile information"
        )


@router.get("/health")
async def auth_health_check(request: Request) -> Dict[str, Any]:
    """Health check endpoint for authentication service."""
    start_time = time.time()
    
    try:
        # Check Supabase connection
        from apps.core.supabase_client import supabase_client
        is_healthy = supabase_client.health_check()
        
        health_status = {
            "status": "healthy" if is_healthy else "unhealthy",
            "timestamp": int(time.time()),
            "service": "supabase_auth",
            "version": "2.0",
            "checks": {
                "supabase_connection": "healthy" if is_healthy else "unhealthy",
                "jwt_validation": "healthy"
            }
        }
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(
            "Auth health check completed",
            status="healthy" if is_healthy else "unhealthy",
            duration_ms=duration_ms,
            client_ip=request.client.host if request.client else "unknown"
        )
        
        if not is_healthy:
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content=health_status
            )
        
        return health_status
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.error(
            "Auth health check failed",
            error=str(e),
            duration_ms=duration_ms
        )
        
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "unhealthy",
                "timestamp": int(time.time()),
                "service": "supabase_auth",
                "error": "Health check failed"
            }
        )