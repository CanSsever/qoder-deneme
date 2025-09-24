"""
Monitoring and observability package for OneShot Face Swapper.
"""

from .sentry_config import init_sentry, init_sentry_worker, capture_job_context, capture_provider_context
from .prometheus_metrics import (
    metrics,
    increment_job_counter,
    observe_job_latency,
    set_queue_depth,
    increment_provider_error,
    increment_http_requests,
    observe_http_request_duration,
    set_concurrent_jobs,
    increment_webhook_events,
)

__all__ = [
    "init_sentry",
    "init_sentry_worker", 
    "capture_job_context",
    "capture_provider_context",
    "metrics",
    "increment_job_counter",
    "observe_job_latency",
    "set_queue_depth",
    "increment_provider_error",
    "increment_http_requests",
    "observe_http_request_duration",
    "set_concurrent_jobs",
    "increment_webhook_events",
]