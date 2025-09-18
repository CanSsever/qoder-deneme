"""
Billing router for payment and subscription management.
"""
from fastapi import APIRouter, Depends
from sqlmodel import Session
from apps.db.session import get_session
from apps.db.models.subscription import ReceiptValidation, ReceiptValidationResponse
from apps.db.models.user import User
from apps.api.services import BillingService
from apps.core.security import get_current_active_user

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/validate", response_model=ReceiptValidationResponse)
async def validate_receipt(
    receipt_data: ReceiptValidation,
    current_user: User = Depends(get_current_active_user),
    session: Session = Depends(get_session)
):
    """Validate Superwall receipt and add credits."""
    return BillingService.validate_receipt(session, current_user, receipt_data)