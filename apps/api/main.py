"""
Advanced FastAPI application setup with monitoring, rate limiting, and comprehensive error handling.
"""
import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from prometheus_fastapi_instrumentator import Instrumentator
from apps.core.settings import settings
from apps.core.exceptions import (
    oneshot_exception_handler,
    validation_exception_handler, 
    general_exception_handler,
    OneShotException
)
from apps.db.session import create_db_and_tables

# Setup structured logging
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

logger = structlog.get_logger()

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address, storage_uri=settings.redis_url)


def create_application() -> FastAPI:
    """Create and configure advanced FastAPI application."""
    
    app = FastAPI(
        title="OneShot Face Swapper API",
        description="Advanced AI-powered face swapping and restoration service with monitoring",
        version="2.0.0",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
    )
    
    # Add rate limiting state
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    # Add middleware
    setup_middleware(app)
    
    # Add monitoring
    setup_monitoring(app)
    
    # Add exception handlers
    setup_exception_handlers(app)
    
    # Include routers
    setup_routers(app)
    
    # Setup event handlers
    setup_event_handlers(app)
    
    return app


def setup_middleware(app: FastAPI):
    """Setup application middleware."""
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )
    
    # Trusted host middleware (for production)
    if settings.is_production:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*.oneshot.ai", "localhost", "127.0.0.1"]
        )


def setup_monitoring(app: FastAPI):
    """Setup Prometheus monitoring."""
    instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        should_instrument_requests_inprogress=True,
        excluded_handlers=["/metrics"],
        env_var_name="ENABLE_METRICS",
        inprogress_name="oneshot_requests_inprogress",
        inprogress_labels=True,
    )
    
    instrumentator.instrument(app).expose(app, endpoint="/metrics")


def setup_exception_handlers(app: FastAPI):
    """Setup comprehensive exception handlers."""
    
    app.add_exception_handler(OneShotException, oneshot_exception_handler)
    app.add_exception_handler(Exception, general_exception_handler)
    
    @app.exception_handler(422)
    async def validation_exception_handler_422(request: Request, exc):
        """Handle validation errors with detailed response."""
        logger.error("Validation error", 
                    path=request.url.path,
                    method=request.method,
                    errors=str(exc))
        
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Input validation failed",
                    "details": str(exc)
                }
            }
        )


def setup_routers(app: FastAPI):
    """Setup API routers with rate limiting."""
    
    from apps.api.routers import auth, uploads, jobs, billing
    
    # Include routers with API prefix
    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(uploads.router, prefix="/api/v1")
    app.include_router(jobs.router, prefix="/api/v1")
    app.include_router(billing.router, prefix="/api/v1")
    
    # Health check endpoint with rate limiting
    @app.get("/health")
    @limiter.limit("100/minute")
    async def health_check(request: Request):
        """Health check endpoint with monitoring."""
        logger.info("Health check requested", remote_addr=get_remote_address(request))
        return {
            "status": "healthy", 
            "version": "2.0.0",
            "environment": settings.environment
        }
    
    # Root endpoint
    @app.get("/")
    @limiter.limit("60/minute")
    async def root(request: Request):
        """Root endpoint with API information."""
        return {
            "message": "OneShot Face Swapper API v2.0",
            "version": "2.0.0",
            "docs": "/docs" if settings.is_development else "Contact admin for API documentation",
            "features": [
                "Advanced AI Processing",
                "Rate Limiting", 
                "Monitoring & Metrics",
                "Structured Logging"
            ]
        }


def setup_event_handlers(app: FastAPI):
    """Setup application event handlers."""
    
    @app.on_event("startup")
    async def startup_event():
        """Application startup event with logging."""
        logger.info("OneShot API v2.0 starting up", 
                   environment=settings.environment,
                   database_url=settings.database_url[:20] + "...")
        
        # Create database tables
        create_db_and_tables()
        
        # Apply pending migrations
        try:
            import subprocess
            result = subprocess.run(
                ["python", "-c", "from alembic.config import Config; from alembic import command; cfg = Config('alembic.ini'); command.upgrade(cfg, 'head')"],
                capture_output=True,
                text=True,
                cwd="."
            )
            if result.returncode == 0:
                logger.info("Database migrations applied successfully")
            else:
                logger.warning("Migration check failed", error=result.stderr)
        except Exception as e:
            logger.warning("Could not run migrations", error=str(e))
        
        logger.info("OneShot API v2.0 started successfully")
    
    @app.on_event("shutdown")
    async def shutdown_event():
        """Application shutdown event."""
        logger.info("OneShot API v2.0 shutting down")


# Create application instance
app = create_application()