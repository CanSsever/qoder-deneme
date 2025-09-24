"""
Prometheus metrics for OneShot Face Swapper.
Provides comprehensive monitoring of jobs, queues, providers, and performance.
"""

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, CONTENT_TYPE_LATEST, generate_latest
from fastapi import Response
import time
import structlog

logger = structlog.get_logger(__name__)

# Create custom registry for our metrics
registry = CollectorRegistry()

# Job Processing Metrics
job_total = Counter(
    'oneshot_jobs_total',
    'Total number of jobs processed',
    ['pipeline', 'status', 'provider'],
    registry=registry
)

job_duration = Histogram(
    'oneshot_job_duration_seconds',
    'Job processing duration in seconds',
    ['pipeline', 'provider', 'status'],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0, 1200.0, float('inf')],
    registry=registry
)

# Queue Metrics
queue_depth = Gauge(
    'oneshot_queue_depth',
    'Number of jobs waiting in queue',
    ['queue_name'],
    registry=registry
)

concurrent_jobs = Gauge(
    'oneshot_concurrent_jobs',
    'Number of jobs currently being processed',
    ['provider'],
    registry=registry
)

# Provider Metrics
provider_errors = Counter(
    'oneshot_provider_errors_total',
    'Total number of provider errors',
    ['provider', 'error_type'],
    registry=registry
)

provider_request_duration = Histogram(
    'oneshot_provider_request_duration_seconds',
    'Provider request duration in seconds',
    ['provider', 'operation'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0, 50.0, float('inf')],
    registry=registry
)

# HTTP Metrics
http_requests_total = Counter(
    'oneshot_http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code'],
    registry=registry
)

http_request_duration = Histogram(
    'oneshot_http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint'],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0, float('inf')],
    registry=registry
)

# Database Metrics
db_operations = Counter(
    'oneshot_db_operations_total',
    'Total database operations',
    ['operation', 'table'],
    registry=registry
)

db_operation_duration = Histogram(
    'oneshot_db_operation_duration_seconds',
    'Database operation duration in seconds',
    ['operation', 'table'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, float('inf')],
    registry=registry
)

# Cache Metrics
cache_operations = Counter(
    'oneshot_cache_operations_total',
    'Total cache operations',
    ['operation', 'result'],
    registry=registry
)

# Webhook Metrics
webhook_events = Counter(
    'oneshot_webhook_events_total',
    'Total webhook events processed',
    ['event_type', 'status'],
    registry=registry
)

# Authentication Metrics
auth_operations = Counter(
    'oneshot_auth_operations_total',
    'Total authentication operations',
    ['operation', 'result'],
    registry=registry
)

# Health Check Metrics
health_check_duration = Histogram(
    'oneshot_health_check_duration_seconds',
    'Health check duration in seconds',
    ['check_type', 'service'],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, float('inf')],
    registry=registry
)

health_check_status = Gauge(
    'oneshot_health_check_status',
    'Health check status (1=healthy, 0=unhealthy)',
    ['service'],
    registry=registry
)

# Business Metrics
active_users = Gauge(
    'oneshot_active_users',
    'Number of active users',
    ['time_window'],
    registry=registry
)

credits_consumed = Counter(
    'oneshot_credits_consumed_total',
    'Total credits consumed',
    ['user_plan'],
    registry=registry
)


class MetricsCollector:
    """Centralized metrics collection and helper methods."""
    
    def __init__(self):
        self.registry = registry
    
    def get_metrics_response(self) -> Response:
        """Return Prometheus metrics as HTTP response."""
        metrics_data = generate_latest(self.registry)
        return Response(
            content=metrics_data,
            media_type=CONTENT_TYPE_LATEST
        )


# Global metrics collector instance
metrics = MetricsCollector()


# Helper functions for common metric operations
def increment_job_counter(pipeline: str, status: str, provider: str):
    """Increment job counter with labels."""
    job_total.labels(pipeline=pipeline, status=status, provider=provider).inc()
    logger.debug(
        "job_counter_incremented",
        pipeline=pipeline,
        status=status,
        provider=provider
    )


