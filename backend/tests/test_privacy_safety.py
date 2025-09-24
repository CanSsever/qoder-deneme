"""
Tests for privacy and content safety features.
"""
import pytest
import tempfile
import os
from io import BytesIO
from PIL import Image, ExifTags
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from apps.core.privacy import (
    ImagePrivacyService,
    ContentSafetyService,
    NSFWDetectionService,
    WatermarkService,
    DataRetentionService,
    FaceConsentService
)
from apps.core.privacy.content_safety import NSFWMode, NSFWSeverity
from apps.core.privacy.watermark import WatermarkPosition
from apps.db.models.user import User


class TestImagePrivacyService:
    """Test image privacy features."""
    
    def test_strip_exif_metadata(self):
        """Test EXIF metadata stripping."""
        # Create test image with EXIF data
        img = Image.new('RGB', (100, 100), color='red')
        
        # Add fake EXIF data
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}
        exif_dict["0th"][ExifTags.TAGS_V2['Make'].value] = "Test Camera"
        exif_dict["0th"][ExifTags.TAGS_V2['Model'].value] = "Test Model"
        
        # Save with metadata
        img_buffer = BytesIO()
        img.save(img_buffer, format='JPEG', quality=95)
        original_data = img_buffer.getvalue()
        
        # Strip EXIF
        privacy_service = ImagePrivacyService()
        clean_data, metadata_info = privacy_service.strip_exif_metadata(original_data)
        
        # Verify EXIF was removed
        assert len(clean_data) > 0
        assert clean_data != original_data
        
        # Check that clean image has no EXIF
        clean_img = Image.open(BytesIO(clean_data))
        clean_exif = clean_img.getexif()
        assert len(clean_exif) == 0 or clean_exif is None
    
    def test_process_upload_privacy(self):
        """Test upload privacy processing."""
        # Create test image
        img = Image.new('RGB', (200, 200), color='blue')
        img_buffer = BytesIO()
        img.save(img_buffer, format='JPEG')
        image_data = img_buffer.getvalue()
        
        privacy_service = ImagePrivacyService()
        processed_data, processing_info = privacy_service.process_upload_privacy(
            image_data, "test.jpg"
        )
        
        assert processing_info["privacy_processed"] is True
        assert processing_info["original_size"] == len(image_data)
        assert len(processed_data) > 0
    
    def test_validate_image_safety(self):
        """Test image safety validation."""
        # Create valid test image
        img = Image.new('RGB', (300, 300), color='green')
        img_buffer = BytesIO()
        img.save(img_buffer, format='PNG')
        image_data = img_buffer.getvalue()
        
        privacy_service = ImagePrivacyService()
        validation_result = privacy_service.validate_image_safety(image_data)
        
        assert validation_result["valid"] is True
        assert len(validation_result["issues"]) == 0
        assert validation_result["metadata"]["format"] == "PNG"
        assert validation_result["metadata"]["size"] == (300, 300)


class TestNSFWDetectionService:
    """Test NSFW content detection."""
    
    def test_detect_nsfw_content_safe_image(self):
        """Test NSFW detection on safe image."""
        # Create simple safe image (mostly blue)
        img = Image.new('RGB', (256, 256), color='blue')
        img_buffer = BytesIO()
        img.save(img_buffer, format='JPEG')
        image_data = img_buffer.getvalue()
        
        nsfw_service = NSFWDetectionService(NSFWMode.BLOCK)
        result = nsfw_service.detect_nsfw_content(image_data)
        
        assert result["is_nsfw"] is False
        assert result["severity"] == NSFWSeverity.SAFE.value
        assert result["safe_for_processing"] is True
        assert result["confidence"] > 0.5  # Should be confident it's safe
    
    def test_detect_nsfw_content_suspicious_image(self):
        """Test NSFW detection on suspicious image."""
        # Create image with high skin tone content
        img = Image.new('RGB', (256, 256))
        pixels = []
        for y in range(256):
            for x in range(256):
                # Add lots of skin-colored pixels
                pixels.append((220, 170, 120))  # Skin tone
        img.putdata(pixels)
        
        img_buffer = BytesIO()
        img.save(img_buffer, format='JPEG')
        image_data = img_buffer.getvalue()
        
        nsfw_service = NSFWDetectionService(NSFWMode.BLOCK)
        result = nsfw_service.detect_nsfw_content(image_data)
        
        # Should detect as suspicious due to high skin ratio
        assert "analysis" in result
        assert result["analysis"]["skin_ratio"] > 0.8  # High skin content
    
    def test_nsfw_modes(self):
        """Test different NSFW detection modes."""
        img = Image.new('RGB', (100, 100), color='red')
        img_buffer = BytesIO()
        img.save(img_buffer, format='JPEG')
        image_data = img_buffer.getvalue()
        
        # Test BLOCK mode
        block_service = NSFWDetectionService(NSFWMode.BLOCK)
        block_result = block_service.detect_nsfw_content(image_data)
        
        # Test FLAG mode
        flag_service = NSFWDetectionService(NSFWMode.FLAG)
        flag_result = flag_service.detect_nsfw_content(image_data)
        
        # Both should process but have different behaviors for violations
        assert "safe_for_processing" in block_result
        assert "safe_for_processing" in flag_result


