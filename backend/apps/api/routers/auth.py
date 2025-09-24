"""
Authentication router for user login and profile endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session
from apps.db.session import get_session
from apps.db.models.user import UserLogin, UserResponse, UserRead, UserCreate
from apps.api.services import AuthService
from apps.core.security import get_current_active_user
from apps.db.models.user import User

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=UserResponse)
async def register_user(
    user_data: UserCreate,
    session: Session = Depends(get_session)
):
    """Register a new user account."""
    user = AuthService.create_user(session, user_data)
    
    # Login the newly created user
    login_data = UserLogin(email=user.email, password=user_data.password)
    return AuthService.login_user(session, login_data)


@router.post("/login", response_model=UserResponse)
async def login_user(
    login_data: UserLogin,
    session: Session = Depends(get_session)
):
    """Authenticate user and return access token."""
    return AuthService.login_user(session, login_data)


@router.get("/me", response_model=UserRead)
async def get_current_user_profile(
    current_user: User = Depends(get_current_active_user)
):
    """Get current user profile information."""
    return UserRead(
        id=current_user.id,
        email=current_user.email,
        credits=current_user.credits,
        subscription_status=current_user.subscription_status,
        subscription_expires_at=current_user.subscription_expires_at,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at
    )