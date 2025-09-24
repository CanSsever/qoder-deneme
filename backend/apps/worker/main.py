"""
Worker main entry point for background processing.
"""
import structlog
from apps.worker.tasks import celery_app
from apps.core.monitoring import init_sentry_worker

# Initialize Sentry for worker
init_sentry_worker()

# Configure structured logging for worker
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO level
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

if __name__ == '__main__':
    logger.info("Starting OneShot worker with monitoring")
    celery_app.start()