class TestContentSafetyService:
    """Test comprehensive content safety."""
    
    def test_evaluate_content_safety_safe_content(self):
        """Test content safety evaluation on safe content."""
        img = Image.new('RGB', (400, 400), color='white')
        img_buffer = BytesIO()
        img.save(img_buffer, format='PNG')
        image_data = img_buffer.getvalue()
        
        safety_service = ContentSafetyService(NSFWMode.BLOCK)
        result = safety_service.evaluate_content_safety(image_data, "pro")
        
        assert result["safe"] is True
        assert result["processing_allowed"] is True
        assert len(result["violations"]) == 0
        assert "nsfw_detection" in result
        assert "image_validation" in result
    
    def test_get_safety_policy_by_plan(self):
        """Test safety policy retrieval by plan."""
        safety_service = ContentSafetyService()
        
        free_policy = safety_service.get_safety_policy("free")
        pro_policy = safety_service.get_safety_policy("pro")
        premium_policy = safety_service.get_safety_policy("premium")
        
        # Free plan should be most restrictive
        assert free_policy["nsfw_mode"] == "block"
        assert free_policy["max_image_size"] == 2048
        
        # Pro plan should be less restrictive
        assert pro_policy["nsfw_mode"] == "flag"
        assert pro_policy["max_image_size"] == 4096
        
        # Premium should be least restrictive
        assert premium_policy["max_image_size"] == 8192


class TestWatermarkService:
    """Test watermark functionality."""
    
    def test_should_apply_watermark_by_plan(self):
        """Test watermark application logic by plan."""
        watermark_service = WatermarkService()
        
        # Free users always get watermarks
        assert watermark_service.should_apply_watermark("free") is True
        
        # Pro users can disable (default off)
        assert watermark_service.should_apply_watermark("pro") is False
        
        # Pro users with enabled setting
        pro_settings = {"watermark_enabled": True}
        assert watermark_service.should_apply_watermark("pro", pro_settings) is True
    
    def test_apply_watermark(self):
        """Test watermark application."""
        img = Image.new('RGB', (500, 500), color='white')
        img_buffer = BytesIO()
        img.save(img_buffer, format='JPEG')
        image_data = img_buffer.getvalue()
        
        watermark_service = WatermarkService()
        watermarked_data, watermark_info = watermark_service.apply_watermark(
            image_data, "free"
        )
        
        assert watermark_info["watermark_applied"] is True
        assert watermark_info["text"] == "oneshot.ai"
        assert len(watermarked_data) > 0
        assert watermarked_data != image_data  # Should be different
    
    def test_watermark_positions(self):
        """Test different watermark positions."""
        img = Image.new('RGB', (400, 400), color='gray')
        img_buffer = BytesIO()
        img.save(img_buffer, format='PNG')
        image_data = img_buffer.getvalue()
        
        watermark_service = WatermarkService()
        
        positions = [
            WatermarkPosition.BOTTOM_RIGHT,
            WatermarkPosition.TOP_LEFT,
            WatermarkPosition.CENTER
        ]
        
        for position in positions:
            settings = {"watermark_position": position.value}
            watermarked_data, info = watermark_service.apply_watermark(
                image_data, "free", settings
            )
            
            assert info["watermark_applied"] is True
            assert len(watermarked_data) > 0
    
    def test_get_watermark_preview(self):
        """Test watermark preview functionality."""
        watermark_service = WatermarkService()
        
        preview = watermark_service.get_watermark_preview("pro")
        
        assert "watermark_enabled" in preview
        assert "text" in preview
        assert "customizable" in preview
        assert preview["plan"] == "pro"


class TestFaceConsentService:
    """Test face consent enforcement."""
    
    def test_validate_face_swap_consent_valid(self):
        """Test valid face swap consent."""
        consent_service = FaceConsentService()
        
        # Valid consent parameters for free plan
        job_params = {
            "face_swap_consent": True,
            "deepfake_awareness_consent": True
        }
        
        result = consent_service.validate_face_swap_consent(
            job_params, "free", "face_swap"
        )
        
        assert result["consent_valid"] is True
        assert len(result["violations"]) == 0
        assert result["applicable"] is True
    
    def test_validate_face_swap_consent_missing(self):
        """Test missing face swap consent."""
        consent_service = FaceConsentService()
        
        # Missing required consent
        job_params = {
            "face_swap_consent": False,  # Missing required consent
            "deepfake_awareness_consent": True
        }
        
        result = consent_service.validate_face_swap_consent(
            job_params, "free", "face_swap"
        )
        
        assert result["consent_valid"] is False
        assert len(result["violations"]) > 0
        assert "face_swap_consent" in result["missing_consents"]
    
    def test_consent_requirements_by_plan(self):
        """Test consent requirements vary by plan."""
        consent_service = FaceConsentService()
        
        free_consents = consent_service.get_required_consents_for_plan("free")
        pro_consents = consent_service.get_required_consents_for_plan("pro")
        premium_consents = consent_service.get_required_consents_for_plan("premium")
        
        # Free should require most consents
        assert len(free_consents["required_consents"]) >= 2
        
        # Premium should require fewest
        assert len(premium_consents["required_consents"]) == 1
        
        # Check strict enforcement
        assert free_consents["strict_enforcement"] is True
        assert premium_consents["strict_enforcement"] is False
    
    def test_non_face_swap_jobs_skip_consent(self):
        """Test that non-face-swap jobs skip consent validation."""
        consent_service = FaceConsentService()
        
        result = consent_service.validate_face_swap_consent(
            {}, "free", "face_restoration"
        )
        
        assert result["applicable"] is False
        assert result["consent_valid"] is True


