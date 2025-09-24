"""
Content safety service for NSFW detection and content moderation.
"""
import hashlib
import structlog
from typing import Dict, Any, BinaryIO, Optional, Tuple
from io import BytesIO
from PIL import Image
from enum import Enum

logger = structlog.get_logger(__name__)


class NSFWMode(Enum):
    """NSFW detection modes."""
    BLOCK = "block"     # Block NSFW content completely
    FLAG = "flag"       # Flag NSFW content but allow processing


class NSFWSeverity(Enum):
    """NSFW content severity levels."""
    SAFE = "safe"
    SUGGESTIVE = "suggestive"
    EXPLICIT = "explicit"
    
    
class ContentViolationType(Enum):
    """Types of content violations."""
    NSFW_EXPLICIT = "nsfw_explicit"
    NSFW_SUGGESTIVE = "nsfw_suggestive"
    VIOLENCE = "violence"
    HATE_SYMBOLS = "hate_symbols"
    MINOR_SAFETY = "minor_safety"


class NSFWDetectionService:
    """Service for detecting NSFW content in images using basic heuristics."""
    
    def __init__(self, detection_mode: NSFWMode = NSFWMode.BLOCK):
        """
        Initialize NSFW detection service.
        
        Args:
            detection_mode: Mode for handling NSFW content (block or flag)
        """
        self.detection_mode = detection_mode
        
        # Basic skin tone detection thresholds
        self.skin_tone_ranges = [
            ((255, 220, 177), (255, 255, 230)),  # Light skin
            ((215, 180, 140), (245, 210, 180)),  # Medium skin  
            ((185, 140, 100), (215, 180, 140)),  # Dark skin
            ((150, 100, 70), (185, 140, 100)),   # Very dark skin
        ]
        
        # Suspicious pixel ratio thresholds
        self.skin_ratio_threshold = 0.35  # 35% skin-colored pixels
        self.flesh_tone_threshold = 0.25  # 25% flesh tones
    
    def detect_nsfw_content(self, image_data: bytes) -> Dict[str, Any]:
        """
        Detect NSFW content in image using basic heuristics.
        
        Args:
            image_data: Raw image bytes
            
        Returns:
            Dictionary with detection results
        """
        detection_result = {
            "is_nsfw": False,
            "severity": NSFWSeverity.SAFE.value,
            "confidence": 0.0,
            "detection_method": "heuristic",
            "flags": [],
            "safe_for_processing": True
        }
        
        try:
            # Basic image analysis
            with Image.open(BytesIO(image_data)) as img:
                # Convert to RGB for analysis
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Resize for faster processing
                analysis_size = (256, 256)
                img_small = img.resize(analysis_size, Image.Resampling.LANCZOS)
                
                # Perform heuristic analysis
                skin_analysis = self._analyze_skin_content(img_small)
                content_analysis = self._analyze_content_patterns(img_small)
                
                # Calculate overall NSFW score
                nsfw_score = self._calculate_nsfw_score(skin_analysis, content_analysis)
                
                # Determine result based on score
                if nsfw_score > 0.7:
                    detection_result.update({
                        "is_nsfw": True,
                        "severity": NSFWSeverity.EXPLICIT.value,
                        "confidence": nsfw_score
                    })
                elif nsfw_score > 0.4:
                    detection_result.update({
                        "is_nsfw": True,
                        "severity": NSFWSeverity.SUGGESTIVE.value,
                        "confidence": nsfw_score
                    })
                else:
                    detection_result["confidence"] = 1.0 - nsfw_score
                
                # Add analysis details
                detection_result.update({
                    "analysis": {
                        "skin_ratio": skin_analysis["skin_ratio"],
                        "flesh_tone_ratio": skin_analysis["flesh_tone_ratio"],
                        "suspicious_patterns": content_analysis["suspicious_patterns"]
                    }
                })
                
                # Set processing permission based on mode
                if detection_result["is_nsfw"]:
                    if self.detection_mode == NSFWMode.BLOCK:
                        detection_result["safe_for_processing"] = False
                        detection_result["flags"].append("blocked_by_nsfw_policy")
                    else:  # FLAG mode
                        detection_result["safe_for_processing"] = True
                        detection_result["flags"].append("flagged_as_nsfw")
                
                logger.info("NSFW detection completed",
                           is_nsfw=detection_result["is_nsfw"],
                           severity=detection_result["severity"],
                           confidence=detection_result["confidence"],
                           mode=self.detection_mode.value)
                
        except Exception as e:
            logger.error("NSFW detection failed", error=str(e))
            detection_result.update({
                "error": str(e),
                "safe_for_processing": True  # Fail open for safety
            })
        
        return detection_result
    
    def _analyze_skin_content(self, img: Image.Image) -> Dict[str, Any]:
        """Analyze skin-colored pixel content in image."""
        pixels = list(img.getdata())
        total_pixels = len(pixels)
        
        skin_pixels = 0
        flesh_tone_pixels = 0
        
        for pixel in pixels:
            r, g, b = pixel
            
            # Check if pixel is skin-colored
            if self._is_skin_color(r, g, b):
                skin_pixels += 1
            
            # Check for flesh tones (broader range)
            if self._is_flesh_tone(r, g, b):
                flesh_tone_pixels += 1
        
        return {
            "skin_ratio": skin_pixels / total_pixels,
            "flesh_tone_ratio": flesh_tone_pixels / total_pixels,
            "skin_pixels": skin_pixels,
            "total_pixels": total_pixels
        }
    
    def _analyze_content_patterns(self, img: Image.Image) -> Dict[str, Any]:
        """Analyze suspicious content patterns."""
        # Convert to grayscale for edge detection
        gray = img.convert('L')
        pixels = list(gray.getdata())
        
        # Basic edge detection (simplified)
        width, height = img.size
        edges = 0
        
        for y in range(1, height - 1):
            for x in range(1, width - 1):
                center = pixels[y * width + x]
                # Check surrounding pixels for edges
                surrounding = [
                    pixels[(y-1) * width + x],
                    pixels[(y+1) * width + x],
                    pixels[y * width + (x-1)],
                    pixels[y * width + (x+1)]
                ]
                
                if any(abs(center - p) > 50 for p in surrounding):
                    edges += 1
        
        edge_density = edges / (width * height)
        
        return {
            "edge_density": edge_density,
            "suspicious_patterns": edge_density > 0.3  # High edge density might indicate problematic content
        }
    
    def _is_skin_color(self, r: int, g: int, b: int) -> bool:
        """Check if RGB values match skin color ranges."""
        for (min_r, min_g, min_b), (max_r, max_g, max_b) in self.skin_tone_ranges:
            if min_r <= r <= max_r and min_g <= g <= max_g and min_b <= b <= max_b:
                return True
        return False
    
    def _is_flesh_tone(self, r: int, g: int, b: int) -> bool:
        """Check if RGB values are in flesh tone range (broader than skin detection)."""
        # Flesh tones typically have higher red values
        return (
            r > g and r > b and  # Red dominance
            r >= 95 and g >= 40 and b >= 20 and  # Minimum values
            max(r, g, b) - min(r, g, b) > 15 and  # Sufficient contrast
            abs(r - g) > 15  # Red-green difference
        )
    
    def _calculate_nsfw_score(self, skin_analysis: Dict, content_analysis: Dict) -> float:
        """Calculate overall NSFW score based on analysis results."""
        score = 0.0
        
        # Skin ratio contribution
        skin_ratio = skin_analysis["skin_ratio"]
        if skin_ratio > self.skin_ratio_threshold:
            score += min(0.6, (skin_ratio - self.skin_ratio_threshold) * 2)
        
        # Flesh tone contribution
        flesh_ratio = skin_analysis["flesh_tone_ratio"]
        if flesh_ratio > self.flesh_tone_threshold:
            score += min(0.3, (flesh_ratio - self.flesh_tone_threshold) * 1.5)
        
        # Suspicious patterns contribution
        if content_analysis["suspicious_patterns"]:
            score += 0.2
        
        return min(1.0, score)


