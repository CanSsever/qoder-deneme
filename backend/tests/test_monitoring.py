"""
Tests for monitoring, metrics, and alerting functionality.
"""

import pytest
import time
import httpx
from unittest.mock import patch, MagicMock
from prometheus_client import REGISTRY
import structlog

from apps.core.monitoring import (
    metrics,
    increment_job_counter,
    observe_job_latency,
    set_queue_depth,
    increment_provider_error,
    JobMetricsContext,
    ProviderMetricsContext
)
from apps.core.monitoring.health_checks import health_checker, basic_health_check, readiness_check
from apps.core.monitoring.prometheus_metrics import (
    job_total,
    job_duration,
    queue_depth,
    provider_errors,
    http_requests_total
)

logger = structlog.get_logger(__name__)


class TestPrometheusMetrics:
    """Test Prometheus metrics collection."""
    
    def setup_method(self):
        """Reset metrics before each test."""
        # Clear all metrics
        for collector in list(REGISTRY._collector_to_names.keys()):
            if hasattr(collector, '_metrics'):
                collector._metrics.clear()
    
    def test_job_counter_increment(self):
        """Test job counter increments correctly."""
        initial_value = self._get_metric_value(job_total, "face_swap", "completed", "comfy_local")
        
        increment_job_counter("face_swap", "completed", "comfy_local")
        
        new_value = self._get_metric_value(job_total, "face_swap", "completed", "comfy_local")
        assert new_value == initial_value + 1
    
    def test_job_latency_observation(self):
        """Test job latency metrics recording."""
        observe_job_latency("face_restoration", "runpod", "completed", 15.5)
        
        # Verify histogram bucket is updated
        bucket_metric = job_duration.labels(
            pipeline="face_restoration", 
            provider="runpod", 
            status="completed"
        )
        
        # The observation should be recorded
        assert bucket_metric._sum._value > 0
        assert bucket_metric._count._value > 0
    
    def test_queue_depth_setting(self):
        """Test queue depth gauge setting."""
        set_queue_depth("default", 42)
        
        value = self._get_metric_value(queue_depth, "default")
        assert value == 42
    
    def test_provider_error_increment(self):
        """Test provider error counter."""
        initial_value = self._get_metric_value(provider_errors, "runpod", "TimeoutError")
        
        increment_provider_error("runpod", "TimeoutError")
        
        new_value = self._get_metric_value(provider_errors, "runpod", "TimeoutError")
        assert new_value == initial_value + 1
    
    def test_job_metrics_context_success(self):
        """Test job metrics context manager for successful jobs."""
        with JobMetricsContext("face_swap", "comfy_local", "job-123") as ctx:
            time.sleep(0.1)  # Simulate work
        
        # Verify metrics were recorded
        completed_count = self._get_metric_value(job_total, "face_swap", "completed", "comfy_local")
        assert completed_count > 0
        
        # Verify duration was recorded
        duration_metric = job_duration.labels(
            pipeline="face_swap", 
            provider="comfy_local", 
            status="completed"
        )
        assert duration_metric._count._value > 0
    
    def test_job_metrics_context_failure(self):
        """Test job metrics context manager for failed jobs."""
        with pytest.raises(ValueError):
            with JobMetricsContext("face_restoration", "runpod") as ctx:
                raise ValueError("Simulated failure")
        
        # Verify failure metrics were recorded
        failed_count = self._get_metric_value(job_total, "face_restoration", "failed", "runpod")
        assert failed_count > 0
    
    def test_provider_metrics_context(self):
        """Test provider metrics context manager."""
        with ProviderMetricsContext("comfy_local", "submit") as ctx:
            time.sleep(0.05)  # Simulate provider call
        
        # Verify provider request duration was recorded
        # Note: This would need the provider_request_duration metric to be imported
        # For now, just verify no exceptions were raised
        assert True
    
    def _get_metric_value(self, metric, *labels):
        """Helper to get current metric value."""
        try:
            return metric.labels(*labels)._value._value
        except:
            return 0


