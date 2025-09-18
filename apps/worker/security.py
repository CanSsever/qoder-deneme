"""
Security and validation utilities for OneShot Face Swapper Backend.

This module provides comprehensive security features for file handling,
input validation, and content verification to ensure safe processing
of user-uploaded images and protect against malicious content.
"""

import asyncio
import hashlib
import magic
import mimetypes
import tempfile
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import aiofiles
import aiohttp
import structlog
from PIL import Image

from apps.core.exceptions import ValidationError

logger = structlog.get_logger(__name__)

# Magic byte signatures for common image formats
IMAGE_MAGIC_BYTES = {
    b'\xFF\xD8\xFF': 'image/jpeg',
    b'\x89PNG\r\n\x1a\n': 'image/png',
    b'GIF87a': 'image/gif',
    b'GIF89a': 'image/gif',
    b'RIFF': 'image/webp',  # WebP files start with RIFF
    b'BM': 'image/bmp',
    b'\x00\x00\x01\x00': 'image/x-icon',  # ICO
}

# Maximum file sizes by type (in bytes)
MAX_FILE_SIZES = {
    'image/jpeg': 20 * 1024 * 1024,  # 20MB for JPEG
    'image/png': 20 * 1024 * 1024,   # 20MB for PNG
    'image/webp': 15 * 1024 * 1024,  # 15MB for WebP
    'image/gif': 10 * 1024 * 1024,   # 10MB for GIF
    'image/bmp': 25 * 1024 * 1024,   # 25MB for BMP
}

# Allowed MIME types for image processing
ALLOWED_IMAGE_TYPES = [
    'image/jpeg',
    'image/png',
    'image/webp',
    'image/gif',
    'image/bmp',
]

# Minimum and maximum image dimensions (pixels)
MIN_IMAGE_SIZE = (64, 64)
MAX_IMAGE_SIZE = (8192, 8192)

# Suspicious patterns that might indicate malicious content
SUSPICIOUS_PATTERNS = [
    b'<?php',
    b'<script',
    b'javascript:',
    b'data:text/',
    b'<html',
    b'<svg',
    b'#!/bin/',
    b'%PDF',
]