class ContentSafetyService:
    """Main content safety service coordinating various safety checks."""
    
    def __init__(self, nsfw_mode: NSFWMode = NSFWMode.BLOCK):
        """
        Initialize content safety service.
        
        Args:
            nsfw_mode: Mode for handling NSFW content
        """
        self.nsfw_detector = NSFWDetectionService(nsfw_mode)
        self.nsfw_mode = nsfw_mode
    
    def evaluate_content_safety(
        self, 
        image_data: bytes, 
        user_plan: str,
        additional_checks: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Perform comprehensive content safety evaluation.
        
        Args:
            image_data: Raw image bytes
            user_plan: User's subscription plan
            additional_checks: Optional additional safety checks
            
        Returns:
            Dictionary with comprehensive safety evaluation
        """
        safety_result = {
            "safe": True,
            "violations": [],
            "warnings": [],
            "user_plan": user_plan,
            "checks_performed": [],
            "processing_allowed": True
        }
        
        try:
            # NSFW Detection
            nsfw_result = self.nsfw_detector.detect_nsfw_content(image_data)
            safety_result["nsfw_detection"] = nsfw_result
            safety_result["checks_performed"].append("nsfw_detection")
            
            # Process NSFW results
            if nsfw_result["is_nsfw"]:
                violation = {
                    "type": ContentViolationType.NSFW_EXPLICIT.value if nsfw_result["severity"] == "explicit" 
                            else ContentViolationType.NSFW_SUGGESTIVE.value,
                    "severity": nsfw_result["severity"],
                    "confidence": nsfw_result["confidence"],
                    "message": f"Content flagged as {nsfw_result['severity']} NSFW material"
                }
                
                if self.nsfw_mode == NSFWMode.BLOCK:
                    safety_result["violations"].append(violation)
                    safety_result["safe"] = False
                    safety_result["processing_allowed"] = False
                else:
                    safety_result["warnings"].append(violation)
            
            # Additional plan-based checks
            if user_plan == "free":
                # Free users have stricter content policies
                if nsfw_result.get("confidence", 0) > 0.3:  # Lower threshold for free users
                    safety_result["warnings"].append({
                        "type": "plan_restriction",
                        "message": "Content may violate free plan policies"
                    })
            
            # Basic image validation
            image_validation = self._validate_image_content(image_data)
            safety_result["image_validation"] = image_validation
            safety_result["checks_performed"].append("image_validation")
            
            if not image_validation["valid"]:
                safety_result["violations"].extend(image_validation["violations"])
                safety_result["safe"] = False
                safety_result["processing_allowed"] = False
            
            logger.info("Content safety evaluation completed",
                       safe=safety_result["safe"],
                       violations_count=len(safety_result["violations"]),
                       warnings_count=len(safety_result["warnings"]),
                       plan=user_plan)
            
        except Exception as e:
            logger.error("Content safety evaluation failed", error=str(e))
            safety_result.update({
                "error": str(e),
                "safe": True,  # Fail open
                "processing_allowed": True
            })
        
        return safety_result
    
    def _validate_image_content(self, image_data: bytes) -> Dict[str, Any]:
        """Basic image content validation."""
        validation_result = {
            "valid": True,
            "violations": [],
            "metadata": {}
        }
        
        try:
            with Image.open(BytesIO(image_data)) as img:
                # Check image properties
                width, height = img.size
                
                # Size limits
                if width > 4096 or height > 4096:
                    validation_result["violations"].append({
                        "type": "oversized_image",
                        "message": f"Image dimensions too large: {width}x{height}"
                    })
                    validation_result["valid"] = False
                
                # Minimum size
                if width < 64 or height < 64:
                    validation_result["violations"].append({
                        "type": "undersized_image", 
                        "message": f"Image dimensions too small: {width}x{height}"
                    })
                    validation_result["valid"] = False
                
                validation_result["metadata"] = {
                    "format": img.format,
                    "mode": img.mode,
                    "size": img.size
                }
                
        except Exception as e:
            validation_result["violations"].append({
                "type": "invalid_image",
                "message": f"Cannot process image: {str(e)}"
            })
            validation_result["valid"] = False
        
        return validation_result
    
    def get_safety_policy(self, user_plan: str) -> Dict[str, Any]:
        """Get content safety policy for user plan."""
        policies = {
            "free": {
                "nsfw_mode": "block",
                "nsfw_threshold": 0.3,
                "max_image_size": 2048,
                "allowed_formats": ["JPEG", "PNG"],
                "restrictions": [
                    "NSFW content strictly prohibited",
                    "Commercial use restrictions apply",
                    "Watermarks applied to all outputs"
                ]
            },
            "pro": {
                "nsfw_mode": "flag",
                "nsfw_threshold": 0.5,
                "max_image_size": 4096,
                "allowed_formats": ["JPEG", "PNG", "WEBP"],
                "restrictions": [
                    "Explicit NSFW content flagged but allowed",
                    "Commercial use permitted",
                    "Optional watermarks"
                ]
            },
            "premium": {
                "nsfw_mode": "flag",
                "nsfw_threshold": 0.7,
                "max_image_size": 8192,
                "allowed_formats": ["JPEG", "PNG", "WEBP", "TIFF"],
                "restrictions": [
                    "Minimal content restrictions",
                    "Full commercial rights",
                    "No watermarks"
                ]
            }
        }
        
        return policies.get(user_plan, policies["free"])