def observe_job_latency(pipeline: str, provider: str, status: str, duration_seconds: float):
    """Record job processing latency."""
    job_duration.labels(pipeline=pipeline, provider=provider, status=status).observe(duration_seconds)
    logger.debug(
        "job_latency_recorded",
        pipeline=pipeline,
        provider=provider,
        status=status,
        duration_seconds=duration_seconds
    )


def set_queue_depth(queue_name: str, depth: int):
    """Set current queue depth."""
    queue_depth.labels(queue_name=queue_name).set(depth)


def set_concurrent_jobs(provider: str, count: int):
    """Set current concurrent job count."""
    concurrent_jobs.labels(provider=provider).set(count)


def increment_provider_error(provider: str, error_type: str):
    """Increment provider error counter."""
    provider_errors.labels(provider=provider, error_type=error_type).inc()
    logger.warning(
        "provider_error_recorded",
        provider=provider,
        error_type=error_type
    )


def observe_provider_request_duration(provider: str, operation: str, duration_seconds: float):
    """Record provider request duration."""
    provider_request_duration.labels(provider=provider, operation=operation).observe(duration_seconds)


def increment_http_requests(method: str, endpoint: str, status_code: str):
    """Increment HTTP request counter."""
    http_requests_total.labels(method=method, endpoint=endpoint, status_code=status_code).inc()


def observe_http_request_duration(method: str, endpoint: str, duration_seconds: float):
    """Record HTTP request duration."""
    http_request_duration.labels(method=method, endpoint=endpoint).observe(duration_seconds)


def increment_db_operations(operation: str, table: str):
    """Increment database operation counter."""
    db_operations.labels(operation=operation, table=table).inc()


def observe_db_operation_duration(operation: str, table: str, duration_seconds: float):
    """Record database operation duration."""
    db_operation_duration.labels(operation=operation, table=table).observe(duration_seconds)


def increment_cache_operations(operation: str, result: str):
    """Increment cache operation counter."""
    cache_operations.labels(operation=operation, result=result).inc()


def increment_webhook_events(event_type: str, status: str):
    """Increment webhook event counter."""
    webhook_events.labels(event_type=event_type, status=status).inc()


def increment_auth_operations(operation: str, result: str):
    """Increment authentication operation counter."""
    auth_operations.labels(operation=operation, result=result).inc()


def observe_health_check_duration(check_type: str, service: str, duration_seconds: float):
    """Record health check duration."""
    health_check_duration.labels(check_type=check_type, service=service).observe(duration_seconds)


def set_health_check_status(service: str, is_healthy: bool):
    """Set health check status."""
    health_check_status.labels(service=service).set(1 if is_healthy else 0)


def set_active_users(time_window: str, count: int):
    """Set active user count."""
    active_users.labels(time_window=time_window).set(count)


def increment_credits_consumed(user_plan: str, amount: int = 1):
    """Increment credits consumed counter."""
    credits_consumed.labels(user_plan=user_plan).inc(amount)


# Context managers for automatic metric recording
class JobMetricsContext:
    """Context manager for automatic job metrics recording."""
    
    def __init__(self, pipeline: str, provider: str, job_id: str = None):
        self.pipeline = pipeline
        self.provider = provider
        self.job_id = job_id
        self.start_time = None
        self.status = "unknown"
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            self.status = "failed" if exc_type else "completed"
            observe_job_latency(self.pipeline, self.provider, self.status, duration)
            increment_job_counter(self.pipeline, self.status, self.provider)


class ProviderMetricsContext:
    """Context manager for automatic provider metrics recording."""
    
    def __init__(self, provider: str, operation: str):
        self.provider = provider
        self.operation = operation
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            observe_provider_request_duration(self.provider, self.operation, duration)
            if exc_type:
                error_type = exc_type.__name__ if exc_type else "unknown"
                increment_provider_error(self.provider, error_type)