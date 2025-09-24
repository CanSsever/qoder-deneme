"""
Advanced upload router with comprehensive validation and monitoring.
"""
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import SQLModel
from slowapi import Limiter
from slowapi.util import get_remote_address
from pydantic import validator
from apps.api.services.uploads import UploadService
from apps.core.security import get_current_active_user
from apps.db.models.user import User
from apps.core.settings import settings

logger = structlog.get_logger()
limiter = Limiter(key_func=get_remote_address)

router = APIRouter(prefix="/uploads", tags=["uploads"])

# Allowed MIME types
ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/jpg", 
    "image/png",
    "image/webp"
}

# Maximum file size (20MB)
MAX_FILE_SIZE = 20 * 1024 * 1024


class PresignRequest(SQLModel):
    """Advanced request schema for presigned URL generation with validation."""
    filename: str
    content_type: str
    file_size: int
    
    @validator('filename')
    def validate_filename(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("Filename cannot be empty")
        
        # Check for valid image extensions
        valid_extensions = ('.jpg', '.jpeg', '.png', '.webp')
        if not v.lower().endswith(valid_extensions):
            raise ValueError(f"Invalid file extension. Allowed: {valid_extensions}")
        
        # Prevent path traversal
        if '../' in v or '..\\' in v:
            raise ValueError("Invalid filename - path traversal detected")
        
        return v.strip()
    
    @validator('content_type')
    def validate_content_type(cls, v):
        if v not in ALLOWED_MIME_TYPES:
            raise ValueError(f"Invalid content type. Allowed: {ALLOWED_MIME_TYPES}")
        return v
    
    @validator('file_size')
    def validate_file_size(cls, v):
        if v <= 0:
            raise ValueError("File size must be greater than 0")
        if v > MAX_FILE_SIZE:
            raise ValueError(f"File size exceeds maximum allowed size of {MAX_FILE_SIZE // (1024*1024)}MB")
        return v


class PresignResponse(SQLModel):
    """Response schema for presigned URL."""
    presigned_url: str
    upload_id: str
    expires_in: int
    max_file_size: int
    allowed_mime_types: list


@router.post("/presign", response_model=PresignResponse)
@limiter.limit("20/minute")  # Rate limit: 20 uploads per minute
async def generate_presigned_url(
    request: Request,
    upload_request: PresignRequest,
    current_user: User = Depends(get_current_active_user)
):
    """Generate S3 presigned URL for image upload with comprehensive validation."""
    
    logger.info("Presigned URL request", 
               user_id=str(current_user.id),
               filename=upload_request.filename,
               content_type=upload_request.content_type,
               file_size=upload_request.file_size,
               remote_addr=get_remote_address(request))
    
    try:
        upload_service = UploadService()
        result = upload_service.generate_presigned_url(
            filename=upload_request.filename,
            content_type=upload_request.content_type,
            file_size=upload_request.file_size
        )
        
        logger.info("Presigned URL generated successfully", 
                   user_id=str(current_user.id),
                   upload_id=result["upload_id"])
        
        return PresignResponse(
            presigned_url=result["presigned_url"],
            upload_id=result["upload_id"],
            expires_in=result["expires_in"],
            max_file_size=MAX_FILE_SIZE,
            allowed_mime_types=list(ALLOWED_MIME_TYPES)
        )
        
    except Exception as e:
        logger.error("Presigned URL generation failed", 
                    user_id=str(current_user.id),
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "code": "UPLOAD_URL_GENERATION_FAILED",
                "message": "Failed to generate upload URL. Please try again."
            }
        )