class SecurityValidator:
    """
    Comprehensive security validator for image files and URLs.
    
    Provides validation for:
    - File size limits
    - MIME type validation
    - Magic byte verification
    - Image format validation
    - Malicious content detection
    - URL safety checks
    """
    
    def __init__(self, max_size_mb: int = 20):
        """
        Initialize security validator.
        
        Args:
            max_size_mb: Maximum file size in megabytes
        """
        self.max_size_bytes = max_size_mb * 1024 * 1024
        
    async def validate_image_url(self, url: str) -> Dict[str, any]:
        """
        Validate and download image from URL with security checks.
        
        Args:
            url: Image URL to validate and download
            
        Returns:
            Dict containing validation results and file info
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Validate URL format
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                raise ValidationError("Invalid URL format")
            
            if parsed_url.scheme not in ['http', 'https']:
                raise ValidationError("Only HTTP and HTTPS URLs are allowed")
            
            # Download with security headers and size limits
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=30),
                    headers={
                        'User-Agent': 'OneShot-FaceSwapper/2.0',
                        'Accept': 'image/*',
                    }
                ) as response:
                    # Check response status
                    if response.status != 200:
                        raise ValidationError(f"Failed to download image: HTTP {response.status}")
                    
                    # Check content type from headers
                    content_type = response.headers.get('content-type', '').lower()
                    if content_type and not content_type.startswith('image/'):
                        raise ValidationError(f"Invalid content type: {content_type}")
                    
                    # Check content length
                    content_length = response.headers.get('content-length')
                    if content_length and int(content_length) > self.max_size_bytes:
                        raise ValidationError(f"File too large: {content_length} bytes (max: {self.max_size_bytes})")
                    
                    # Read content with size limit
                    content = BytesIO()
                    downloaded_size = 0
                    
                    async for chunk in response.content.iter_chunked(8192):
                        downloaded_size += len(chunk)
                        if downloaded_size > self.max_size_bytes:
                            raise ValidationError(f"File too large: {downloaded_size} bytes (max: {self.max_size_bytes})")
                        content.write(chunk)
                    
                    content.seek(0)
                    content_bytes = content.getvalue()
                    
                    # Validate the downloaded content
                    validation_result = await self.validate_image_content(content_bytes, url)
                    
                    logger.info(
                        "Image URL validated successfully",
                        url=url,
                        file_size=len(content_bytes),
                        mime_type=validation_result['mime_type'],
                        dimensions=validation_result['dimensions']
                    )
                    
                    return {
                        **validation_result,
                        'content': content_bytes,
                        'url': url,
                        'file_size': len(content_bytes)
                    }
                    
        except aiohttp.ClientError as e:
            logger.error("Network error downloading image", url=url, error=str(e))
            raise ValidationError(f"Network error: {str(e)}")
        except asyncio.TimeoutError:
            logger.error("Timeout downloading image", url=url)
            raise ValidationError("Download timeout")
        except Exception as e:
            logger.error("Unexpected error validating image URL", url=url, error=str(e))
            raise ValidationError(f"Validation error: {str(e)}")
    
    async def validate_image_content(self, content: bytes, source: str = "unknown") -> Dict[str, any]:
        """
        Validate image content with comprehensive security checks.
        
        Args:
            content: Image file content as bytes
            source: Source identifier for logging
            
        Returns:
            Dict containing validation results
            
        Raises:
            ValidationError: If validation fails
        """
        try:
            # Check file size
            if len(content) > self.max_size_bytes:
                raise ValidationError(f"File too large: {len(content)} bytes (max: {self.max_size_bytes})")
            
            if len(content) < 100:  # Minimum viable image size
                raise ValidationError("File too small to be a valid image")
            
            # Magic byte validation
            mime_type = self._detect_mime_from_magic_bytes(content)
            if not mime_type:
                raise ValidationError("Unrecognized or invalid file format")
            
            if mime_type not in ALLOWED_IMAGE_TYPES:
                raise ValidationError(f"Unsupported image type: {mime_type}")
            
            # Check file size limits by type
            max_size_for_type = MAX_FILE_SIZES.get(mime_type, self.max_size_bytes)
            if len(content) > max_size_for_type:
                raise ValidationError(f"File too large for {mime_type}: {len(content)} bytes (max: {max_size_for_type})")
            
            # Malicious content detection
            self._check_suspicious_patterns(content)
            
            # Validate using libmagic (more thorough)
            try:
                detected_mime = magic.from_buffer(content, mime=True)
                if detected_mime not in ALLOWED_IMAGE_TYPES:
                    raise ValidationError(f"libmagic detected unsupported type: {detected_mime}")
            except Exception as e:
                logger.warning("libmagic validation failed, using magic bytes only", error=str(e))
            
            # Validate image structure with PIL
            dimensions, format_info = await self._validate_image_structure(content)
            
            # Generate content hash for deduplication
            content_hash = hashlib.sha256(content).hexdigest()
            
            result = {
                'mime_type': mime_type,
                'dimensions': dimensions,
                'format': format_info,
                'content_hash': content_hash,
                'file_size': len(content),
                'validation_passed': True
            }
            
            logger.info(
                "Image content validated successfully",
                source=source,
                **result
            )
            
            return result
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error("Unexpected error during content validation", source=source, error=str(e))
            raise ValidationError(f"Content validation failed: {str(e)}")
    
    def _detect_mime_from_magic_bytes(self, content: bytes) -> Optional[str]:
        """
        Detect MIME type from magic bytes at the beginning of the file.
        
        Args:
            content: File content bytes
            
        Returns:
            Detected MIME type or None if not recognized
        """
        for magic_bytes, mime_type in IMAGE_MAGIC_BYTES.items():
            if content.startswith(magic_bytes):
                return mime_type
        
        # Special case for WebP - check RIFF header more thoroughly
        if content.startswith(b'RIFF') and b'WEBP' in content[:20]:
            return 'image/webp'
        
        return None
    
    def _check_suspicious_patterns(self, content: bytes) -> None:
        """
        Check for suspicious patterns that might indicate malicious content.
        
        Args:
            content: File content to check
            
        Raises:
            ValidationError: If suspicious patterns are found
        """
        # Check first 1KB for suspicious patterns
        check_content = content[:1024].lower()
        
        for pattern in SUSPICIOUS_PATTERNS:
            if pattern in check_content:
                raise ValidationError(f"Suspicious content detected: potential security risk")
        
        # Check for embedded executables (PE header)
        if b'MZ' in content[:1024]:
            raise ValidationError("Executable content detected in image file")
        
        # Check for ZIP/archive signatures (could be polyglot files)
        if content.startswith(b'PK'):
            raise ValidationError("Archive content detected in image file")
    
    async def _validate_image_structure(self, content: bytes) -> Tuple[Tuple[int, int], str]:
        """
        Validate image structure using PIL and get dimensions.
        
        Args:
            content: Image content bytes
            
        Returns:
            Tuple of (dimensions, format_info)
            
        Raises:
            ValidationError: If image structure is invalid
        """
        try:
            with BytesIO(content) as image_buffer:
                with Image.open(image_buffer) as img:
                    # Verify the image can be loaded
                    img.verify()
                    
                    # Get dimensions
                    width, height = img.size
                    
                    # Check dimension limits
                    if width < MIN_IMAGE_SIZE[0] or height < MIN_IMAGE_SIZE[1]:
                        raise ValidationError(f"Image too small: {width}x{height} (min: {MIN_IMAGE_SIZE[0]}x{MIN_IMAGE_SIZE[1]})")
                    
                    if width > MAX_IMAGE_SIZE[0] or height > MAX_IMAGE_SIZE[1]:
                        raise ValidationError(f"Image too large: {width}x{height} (max: {MAX_IMAGE_SIZE[0]}x{MAX_IMAGE_SIZE[1]})")
                    
                    # Check aspect ratio (prevent extremely thin images)
                    aspect_ratio = max(width, height) / min(width, height)
                    if aspect_ratio > 10:
                        raise ValidationError(f"Extreme aspect ratio: {aspect_ratio:.2f} (max: 10)")
                    
                    return (width, height), img.format
                    
        except ValidationError:
            raise
        except Exception as e:
            raise ValidationError(f"Invalid image structure: {str(e)}")


class OutputSecurity:
    """
    Security utilities for output file generation and handling.
    """
    
    @staticmethod
    def generate_secure_filename(original_name: str, job_id: str, suffix: str = "") -> str:
        """
        Generate a secure filename for output files.
        
        Args:
            original_name: Original filename
            job_id: Job identifier
            suffix: Optional suffix
            
        Returns:
            Secure filename
        """
        # Extract extension safely
        original_path = Path(original_name)
        extension = original_path.suffix.lower() if original_path.suffix else '.png'
        
        # Ensure valid image extension
        if extension not in ['.png', '.jpg', '.jpeg', '.webp']:
            extension = '.png'
        
        # Create secure filename
        safe_name = f"output_{job_id}_{suffix}_{hashlib.md5(original_name.encode()).hexdigest()[:8]}{extension}"
        
        return safe_name
    
    @staticmethod
    async def save_output_securely(
        content: bytes, 
        output_path: str, 
        format_type: str = 'PNG',
        quality: int = 95
    ) -> Dict[str, any]:
        """
        Save output image with security and quality controls.
        
        Args:
            content: Image content bytes
            output_path: Output file path
            format_type: Output format (PNG, JPEG)
            quality: JPEG quality (ignored for PNG)
            
        Returns:
            Dict with save results
        """
        try:
            output_path_obj = Path(output_path)
            
            with BytesIO(content) as input_buffer:
                with Image.open(input_buffer) as img:
                    # Convert to RGB if saving as JPEG
                    if format_type.upper() == 'JPEG' and img.mode in ['RGBA', 'P']:
                        # Create white background for transparency
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                        img = background
                    
                    # Ensure output directory exists
                    output_path_obj.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Save with appropriate settings
                    save_kwargs = {'format': format_type.upper()}
                    if format_type.upper() == 'JPEG':
                        save_kwargs['quality'] = quality
                        save_kwargs['optimize'] = True
                    elif format_type.upper() == 'PNG':
                        save_kwargs['optimize'] = True
                        save_kwargs['compress_level'] = 6
                    
                    img.save(output_path_obj, **save_kwargs)
                    
                    file_size = output_path_obj.stat().st_size
                    
                    return {
                        'path': str(output_path_obj),
                        'format': format_type.upper(),
                        'size': file_size,
                        'dimensions': img.size
                    }
                    
        except Exception as e:
            logger.error("Failed to save output securely", path=str(output_path), error=str(e))
            raise ValidationError(f"Failed to save output: {str(e)}")


# Utility functions for easy import
async def validate_image_url(url: str, max_size_mb: int = 20) -> Dict[str, any]:
    """
    Convenience function to validate an image URL.
    
    Args:
        url: Image URL to validate
        max_size_mb: Maximum file size in MB
        
    Returns:
        Validation results dict
    """
    validator = SecurityValidator(max_size_mb)
    return await validator.validate_image_url(url)


async def validate_image_content(content: bytes, source: str = "unknown") -> Dict[str, any]:
    """
    Convenience function to validate image content.
    
    Args:
        content: Image content bytes
        source: Source identifier
        
    Returns:
        Validation results dict
    """
    validator = SecurityValidator()
    return await validator.validate_image_content(content, source)


def generate_secure_output_filename(original_name: str, job_id: str, suffix: str = "") -> str:
    """
    Convenience function to generate secure output filename.
    
    Args:
        original_name: Original filename
        job_id: Job identifier
        suffix: Optional suffix
        
    Returns:
        Secure filename
    """
    return OutputSecurity.generate_secure_filename(original_name, job_id, suffix)