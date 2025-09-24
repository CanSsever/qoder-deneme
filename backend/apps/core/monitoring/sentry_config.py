"""
Sentry integration for OneShot Face Swapper.
Provides exception tracking and performance monitoring.
"""

import os
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
import structlog

logger = structlog.get_logger(__name__)


def init_sentry():
    """Initialize Sentry with comprehensive integrations."""
    dsn = os.getenv("SENTRY_DSN")
    environment = os.getenv("ENVIRONMENT", "development")
    release = os.getenv("RELEASE_VERSION", "unknown")
    
    if not dsn:
        logger.info("Sentry DSN not configured, skipping Sentry initialization")
        return
    
    # Performance sampling configuration
    traces_sample_rate = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))
    profiles_sample_rate = float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1"))
    
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        traces_sample_rate=traces_sample_rate,
        profiles_sample_rate=profiles_sample_rate,
        attach_stacktrace=True,
        send_default_pii=False,  # Don't send PII for privacy
        max_breadcrumbs=50,
        debug=environment == "development",
        integrations=[
            FastApiIntegration(
                auto_tracing=True,
                auto_transaction=True,
                failed_request_status_codes=[400, range(500, 600)],
            ),
            SqlalchemyIntegration(),
            RedisIntegration(),
            CeleryIntegration(
                monitor_beat_tasks=True,
                propagate_traces=True,
            ),
            LoggingIntegration(
                level=None,  # Capture all log levels
                event_level=None,  # Send all log events to Sentry
            ),
        ],
        # Custom tag extraction
        before_send=_before_send_filter,
        before_send_transaction=_before_send_transaction_filter,
    )
    
    # Set global tags
    sentry_sdk.set_tag("service", "oneshot-face-swapper")
    sentry_sdk.set_tag("component", "api")
    
    logger.info(
        "sentry_initialized",
        environment=environment,
        traces_sample_rate=traces_sample_rate,
        profiles_sample_rate=profiles_sample_rate,
    )


def init_sentry_worker():
    """Initialize Sentry for Celery worker with worker-specific configuration."""
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return
    
    environment = os.getenv("ENVIRONMENT", "development")
    release = os.getenv("RELEASE_VERSION", "unknown")
    
    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        traces_sample_rate=0.05,  # Lower sampling for workers
        profiles_sample_rate=0.05,
        attach_stacktrace=True,
        send_default_pii=False,
        integrations=[
            CeleryIntegration(
                monitor_beat_tasks=True,
                propagate_traces=True,
            ),
            RedisIntegration(),
            LoggingIntegration(level=None, event_level=None),
        ],
        before_send=_before_send_filter,
        before_send_transaction=_before_send_transaction_filter,
    )
    
    # Set worker-specific tags
    sentry_sdk.set_tag("service", "oneshot-face-swapper")
    sentry_sdk.set_tag("component", "worker")
    
    logger.info("sentry_worker_initialized", environment=environment)


def _before_send_filter(event, hint):
    """Filter and enrich events before sending to Sentry."""
    # Add custom context
    if "request" in event:
        # Don't send authorization headers
        headers = event.get("request", {}).get("headers", {})
        if "authorization" in headers:
            headers["authorization"] = "[Filtered]"
    
    # Skip health check endpoints
    if event.get("transaction") in ["/healthz", "/readyz", "/metrics"]:
        return None
    
    # Add job context if available
    if "extra" in event:
        job_id = event["extra"].get("job_id")
        if job_id:
            sentry_sdk.set_tag("job_id", job_id)
    
    return event


def _before_send_transaction_filter(event, hint):
    """Filter transactions before sending to Sentry."""
    # Skip health check transactions
    transaction_name = event.get("transaction")
    if transaction_name in ["/healthz", "/readyz", "/metrics"]:
        return None
    
    # Sample high-frequency transactions
    if transaction_name and transaction_name.startswith("/api/v1/jobs/"):
        # Reduce sampling for frequent job status checks
        import random
        if random.random() > 0.1:  # 10% sampling
            return None
    
    return event


def capture_job_context(job_id: str, user_id: str = None, pipeline: str = None):
    """Set job context for current Sentry scope."""
    with sentry_sdk.configure_scope() as scope:
        scope.set_tag("job_id", job_id)
        if user_id:
            scope.set_user({"id": user_id})
        if pipeline:
            scope.set_tag("pipeline", pipeline)


def capture_provider_context(provider: str, remote_id: str = None):
    """Set provider context for current Sentry scope."""
    with sentry_sdk.configure_scope() as scope:
        scope.set_tag("gpu_provider", provider)
        if remote_id:
            scope.set_tag("remote_job_id", remote_id)


def capture_performance_metrics(operation: str, duration_ms: float, **kwargs):
    """Capture custom performance metrics."""
    with sentry_sdk.configure_scope() as scope:
        scope.set_extra("operation", operation)
        scope.set_extra("duration_ms", duration_ms)
        for key, value in kwargs.items():
            scope.set_extra(key, value)