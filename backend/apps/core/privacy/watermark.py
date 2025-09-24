"""
Watermark service for applying plan-based watermarks to processed images.
"""
import os
import tempfile
import structlog
from typing import BinaryIO, Dict, Any, Tuple, Optional
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
from enum import Enum

logger = structlog.get_logger(__name__)


class WatermarkPosition(Enum):
    """Watermark position options."""
    BOTTOM_RIGHT = "bottom_right"
    BOTTOM_LEFT = "bottom_left"
    TOP_RIGHT = "top_right"
    TOP_LEFT = "top_left"
    CENTER = "center"


class WatermarkService:
    """Service for applying watermarks based on user subscription plans."""
    
    def __init__(self):
        """Initialize watermark service with default settings."""
        # Default watermark settings
        self.default_text = "oneshot.ai"
        self.default_opacity = 0.3
        self.default_position = WatermarkPosition.BOTTOM_RIGHT
        self.default_font_size_ratio = 0.03  # 3% of image width
        self.margin_ratio = 0.02  # 2% margin from edges
    
    def should_apply_watermark(self, user_plan: str, user_settings: Optional[Dict] = None) -> bool:
        """
        Determine if watermark should be applied based on user plan and settings.
        
        Args:
            user_plan: User's subscription plan (free, pro, premium)
            user_settings: Optional user watermark preferences
            
        Returns:
            Boolean indicating if watermark should be applied
        """
        # Default plan-based rules
        plan_defaults = {
            "free": True,      # Free users always get watermarks
            "pro": False,      # Pro users can disable watermarks
            "premium": False   # Premium users can disable watermarks
        }
        
        # Default behavior if plan not recognized
        if user_plan not in plan_defaults:
            logger.warning("Unknown user plan, applying watermark", plan=user_plan)
            return True
        
        # For paid plans, check user settings
        if user_plan in ["pro", "premium"] and user_settings:
            # Check if user explicitly disabled watermarks
            watermark_enabled = user_settings.get("watermark_enabled", False)
            return watermark_enabled
        
        # Use plan default
        return plan_defaults[user_plan]
    
    def apply_watermark(
        self, 
        image_data: bytes, 
        user_plan: str,
        user_settings: Optional[Dict] = None,
        custom_text: Optional[str] = None
    ) -> Tuple[bytes, Dict[str, Any]]:
        """
        Apply watermark to image based on user plan and preferences.
        
        Args:
            image_data: Raw image bytes
            user_plan: User's subscription plan
            user_settings: Optional user watermark preferences
            custom_text: Optional custom watermark text (premium feature)
            
        Returns:
            Tuple of (watermarked_image_bytes, watermark_info)
        """
        watermark_info = {
            "watermark_applied": False,
            "user_plan": user_plan,
            "reason": None
        }
        
        # Check if watermark should be applied
        if not self.should_apply_watermark(user_plan, user_settings):
            watermark_info["reason"] = "disabled_by_plan_or_settings"
            logger.info("Watermark skipped", plan=user_plan, reason=watermark_info["reason"])
            return image_data, watermark_info
        
        try:
            # Load image
            with Image.open(BytesIO(image_data)) as img:
                # Convert to RGBA for transparency support
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                
                # Create watermark overlay
                overlay = Image.new('RGBA', img.size, (255, 255, 255, 0))
                draw = ImageDraw.Draw(overlay)
                
                # Determine watermark text
                watermark_text = self._get_watermark_text(custom_text, user_plan)
                
                # Get font and position
                font = self._get_font(img.size)
                position = self._get_watermark_position(img.size, watermark_text, font, user_settings)
                
                # Get watermark color and opacity
                color, opacity = self._get_watermark_style(user_settings)
                
                # Draw watermark text
                draw.text(
                    position,
                    watermark_text,
                    font=font,
                    fill=(*color, opacity)
                )
                
                # Apply overlay to image
                watermarked = Image.alpha_composite(img, overlay)
                
                # Convert back to original mode if needed
                if watermarked.mode == 'RGBA' and img.mode != 'RGBA':
                    # Create white background for JPEG conversion
                    background = Image.new('RGB', watermarked.size, (255, 255, 255))
                    background.paste(watermarked, mask=watermarked.split()[-1])  # Use alpha channel as mask
                    watermarked = background
                
                # Save to bytes
                output_buffer = BytesIO()
                format_type = 'JPEG' if watermarked.mode == 'RGB' else 'PNG'
                
                save_kwargs = {'format': format_type}
                if format_type == 'JPEG':
                    save_kwargs['quality'] = 95
                    save_kwargs['optimize'] = True
                
                watermarked.save(output_buffer, **save_kwargs)
                
                watermark_info.update({
                    "watermark_applied": True,
                    "text": watermark_text,
                    "position": position,
                    "opacity": opacity,
                    "format": format_type,
                    "size_increase": len(output_buffer.getvalue()) - len(image_data)
                })
                
                logger.info("Watermark applied successfully",
                           plan=user_plan,
                           text=watermark_text,
                           position=position)
                
                return output_buffer.getvalue(), watermark_info
                
        except Exception as e:
            logger.error("Failed to apply watermark", error=str(e), plan=user_plan)
            watermark_info.update({
                "reason": "processing_error",
                "error": str(e)
            })
            # Return original image if watermarking fails
            return image_data, watermark_info
    
    def _get_watermark_text(self, custom_text: Optional[str], user_plan: str) -> str:
        """Get watermark text based on plan and custom settings."""
        # Premium users can use custom text
        if user_plan == "premium" and custom_text:
            return custom_text[:50]  # Limit length
        
        return self.default_text
    
    def _get_font(self, image_size: Tuple[int, int]) -> ImageFont.FreeTypeFont:
        """Get appropriate font for watermark based on image size."""
        width, height = image_size
        font_size = int(width * self.default_font_size_ratio)
        
        # Ensure minimum and maximum font sizes
        font_size = max(12, min(font_size, 72))
        
        try:
            # Try to load a system font
            if os.name == 'nt':  # Windows
                font_paths = [
                    "C:/Windows/Fonts/arial.ttf",
                    "C:/Windows/Fonts/calibri.ttf"
                ]
            else:  # Linux/Mac
                font_paths = [
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                    "/System/Library/Fonts/Arial.ttf",
                    "/usr/share/fonts/TTF/arial.ttf"
                ]
            
            for font_path in font_paths:
                if os.path.exists(font_path):
                    return ImageFont.truetype(font_path, font_size)
            
            # Fallback to default font
            return ImageFont.load_default()
            
        except Exception:
            # Use default font as last resort
            return ImageFont.load_default()
    
    def _get_watermark_position(
        self, 
        image_size: Tuple[int, int], 
        text: str, 
        font: ImageFont.FreeTypeFont,
        user_settings: Optional[Dict] = None
    ) -> Tuple[int, int]:
        """Calculate watermark position based on settings and image size."""
        width, height = image_size
        margin_x = int(width * self.margin_ratio)
        margin_y = int(height * self.margin_ratio)
        
        # Get text dimensions
        bbox = font.getbbox(text)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        # Get position preference
        position = WatermarkPosition.BOTTOM_RIGHT
        if user_settings and "watermark_position" in user_settings:
            try:
                position = WatermarkPosition(user_settings["watermark_position"])
            except ValueError:
                pass  # Use default if invalid position
        
        # Calculate position based on preference
        if position == WatermarkPosition.BOTTOM_RIGHT:
            x = width - text_width - margin_x
            y = height - text_height - margin_y
        elif position == WatermarkPosition.BOTTOM_LEFT:
            x = margin_x
            y = height - text_height - margin_y
        elif position == WatermarkPosition.TOP_RIGHT:
            x = width - text_width - margin_x
            y = margin_y
        elif position == WatermarkPosition.TOP_LEFT:
            x = margin_x
            y = margin_y
        else:  # CENTER
            x = (width - text_width) // 2
            y = (height - text_height) // 2
        
        return (max(0, x), max(0, y))
    
    def _get_watermark_style(self, user_settings: Optional[Dict] = None) -> Tuple[Tuple[int, int, int], int]:
        """Get watermark color and opacity based on user settings."""
        # Default white color
        color = (255, 255, 255)
        opacity = int(255 * self.default_opacity)
        
        if user_settings:
            # Custom color (premium feature)
            if "watermark_color" in user_settings:
                try:
                    color_hex = user_settings["watermark_color"]
                    if color_hex.startswith("#"):
                        color_hex = color_hex[1:]
                    color = tuple(int(color_hex[i:i+2], 16) for i in (0, 2, 4))
                except (ValueError, IndexError):
                    pass  # Use default if invalid color
            
            # Custom opacity
            if "watermark_opacity" in user_settings:
                try:
                    opacity_pct = float(user_settings["watermark_opacity"])
                    opacity = int(255 * max(0.1, min(1.0, opacity_pct)))
                except (ValueError, TypeError):
                    pass  # Use default if invalid opacity
        
        return color, opacity
    
    def get_watermark_preview(
        self, 
        user_plan: str,
        user_settings: Optional[Dict] = None,
        custom_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get watermark preview configuration without processing an image.
        
        Args:
            user_plan: User's subscription plan
            user_settings: Optional user watermark preferences  
            custom_text: Optional custom watermark text
            
        Returns:
            Dictionary with watermark configuration preview
        """
        preview = {
            "watermark_enabled": self.should_apply_watermark(user_plan, user_settings),
            "text": self._get_watermark_text(custom_text, user_plan),
            "user_plan": user_plan
        }
        
        if preview["watermark_enabled"]:
            color, opacity = self._get_watermark_style(user_settings)
            preview.update({
                "color_rgb": color,
                "opacity": opacity / 255.0,
                "position": user_settings.get("watermark_position", "bottom_right") if user_settings else "bottom_right",
                "customizable": user_plan in ["pro", "premium"]
            })
        
        return preview