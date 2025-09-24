"""
S3 upload service for handling file uploads.
"""
import boto3
from botocore.exceptions import ClientError
from uuid import uuid4
import os
from apps.core.settings import settings
from apps.core.exceptions import ValidationError


class UploadService:
    """S3 upload service for handling file uploads."""
    
    def __init__(self):
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.s3_key,
            aws_secret_access_key=settings.s3_secret,
            region_name=settings.s3_region
        )
    
    def generate_presigned_url(
        self, 
        filename: str, 
        content_type: str, 
        file_size: int,
        expires_in: int = 3600
    ) -> dict:
        """Generate presigned URL for S3 upload."""
        # Validate file size
        max_size = settings.max_file_size_mb * 1024 * 1024  # Convert to bytes
        if file_size > max_size:
            raise ValidationError(f"File size exceeds maximum allowed size of {settings.max_file_size_mb}MB")
        
        # Validate content type
        if not content_type.startswith('image/'):
            raise ValidationError("Only image files are allowed")
        
        # Generate unique file key
        file_extension = os.path.splitext(filename)[1]
        unique_filename = f"{uuid4()}{file_extension}"
        file_key = f"uploads/{unique_filename}"
        
        try:
            # Generate presigned URL
            presigned_url = self.s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': settings.s3_bucket,
                    'Key': file_key,
                    'ContentType': content_type
                },
                ExpiresIn=expires_in
            )
            
            return {
                "presigned_url": presigned_url,
                "upload_id": str(uuid4()),
                "file_key": file_key,
                "expires_in": expires_in
            }
            
        except ClientError as e:
            raise ValidationError(f"Failed to generate upload URL: {str(e)}")
    
    def get_file_url(self, file_key: str) -> str:
        """Get public URL for uploaded file."""
        return f"https://{settings.s3_bucket}.s3.{settings.s3_region}.amazonaws.com/{file_key}"