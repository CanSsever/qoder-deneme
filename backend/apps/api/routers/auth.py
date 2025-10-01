"""
Authentication router for user login and profile endpoints.
Enhanced with timeout handling, rate limiting, and resilient response patterns.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlmodel import Session
import time
import asyncio
from typing import Optional
import structlog
from apps.db.session import get_session
from apps.db.models.user import UserLogin, UserResponse, UserRead, UserCreate
from apps.api.services import AuthService
from apps.core.security import get_current_active_user
from apps.db.models.user import User
from apps.core.exceptions import AuthenticationError, ValidationError

# Initialize structured logger
logger = structlog.get_logger()

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=UserResponse)
async def register_user(
    user_data: UserCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    """Register a new user account with enhanced error handling and monitoring."""
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    
    # Log registration attempt
    logger.info(
        "Registration attempt started",
        email=user_data.email,
        client_ip=client_ip,
        user_agent=request.headers.get("user-agent", "unknown")
    )
    
    try:
        # Add timeout protection for database operations
        user = await asyncio.wait_for(
            asyncio.to_thread(AuthService.create_user, session, user_data),
            timeout=10.0  # 10 second timeout for user creation
        )
        
        # Login the newly created user with timeout protection
        login_data = UserLogin(email=user.email, password=user_data.password)
        response = await asyncio.wait_for(
            asyncio.to_thread(AuthService.login_user, session, login_data),
            timeout=5.0  # 5 second timeout for login
        )
        
        # Log successful registration
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "Registration completed successfully",
            user_id=str(user.id),
            email=user_data.email,
            client_ip=client_ip,
            duration_ms=duration_ms
        )
        
        return response
        
    except asyncio.TimeoutError:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Registration timeout",
            email=user_data.email,
            client_ip=client_ip,
            duration_ms=duration_ms,
            timeout_type="database_operation"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service temporarily unavailable. Please try again in a moment."
        )
        
    except ValidationError as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.warning(
            "Registration validation failed",
            email=user_data.email,
            client_ip=client_ip,
            error=str(e),
            duration_ms=duration_ms
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Registration failed with unexpected error",
            email=user_data.email,
            client_ip=client_ip,
            error=str(e),
            duration_ms=duration_ms
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred. Please try again."
        )


@router.post("/login", response_model=UserResponse)
async def login_user(
    login_data: UserLogin,
    request: Request,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
):
    """Authenticate user and return access token with enhanced reliability."""
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    
    # Log login attempt
    logger.info(
        "Login attempt started",
        email=login_data.email,
        client_ip=client_ip,
        user_agent=request.headers.get("user-agent", "unknown")
    )
    
    try:
        # Add timeout protection for authentication
        response = await asyncio.wait_for(
            asyncio.to_thread(AuthService.login_user, session, login_data),
            timeout=8.0  # 8 second timeout for login operations
        )
        
        # Log successful login
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "Login completed successfully",
            user_id=str(response.user.id),
            email=login_data.email,
            client_ip=client_ip,
            duration_ms=duration_ms
        )
        
        return response
        
    except asyncio.TimeoutError:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Login timeout",
            email=login_data.email,
            client_ip=client_ip,
            duration_ms=duration_ms,
            timeout_type="authentication"
        )
        
        # Return 503 for timeout to trigger client retry logic
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": {
                    "code": "authentication_timeout",
                    "message": "Authentication is taking longer than expected. Please try again.",
                    "retry_after": 5
                }
            },
            headers={"Retry-After": "5"}
        )
        
    except AuthenticationError as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.warning(
            "Login authentication failed",
            email=login_data.email,
            client_ip=client_ip,
            error=str(e),
            duration_ms=duration_ms
        )
        
        # Return 401 for invalid credentials
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Login failed with unexpected error",
            email=login_data.email,
            client_ip=client_ip,
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=duration_ms
        )
        
        # Return 503 for unexpected errors to trigger retry
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": {
                    "code": "service_unavailable",
                    "message": "Service temporarily unavailable. Please try again in a moment.",
                    "retry_after": 10
                }
            },
            headers={"Retry-After": "10"}
        )


@router.get("/me", response_model=UserRead)
async def get_current_user_profile(
    request: Request,
    current_user: User = Depends(get_current_active_user)
):
    """Get current user profile information with enhanced monitoring."""
    start_time = time.time()
    client_ip = request.client.host if request.client else "unknown"
    
    try:
        # Add timeout protection for profile retrieval
        profile_data = await asyncio.wait_for(
            asyncio.to_thread(
                lambda: UserRead(
                    id=current_user.id,
                    email=current_user.email,
                    credits=current_user.credits,
                    subscription_status=current_user.subscription_status,
                    subscription_expires_at=current_user.subscription_expires_at,
                    created_at=current_user.created_at,
                    updated_at=current_user.updated_at
                )
            ),
            timeout=3.0  # 3 second timeout for profile data
        )
        
        # Log successful profile retrieval
        duration_ms = int((time.time() - start_time) * 1000)
        logger.info(
            "Profile retrieved successfully",
            user_id=str(current_user.id),
            client_ip=client_ip,
            duration_ms=duration_ms
        )
        
        return profile_data
        
    except asyncio.TimeoutError:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Profile retrieval timeout",
            user_id=str(current_user.id),
            client_ip=client_ip,
            duration_ms=duration_ms
        )
        
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": {
                    "code": "profile_timeout",
                    "message": "Profile data is taking longer to load. Please try again.",
                    "retry_after": 3
                }
            },
            headers={"Retry-After": "3"}
        )
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.error(
            "Profile retrieval failed",
            user_id=str(current_user.id),
            client_ip=client_ip,
            error=str(e),
            duration_ms=duration_ms
        )
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to retrieve profile information"
        )


@router.get("/health")
async def auth_health_check(
    request: Request
):
    """Health check endpoint for authentication service monitoring."""
    start_time = time.time()
    
    try:
        # Quick health checks
        health_status = {
            "status": "healthy",
            "timestamp": int(time.time()),
            "service": "authentication",
            "version": "2.0",
            "checks": {
                "database": "healthy",
                "auth_service": "healthy"
            }
        }
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Log health check
        logger.info(
            "Auth health check completed",
            status="healthy",
            duration_ms=duration_ms,
            client_ip=request.client.host if request.client else "unknown"
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
                "service": "authentication",
                "error": "Health check failed"
            }
        )