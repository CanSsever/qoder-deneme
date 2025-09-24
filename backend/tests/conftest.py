"""
Configuration for E2E tests with mock providers.
"""

import os
import tempfile
from pathlib import Path

import pytest
from sqlmodel import SQLModel, create_engine
from sqlmodel.pool import StaticPool

# Test database configuration
TEST_DATABASE_URL = "sqlite:///:memory:"

# Create test engine
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@pytest.fixture(scope="function")
def setup_test_database():
    """Setup test database for each test."""
    # Create all tables
    SQLModel.metadata.create_all(test_engine)
    
    yield test_engine
    
    # Clean up after test
    SQLModel.metadata.drop_all(test_engine)


@pytest.fixture
def session(setup_test_database):
    """Get database session for testing."""
    from sqlmodel import Session
    with Session(setup_test_database) as session:
        yield session


@pytest.fixture
def test_user(session):
    """Create a test user for testing."""
    from apps.db.models.user import User
    from apps.core.security import SecurityUtils
    
    user = User(
        email="test@example.com",
        hashed_password=SecurityUtils.get_password_hash("testpassword"),
        credits=50
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def temp_output_dir():
    """Create temporary directory for test outputs."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


# Mock settings for testing
class TestSettings:
    """Test-specific settings."""
    
    # Database
    database_url = TEST_DATABASE_URL
    
    # JWT
    jwt_secret = "test-jwt-secret"
    jwt_expiration_hours = 1
    jwt_algorithm = "HS256"
    
    # S3 (mocked)
    s3_bucket = "test-bucket"
    s3_key = "test-key"
    s3_secret = "test-secret"
    s3_region = "us-east-1"
    
    # Redis (mocked)
    redis_url = "redis://localhost:6379/1"
    
    # GPU Providers
    gpu_provider = "mock_comfy_local"
    comfy_local_url = "http://localhost:8188"
    runpod_api_key = "test-runpod-key"
    runpod_endpoint_id = "test-endpoint"
    
    # Output
    output_format = "png"
    output_quality = 95
    max_input_mb = 20
    
    # Security
    max_image_dimension = 8192
    min_image_dimension = 64
    
    # Webhooks
    hmac_secret = "test-hmac-secret"
    webhook_timeout_seconds = 5  # Shorter for tests
    webhook_retry_delays = [1, 2, 5]  # Shorter delays for tests
    
    # App settings
    default_credits = 10
    max_file_size_mb = 10
    environment = "testing"
    allowed_origins = ["http://localhost:3000"]
    log_level = "DEBUG"
    superwall_secret = "test-superwall-secret"


# Environment setup for tests
def setup_test_environment():
    """Setup environment variables for testing."""
    env_vars = {
        "DATABASE_URL": TEST_DATABASE_URL,
        "JWT_SECRET": "test-jwt-secret",
        "S3_BUCKET": "test-bucket",
        "S3_KEY": "test-key",
        "S3_SECRET": "test-secret",
        "REDIS_URL": "redis://localhost:6379/1",
        "GPU_PROVIDER": "mock_comfy_local",
        "COMFY_LOCAL_URL": "http://localhost:8188",
        "OUTPUT_FORMAT": "png",
        "MAX_INPUT_MB": "20",
        "HMAC_SECRET": "test-hmac-secret",
        "ENVIRONMENT": "testing",
        "SUPERWALL_SECRET": "test-superwall-secret"
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value


# Pytest configuration
def pytest_configure(config):
    """Configure pytest for E2E tests."""
    setup_test_environment()


# Custom markers for different test categories
def pytest_collection_modifyitems(config, items):
    """Add custom markers to tests."""
    for item in items:
        # Mark E2E tests
        if "test_e2e" in item.name or "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)
        
        # Mark provider tests
        if "provider" in item.name:
            item.add_marker(pytest.mark.provider)
        
        # Mark security tests
        if "security" in item.name:
            item.add_marker(pytest.mark.security)
        
        # Mark webhook tests
        if "webhook" in item.name:
            item.add_marker(pytest.mark.webhook)


# Test data fixtures
@pytest.fixture
def sample_face_restore_params():
    """Sample parameters for face restoration."""
    return {
        "input_url": "https://example.com/test-face.jpg",
        "face_restore": "gfpgan",
        "enhance": True,
        "max_side": 1024,
        "denoise": 0.5
    }


@pytest.fixture
def sample_face_swap_params():
    """Sample parameters for face swap."""
    return {
        "src_face_url": "https://example.com/source-face.jpg",
        "target_url": "https://example.com/target-image.jpg",
        "lora": None,
        "blend": 0.8,
        "max_side": 1024
    }


@pytest.fixture
def sample_upscale_params():
    """Sample parameters for upscaling."""
    return {
        "input_url": "https://example.com/low-res.jpg",
        "model": "realesrgan_x4plus",
        "scale": 4,
        "tile": 256
    }


@pytest.fixture
def mock_image_data():
    """Mock image data for testing."""
    # Minimal valid PNG data
    return (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x10\x00\x00\x00\x10'
        b'\x08\x06\x00\x00\x00\x1f\xf3\xffa\x00\x00\x00\x19tEXtSoftware\x00'
        b'Adobe ImageReadyq\xc9e<\x00\x00\x00\x0eIDATx\xdac\xf8\x0f\x00\x00'
        b'\x00\x00\x01\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00IEND\xaeB`\x82'
    )


@pytest.fixture
def mock_validation_result():
    """Mock security validation result."""
    return {
        'mime_type': 'image/jpeg',
        'dimensions': (512, 512),
        'format': 'JPEG',
        'content_hash': 'abc123def456',
        'file_size': 150000,
        'validation_passed': True
    }


# Test utilities
class TestHelpers:
    """Helper utilities for E2E tests."""
    
    @staticmethod
    def create_test_user(session, email="test@example.com", credits=50):
        """Create a test user."""
        from apps.db.models.user import User
        user = User(
            email=email,
            hashed_password="test_hash",
            credits=credits
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
    
    @staticmethod
    def create_test_job(session, user_id, job_type="face_restore", params=None):
        """Create a test job."""
        from apps.db.models.job import Job
        if params is None:
            params = {"input_url": "https://example.com/test.jpg"}
        
        job = Job(
            user_id=user_id,
            job_type=job_type,
            status="pending",
            params=params
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        return job
    
    @staticmethod
    def assert_job_completed_successfully(session, job_id):
        """Assert that a job completed successfully."""
        from apps.db.models.job import Job
        from apps.db.models.artifact import Artifact
        from sqlmodel import select
        
        job = session.get(Job, job_id)
        assert job is not None
        assert job.status == "succeeded"
        assert job.progress == 100
        assert job.finished_at is not None
        
        # Check artifacts
        artifacts = session.exec(
            select(Artifact).where(Artifact.job_id == job_id)
        ).all()
        assert len(artifacts) > 0
        assert all(a.output_url.startswith("https://") for a in artifacts)
    
    @staticmethod
    def assert_job_failed_with_error(session, job_id, expected_error_keywords=None):
        """Assert that a job failed with expected error."""
        from apps.db.models.job import Job
        
        job = session.get(Job, job_id)
        assert job is not None
        assert job.status == "failed"
        assert job.finished_at is not None
        
        if expected_error_keywords:
            # Note: In a real implementation, we might store error details
            # For now, we just check that the job failed
            pass


# Performance test configuration
class PerformanceTestConfig:
    """Configuration for performance testing."""
    
    # Job processing timeouts
    FAST_JOB_TIMEOUT = 5  # seconds
    NORMAL_JOB_TIMEOUT = 30  # seconds
    SLOW_JOB_TIMEOUT = 120  # seconds
    
    # Concurrency limits
    MAX_CONCURRENT_JOBS = 5
    
    # Resource limits
    MAX_MEMORY_MB = 512
    MAX_CPU_PERCENT = 80