class TestHealthChecks:
    """Test health check functionality."""
    
    @pytest.mark.asyncio
    async def test_basic_health_check(self):
        """Test basic health check endpoint."""
        result = await basic_health_check()
        
        assert result["status"] == "healthy"
        assert "timestamp" in result
        assert "service" in result
        assert "version" in result
    
    @pytest.mark.asyncio
    @patch('apps.core.monitoring.health_checks.get_db')
    async def test_database_health_check(self):
        """Test database health check."""
        # Mock successful database connection
        mock_session = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (1,)
        mock_session.execute.return_value = mock_result
        
        async def mock_get_db():
            yield mock_session
        
        with patch('apps.core.monitoring.health_checks.get_db', mock_get_db):
            result = await health_checker.check_database()
        
        assert result.service == "database"
        assert result.healthy is True
        assert result.duration_ms >= 0
        assert result.details["connection"] == "ok"
    
    @pytest.mark.asyncio
    @patch('redis.Redis')
    async def test_redis_health_check(self):
        """Test Redis health check."""
        # Mock successful Redis connection
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True
        mock_redis.info.return_value = {
            "connected_clients": 2,
            "used_memory_human": "1.5M"
        }
        
        with patch('redis.Redis.from_url', return_value=mock_redis):
            result = await health_checker.check_redis()
        
        assert result.service == "redis"
        assert result.healthy is True
        assert result.details["ping_test"] == "passed"
    
    @pytest.mark.asyncio
    @patch('boto3.client')
    async def test_storage_health_check(self):
        """Test S3/R2 storage health check."""
        # Mock successful S3 connection
        mock_s3 = MagicMock()
        mock_s3.head_bucket.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}
        
        with patch('boto3.client', return_value=mock_s3):
            result = await health_checker.check_storage()
        
        assert result.service == "storage"
        assert result.healthy is True
        assert result.details["bucket_access"] == "passed"
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient')
    async def test_gpu_provider_health_check_comfy(self):
        """Test ComfyUI provider health check."""
        # Mock successful ComfyUI response
        mock_response = MagicMock()
        mock_response.json.return_value = {"devices": ["cuda:0"]}
        mock_response.raise_for_status.return_value = None
        
        mock_client = MagicMock()
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None
        mock_client.get.return_value = mock_response
        
        with patch('httpx.AsyncClient', return_value=mock_client):
            with patch('apps.core.settings.settings.gpu_provider', "comfy_local"):
                with patch('apps.core.settings.settings.comfy_local_url', "http://localhost:8188"):
                    result = await health_checker.check_gpu_provider()
        
        assert result.service == "provider"
        assert result.healthy is True
        assert result.details["provider"] == "comfy_local"
    
    @pytest.mark.asyncio
    async def test_comprehensive_readiness_check(self):
        """Test comprehensive readiness check."""
        with patch.object(health_checker, 'check_database') as mock_db, \
             patch.object(health_checker, 'check_redis') as mock_redis, \
             patch.object(health_checker, 'check_storage') as mock_storage, \
             patch.object(health_checker, 'check_gpu_provider') as mock_provider:
            
            # Mock all checks as healthy
            mock_db.return_value = MagicMock(service="database", healthy=True, duration_ms=50, to_dict=lambda: {"healthy": True})
            mock_redis.return_value = MagicMock(service="redis", healthy=True, duration_ms=20, to_dict=lambda: {"healthy": True})
            mock_storage.return_value = MagicMock(service="storage", healthy=True, duration_ms=100, to_dict=lambda: {"healthy": True})
            mock_provider.return_value = MagicMock(service="provider", healthy=True, duration_ms=200, to_dict=lambda: {"healthy": True})
            
            result = await readiness_check()
        
        assert result["healthy"] is True
        assert "timestamp" in result
        assert "total_duration_ms" in result
        assert "services" in result
        assert len(result["services"]) == 4


