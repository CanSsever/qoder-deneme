"""
Credits router for managing user credit transactions and balance.
"""
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from typing import Dict, Any, List
from apps.api.services import CreditService
from apps.core.security import get_current_active_user, get_raw_token, SupabaseUser

logger = structlog.get_logger()

router = APIRouter(prefix="/credits", tags=["credits"])


@router.get("")
async def get_credit_transactions(
    request: Request,
    limit: int = 50,
    current_user: SupabaseUser = Depends(get_current_active_user),
    user_token: str = Depends(get_raw_token)
) -> Dict[str, Any]:
    """Get user's credit transaction history."""
    
    try:
        transactions = CreditService.get_credit_transactions(user_token, limit)
        current_credits = CreditService.get_user_credits(user_token)
        
        return {
            "current_credits": current_credits,
            "transactions": transactions,
            "total_transactions": len(transactions)
        }
        
    except Exception as e:
        logger.error("Failed to get credit transactions", 
                    user_id=current_user.id,
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve credit information"
        )


@router.get("/balance")
async def get_credit_balance(
    current_user: SupabaseUser = Depends(get_current_active_user),
    user_token: str = Depends(get_raw_token)
) -> Dict[str, Any]:
    """Get user's current credit balance."""
    
    try:
        credits = CreditService.get_user_credits(user_token)
        
        return {
            "credits": credits,
            "user_id": current_user.id
        }
        
    except Exception as e:
        logger.error("Failed to get credit balance", 
                    user_id=current_user.id,
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve credit balance"
        )