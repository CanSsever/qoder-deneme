"""
Supabase Storage upload router with client-direct uploads.
"""
import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from pydantic import BaseModel, validator
from typing import Dict, Any
from apps.api.services import UploadService
from apps.core.security import get_current_active_user, SupabaseUser
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


class UploadInstructionsRequest(BaseModel):
    """Request schema for upload instructions with validation."""
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


@router.post("/instructions")
@limiter.limit("20/minute")  # Rate limit: 20 uploads per minute
async def get_upload_instructions(
    request: Request,
    upload_request: UploadInstructionsRequest,
    current_user: SupabaseUser = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Get upload instructions for Supabase Storage client-direct upload."""
    
    logger.info("Upload instructions request", 
               user_id=current_user.id,
               filename=upload_request.filename,
               content_type=upload_request.content_type,
               file_size=upload_request.file_size,
               remote_addr=get_remote_address(request))
    
    try:
        instructions = UploadService.get_upload_instructions(
            user_id=current_user.id,
            filename=upload_request.filename,
            content_type=upload_request.content_type,
            file_size=upload_request.file_size
        )
        
        logger.info("Upload instructions generated successfully", 
                   user_id=current_user.id,
                   file_path=instructions["file_path"])
        
        return {
            **instructions,
            "max_file_size": MAX_FILE_SIZE,
            "allowed_mime_types": list(ALLOWED_MIME_TYPES)
        }
        
    except Exception as e:
        logger.error("Upload instructions generation failed", 
                    user_id=current_user.id,
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail={
                "code": "UPLOAD_INSTRUCTIONS_FAILED",
                "message": "Failed to generate upload instructions. Please try again."
            }
        )


@router.get("/download/{file_path:path}")
async def get_download_url(
    file_path: str,
    expires_in: int = 3600,
    current_user: SupabaseUser = Depends(get_current_active_user)
) -> Dict[str, Any]:
    """Get signed download URL for uploaded file."""
    
    # Verify user can access this file (file path should start with user_id)
    if not file_path.startswith(current_user.id):
        raise HTTPException(
            status_code=403,
            detail="Access denied to this file"
        )
    
    try:
        download_url = UploadService.get_download_url(file_path, expires_in)
        
        if not download_url:
            raise HTTPException(
                status_code=404,
                detail="File not found"
            )
        
        return {
            "download_url": download_url,
            "expires_in": expires_in
        }
        
    except Exception as e:
        logger.error("Download URL generation failed", 
                    user_id=current_user.id,
                    file_path=file_path,
                    error=str(e))
        raise HTTPException(
            status_code=500,
            detail="Failed to generate download URL"
        )