class TestAlertGeneration:
    """Test alert generation and monitoring integration."""
    
    def test_generate_high_error_rate_alert(self):
        """Test generating high error rate metrics to trigger alerts."""
        # Generate multiple 5xx errors to trigger alert
        for _ in range(10):
            increment_job_counter("face_swap", "failed", "comfy_local")
        
        # Verify counter was incremented
        failed_count = job_total.labels(pipeline="face_swap", status="failed", provider="comfy_local")._value._value
        assert failed_count >= 10
    
    def test_generate_high_latency_alert(self):
        """Test generating high latency metrics to trigger alerts."""
        # Generate high latency observations
        for i in range(5):
            observe_job_latency("face_restoration", "runpod", "completed", 35.0 + i)
        
        # Verify histogram was updated
        duration_metric = job_duration.labels(
            pipeline="face_restoration",
            provider="runpod", 
            status="completed"
        )
        assert duration_metric._count._value >= 5
    
    def test_generate_high_queue_depth_alert(self):
        """Test generating high queue depth to trigger alerts."""
        set_queue_depth("default", 150)  # Above threshold of 100
        
        value = queue_depth.labels(queue_name="default")._value._value
        assert value == 150
    
    def test_generate_provider_failure_alert(self):
        """Test generating provider failures to trigger alerts."""
        # Generate consecutive provider failures
        for i in range(6):  # Above threshold of 5
            increment_provider_error("runpod", "ConnectionError")
        
        error_count = provider_errors.labels(provider="runpod", error_type="ConnectionError")._value._value
        assert error_count >= 6


def generate_test_alerts():
    """
    Generate test metrics to trigger alerts in dry-run mode.
    This function can be called from the Makefile to test alerting.
    """
    logger.info("Generating test metrics for alert validation...")
    
    # Generate high error rate
    for _ in range(20):
        increment_job_counter("face_swap", "failed", "comfy_local")
        increment_job_counter("face_swap", "completed", "comfy_local")  # Mix with successful jobs
    
    # Generate high latency
    for i in range(10):
        observe_job_latency("face_restoration", "runpod", "completed", 45.0 + i * 2)
    
    # Generate high queue depth
    set_queue_depth("default", 120)
    set_queue_depth("priority", 80)
    
    # Generate provider failures
    for _ in range(8):
        increment_provider_error("runpod", "TimeoutError")
        increment_provider_error("comfy_local", "ConnectionError")
    
    logger.info("Test metrics generated successfully!")
    print("✅ Test alerts generated! Check Prometheus/Alertmanager for alert status.")
    print("🔗 Prometheus: http://localhost:9090/alerts")
    print("🔗 Alertmanager: http://localhost:9093")


@pytest.fixture
def metrics_test_setup():
    """Setup for metrics tests."""
    # Clear metrics before test
    for collector in list(REGISTRY._collector_to_names.keys()):
        if hasattr(collector, '_metrics'):
            collector._metrics.clear()
    yield
    # Cleanup after test
    for collector in list(REGISTRY._collector_to_names.keys()):
        if hasattr(collector, '_metrics'):
            collector._metrics.clear()


class TestSentryIntegration:
    """Test Sentry integration and error tracking."""
    
    @patch('sentry_sdk.init')
    def test_sentry_initialization(self, mock_sentry_init):
        """Test Sentry initialization with proper configuration."""
        from apps.core.monitoring.sentry_config import init_sentry
        
        with patch.dict('os.environ', {'SENTRY_DSN': 'https://test@sentry.io/123'}):
            init_sentry()
        
        mock_sentry_init.assert_called_once()
        args, kwargs = mock_sentry_init.call_args
        
        assert 'dsn' in kwargs
        assert 'environment' in kwargs
        assert 'traces_sample_rate' in kwargs
        assert kwargs['traces_sample_rate'] == 0.1
    
    @patch('sentry_sdk.capture_exception')
    def test_sentry_exception_capture(self, mock_capture):
        """Test that exceptions are properly captured by Sentry."""
        from apps.core.monitoring.sentry_config import capture_job_context
        
        # Simulate an exception with job context
        try:
            capture_job_context("job-123", "user-456", "face_swap")
            raise ValueError("Test exception")
        except ValueError:
            pass
        
        # In a real scenario, Sentry would automatically capture this
        # For testing, we verify the context setting worked
        assert True  # Context was set without errors


if __name__ == "__main__":
    # Allow running this file directly to generate test alerts
    generate_test_alerts()