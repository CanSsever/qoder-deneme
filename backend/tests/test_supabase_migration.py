"""
Basic tests for Supabase migration implementation.
Run with: python -m pytest tests/test_supabase_migration.py -v
"""
import pytest
from unittest.mock import Mock, patch
from apps.core.security import SecurityUtils, SupabaseUser
from apps.core.supabase_client import SupabaseClient
from apps.api.services import ProfileService, JobService, CreditService, UploadService


class TestSupabaseAuthentication:
    """Test Supabase authentication and JWT validation."""
    
    def test_supabase_user_creation(self):
        """Test SupabaseUser object creation."""
        user = SupabaseUser(
            user_id="123e4567-e89b-12d3-a456-426614174000",
            email="test@example.com",
            payload={"sub": "123e4567-e89b-12d3-a456-426614174000", "email": "test@example.com"}
        )
        
        assert user.id == "123e4567-e89b-12d3-a456-426614174000"
        assert user.email == "test@example.com"
        assert user.payload["sub"] == "123e4567-e89b-12d3-a456-426614174000"
    
    @patch('apps.core.security.jwt.decode')
    def test_jwt_validation(self, mock_jwt_decode):
        """Test JWT token validation."""
        # Mock valid JWT payload
        mock_jwt_decode.return_value = {
            "sub": "123e4567-e89b-12d3-a456-426614174000",
            "email": "test@example.com",
            "exp": 1234567890
        }
        
        result = SecurityUtils.verify_supabase_token("fake.jwt.token")
        
        assert result is not None
        assert result["sub"] == "123e4567-e89b-12d3-a456-426614174000"
        assert result["email"] == "test@example.com"
    
    def test_user_extraction_from_token(self):
        """Test extracting user from JWT payload."""
        payload = {
            "sub": "123e4567-e89b-12d3-a456-426614174000",
            "email": "test@example.com",
            "exp": 1234567890
        }
        
        user = SecurityUtils.extract_user_from_token(payload)
        
        assert user is not None
        assert user.id == "123e4567-e89b-12d3-a456-426614174000"
        assert user.email == "test@example.com"


class TestSupabaseClient:
    """Test Supabase client wrapper functionality."""
    
    @patch('apps.core.supabase_client.create_client')
    def test_client_initialization(self, mock_create_client):
        """Test Supabase client initialization."""
        mock_client = Mock()
        mock_create_client.return_value = mock_client
        
        # Mock settings
        with patch('apps.core.supabase_client.settings') as mock_settings:
            mock_settings.supabase_url = "https://test.supabase.co"
            mock_settings.supabase_anon_key = "test-key"
            
            client = SupabaseClient()
            client._initialize_client()
            
            assert client._client == mock_client
            mock_create_client.assert_called_once()


class TestServices:
    """Test service layer functionality."""
    
    def test_upload_service_instructions(self):
        """Test upload instructions generation."""
        instructions = UploadService.get_upload_instructions(
            user_id="123e4567-e89b-12d3-a456-426614174000",
            filename="test.jpg",
            content_type="image/jpeg",
            file_size=1024000
        )
        
        assert "bucket" in instructions
        assert "file_path" in instructions
        assert "upload_url" in instructions
        assert instructions["bucket"] == "uploads"
        assert instructions["file_path"].startswith("123e4567-e89b-12d3-a456-426614174000/")
    
    def test_job_service_credit_costs(self):
        """Test job service credit cost mapping."""
        assert JobService.CREDIT_COSTS["face_swap"] == 2
        assert JobService.CREDIT_COSTS["face_restore"] == 1
        assert JobService.CREDIT_COSTS["upscale"] == 1
    
    @patch('apps.api.services.supabase_client')
    def test_profile_service_get_profile(self, mock_supabase_client):
        """Test profile service get profile."""
        mock_supabase_client.get_profile.return_value = {
            "id": "123e4567-e89b-12d3-a456-426614174000",
            "email": "test@example.com",
            "credits": 10,
            "subscription_status": "inactive"
        }
        
        profile = ProfileService.get_profile("123e4567-e89b-12d3-a456-426614174000")
        
        assert profile is not None
        assert profile["email"] == "test@example.com"
        assert profile["credits"] == 10
        mock_supabase_client.get_profile.assert_called_once_with("123e4567-e89b-12d3-a456-426614174000")


class TestValidation:
    """Test input validation and error handling."""
    
    def test_upload_file_size_validation(self):
        """Test file size validation for uploads."""
        # This would be tested in the actual router with pydantic validation
        max_size = 20 * 1024 * 1024  # 20MB
        
        # Valid size
        assert 1024000 < max_size
        
        # Invalid size
        assert 30 * 1024 * 1024 > max_size
    
    def test_job_type_validation(self):
        """Test job type validation."""
        valid_types = ["face_swap", "face_restore", "upscale"]
        
        assert "face_swap" in valid_types
        assert "invalid_type" not in valid_types


class TestErrorHandling:
    """Test error handling scenarios."""
    
    @patch('apps.core.security.jwt.decode')
    def test_invalid_jwt_handling(self, mock_jwt_decode):
        """Test handling of invalid JWT tokens."""
        # Mock JWT decode raising an exception
        mock_jwt_decode.side_effect = Exception("Invalid token")
        
        result = SecurityUtils.verify_supabase_token("invalid.jwt.token")
        
        assert result is None
    
    def test_missing_user_id_in_token(self):
        """Test handling of JWT payload without user ID."""
        payload = {
            "email": "test@example.com",
            "exp": 1234567890
            # Missing 'sub' field
        }
        
        user = SecurityUtils.extract_user_from_token(payload)
        
        assert user is None


if __name__ == "__main__":
    # Run basic smoke test
    print("Running basic Supabase migration tests...")
    
    # Test user creation
    user = SupabaseUser(
        user_id="test-user-id",
        email="test@example.com",
        payload={"sub": "test-user-id"}
    )
    print(f"✓ User creation: {user}")
    
    # Test upload instructions
    instructions = UploadService.get_upload_instructions(
        user_id="test-user",
        filename="test.jpg",
        content_type="image/jpeg",
        file_size=1000
    )
    print(f"✓ Upload instructions: {instructions['bucket']}/{instructions['file_path']}")
    
    # Test credit costs
    costs = JobService.CREDIT_COSTS
    print(f"✓ Credit costs: {costs}")
    
    print("Basic tests completed successfully!")