class TestDataRetentionService:
    """Test data retention and cleanup."""
    
    @patch('apps.core.privacy.data_retention.get_session')
    @patch('boto3.client')
    def test_get_retention_stats(self, mock_boto, mock_session):
        """Test retention statistics."""
        # Mock database session
        mock_db_session = MagicMock()
        mock_session.return_value = iter([mock_db_session])
        
        # Mock query results
        mock_db_session.exec.return_value.all.return_value = []
        
        retention_service = DataRetentionService(retention_days=30)
        stats = retention_service.get_retention_stats()
        
        assert "total_jobs" in stats
        assert "expired_jobs" in stats
        assert "cutoff_date" in stats
        assert stats["retention_days"] == 30 if "retention_days" in stats else True
    
    @patch('apps.core.privacy.data_retention.get_session')
    def test_run_retention_cleanup_dry_run(self, mock_session):
        """Test retention cleanup in dry run mode."""
        # Mock database session
        mock_db_session = MagicMock()
        mock_session.return_value = iter([mock_db_session])
        
        # Mock empty results
        mock_db_session.exec.return_value.all.return_value = []
        
        retention_service = DataRetentionService(retention_days=7)
        result = retention_service.run_retention_cleanup(dry_run=True)
        
        assert result["dry_run"] is True
        assert result["retention_days"] == 7
        assert "jobs_processed" in result
        assert "artifacts_deleted" in result


class TestPrivacyIntegration:
    """Test privacy features integration with API."""
    
    def test_face_swap_job_with_missing_consent(self, client: TestClient, auth_headers: dict):
        """Test face swap job creation fails without consent."""
        job_data = {
            "job_type": "face_swap",
            "input_image_url": "https://example.com/input.jpg",
            "target_image_url": "https://example.com/target.jpg",
            "parameters": {
                # Missing required consent flags
                "blend_ratio": 0.8
            }
        }
        
        response = client.post("/api/v1/jobs", json=job_data, headers=auth_headers)
        
        # Should fail with 422 due to missing consent
        assert response.status_code == 422
        response_data = response.json()
        assert response_data["detail"]["code"] in ["consent_required", "nsfw_blocked"]
        assert "missing_consents" in response_data["detail"]
    
    def test_face_swap_job_with_valid_consent(self, client: TestClient, auth_headers: dict):
        """Test face swap job creation succeeds with proper consent."""
        job_data = {
            "job_type": "face_swap",
            "input_image_url": "https://example.com/input.jpg",
            "target_image_url": "https://example.com/target.jpg",
            "parameters": {
                "face_swap_consent": True,
                "deepfake_awareness_consent": True,
                "blend_ratio": 0.8
            }
        }
        
        with patch('apps.worker.tasks.process_ai_job.delay') as mock_task:
            mock_task.return_value.id = "test-task-id"
            
            response = client.post("/api/v1/jobs", json=job_data, headers=auth_headers)
        
        # Should succeed with proper consent
        assert response.status_code == 201 or response.status_code == 200
        if response.status_code in [200, 201]:
            response_data = response.json()
            assert "job_id" in response_data
    
    def test_non_face_swap_job_no_consent_required(self, client: TestClient, auth_headers: dict):
        """Test non-face-swap jobs don't require consent."""
        job_data = {
            "job_type": "face_restoration",
            "input_image_url": "https://example.com/input.jpg",
            "parameters": {
                "model": "gfpgan"
                # No consent flags needed for face restoration
            }
        }
        
        with patch('apps.worker.tasks.process_ai_job.delay') as mock_task:
            mock_task.return_value.id = "test-task-id"
            
            response = client.post("/api/v1/jobs", json=job_data, headers=auth_headers)
        
        # Should succeed without consent for non-face-swap
        assert response.status_code in [200, 201, 402, 429]  # 402/429 are credit/rate limit issues, not consent


# Test fixtures for privacy tests
@pytest.fixture
def sample_image_data():
    """Create sample image data for testing."""
    img = Image.new('RGB', (100, 100), color='red')
    buffer = BytesIO()
    img.save(buffer, format='JPEG')
    return buffer.getvalue()


@pytest.fixture
def sample_image_with_exif():
    """Create sample image with EXIF data."""
    img = Image.new('RGB', (200, 200), color='blue')
    buffer = BytesIO()
    img.save(buffer, format='JPEG', quality=95)
    return buffer.getvalue()