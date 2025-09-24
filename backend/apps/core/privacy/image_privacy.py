"""
Image privacy service for EXIF/metadata stripping and secure processing.
"""
import os
import tempfile
import structlog
from typing import BinaryIO, Dict, Any, Tuple, Optional
from io import BytesIO
from PIL import Image, ExifTags
from PIL.ExifTags import TAGS, GPSTAGS

logger = structlog.get_logger(__name__)


class ImagePrivacyService:
    """Service for handling image privacy concerns including EXIF removal."""
    
    @staticmethod
    def strip_exif_metadata(image_data: bytes, preserve_orientation: bool = True) -> Tuple[bytes, Dict[str, Any]]:
        """
        Strip EXIF metadata from image while optionally preserving orientation.
        
        Args:
            image_data: Raw image bytes
            preserve_orientation: Whether to preserve image orientation
            
        Returns:
            Tuple of (cleaned_image_bytes, metadata_info)
        """
        try:
            # Load image
            with Image.open(BytesIO(image_data)) as img:
                # Extract metadata info before stripping
                metadata_info = ImagePrivacyService._extract_metadata_info(img)
                
                # Handle orientation if needed
                if preserve_orientation and hasattr(img, '_getexif'):
                    try:
                        # Apply EXIF orientation transformations
                        img = ImagePrivacyService._apply_orientation(img)
                    except Exception as e:
                        logger.warning("Failed to apply orientation", error=str(e))
                
                # Create new image without EXIF data
                if img.mode == 'RGBA':
                    # For transparent images, keep RGBA
                    clean_img = Image.new('RGBA', img.size)
                    clean_img.paste(img, (0, 0))
                else:
                    # Convert to RGB for JPEG output
                    clean_img = Image.new('RGB', img.size)
                    if img.mode == 'P':
                        img = img.convert('RGB')
                    clean_img.paste(img, (0, 0))
                
                # Save clean image to bytes
                output_buffer = BytesIO()
                
                # Determine format
                format_type = 'JPEG' if clean_img.mode == 'RGB' else 'PNG'
                
                # Save with high quality but no metadata
                save_kwargs = {'format': format_type}
                if format_type == 'JPEG':
                    save_kwargs['quality'] = 95
                    save_kwargs['optimize'] = True
                
                clean_img.save(output_buffer, **save_kwargs)
                
                logger.info("EXIF metadata stripped successfully", 
                           original_size=len(image_data),
                           cleaned_size=len(output_buffer.getvalue()),
                           format=format_type,
                           metadata_found=len(metadata_info) > 0)
                
                return output_buffer.getvalue(), metadata_info
                
        except Exception as e:
            logger.error("Failed to strip EXIF metadata", error=str(e))
            # Return original data if processing fails
            return image_data, {}
    
    @staticmethod
    def _extract_metadata_info(img: Image.Image) -> Dict[str, Any]:
        """Extract metadata information for logging/audit purposes."""
        metadata_info = {}
        
        try:
            # Get EXIF data
            exifdata = img.getexif()
            if exifdata:
                for tag_id, value in exifdata.items():
                    tag = TAGS.get(tag_id, tag_id)
                    
                    # Log potentially sensitive metadata
                    if tag in ['GPS', 'GPSInfo']:
                        metadata_info['has_gps'] = True
                        # Don't store actual GPS data for privacy
                    elif tag in ['DateTime', 'DateTimeOriginal', 'DateTimeDigitized']:
                        metadata_info['has_timestamp'] = True
                    elif tag in ['Make', 'Model']:
                        metadata_info['has_device_info'] = True
                    elif tag in ['Software', 'ProcessingSoftware']:
                        metadata_info['has_software_info'] = True
                    elif tag == 'UserComment':
                        metadata_info['has_user_comment'] = True
                
                # Check for GPS data specifically
                gps_info = exifdata.get_ifd(0x8825)
                if gps_info:
                    metadata_info['gps_tags_count'] = len(gps_info)
                    
        except Exception as e:
            logger.warning("Failed to extract metadata info", error=str(e))
        
        return metadata_info
    
    @staticmethod
    def _apply_orientation(img: Image.Image) -> Image.Image:
        """Apply EXIF orientation to image."""
        try:
            exif = img._getexif()
            if exif is not None:
                orientation_key = None
                for key in ExifTags.TAGS.keys():
                    if ExifTags.TAGS[key] == 'Orientation':
                        orientation_key = key
                        break
                
                if orientation_key and orientation_key in exif:
                    orientation = exif[orientation_key]
                    
                    if orientation == 2:
                        img = img.transpose(Image.FLIP_LEFT_RIGHT)
                    elif orientation == 3:
                        img = img.rotate(180, expand=True)
                    elif orientation == 4:
                        img = img.rotate(180, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
                    elif orientation == 5:
                        img = img.rotate(-90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
                    elif orientation == 6:
                        img = img.rotate(-90, expand=True)
                    elif orientation == 7:
                        img = img.rotate(90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
                    elif orientation == 8:
                        img = img.rotate(90, expand=True)
                        
        except (AttributeError, KeyError, TypeError):
            # No EXIF orientation data or error reading it
            pass
        
        return img
    
    @staticmethod
    def process_upload_privacy(file_data: bytes, filename: str) -> Tuple[bytes, Dict[str, Any]]:
        """
        Process uploaded image for privacy compliance.
        
        Args:
            file_data: Raw image file data
            filename: Original filename
            
        Returns:
            Tuple of (processed_image_data, processing_info)
        """
        logger.info("Processing image for privacy compliance", filename=filename)
        
        processing_info = {
            "original_size": len(file_data),
            "filename": filename,
            "privacy_processed": True
        }
        
        try:
            # Strip EXIF metadata
            clean_data, metadata_info = ImagePrivacyService.strip_exif_metadata(file_data)
            
            processing_info.update({
                "cleaned_size": len(clean_data),
                "metadata_stripped": metadata_info,
                "size_reduction": len(file_data) - len(clean_data)
            })
            
            logger.info("Image privacy processing completed", 
                       original_size=len(file_data),
                       cleaned_size=len(clean_data),
                       metadata_found=bool(metadata_info))
            
            return clean_data, processing_info
            
        except Exception as e:
            logger.error("Image privacy processing failed", 
                        filename=filename, 
                        error=str(e))
            
            # Return original data if processing fails
            processing_info["privacy_processed"] = False
            processing_info["error"] = str(e)
            return file_data, processing_info
    
    @staticmethod
    def validate_image_safety(image_data: bytes) -> Dict[str, Any]:
        """
        Validate image for basic safety checks.
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            Dictionary with validation results
        """
        validation_result = {
            "valid": True,
            "issues": [],
            "metadata": {}
        }
        
        try:
            with Image.open(BytesIO(image_data)) as img:
                # Check image format
                if img.format not in ['JPEG', 'PNG', 'WEBP']:
                    validation_result["valid"] = False
                    validation_result["issues"].append("Unsupported image format")
                
                # Check dimensions
                width, height = img.size
                max_dimension = 8192  # 8K max
                if width > max_dimension or height > max_dimension:
                    validation_result["valid"] = False
                    validation_result["issues"].append(f"Image too large: {width}x{height}")
                
                validation_result["metadata"] = {
                    "format": img.format,
                    "mode": img.mode,
                    "size": img.size,
                    "has_transparency": img.mode in ['RGBA', 'LA', 'P']
                }
                
        except Exception as e:
            validation_result["valid"] = False
            validation_result["issues"].append(f"Image validation failed: {str(e)}")
        
        return validation_result