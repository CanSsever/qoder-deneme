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
import time

from apps.core.settings import settings
from apps.core.exceptions import (
    oneshot_exception_handler,
    validation_exception_handler, 
    general_exception_handler,
    OneShotException
)
from apps.core.monitoring import (
    init_sentry,
    metrics,
    increment_http_requests,
    observe_http_request_duration
)
from apps.core.monitoring.health_checks import basic_health_check, readiness_check

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

# Initialize rate limiter with fallback
RATE_LIMITING_ENABLED = getattr(settings, 'enable_rate_limiting', True)

if RATE_LIMITING_ENABLED:
    try:
        limiter = Limiter(key_func=get_remote_address, storage_uri=settings.redis_url)
        logger.info("Rate limiting enabled with Redis")
    except Exception as e:
        logger.warning("Rate limiting disabled due to Redis connection error", error=str(e))
        RATE_LIMITING_ENABLED = False
        limiter = None
else:
    logger.info("Rate limiting disabled via configuration")
    limiter = None


def create_application() -> FastAPI:
    """Create and configure advanced FastAPI application."""
    
    app = FastAPI(
        title="OneShot Face Swapper API",
        description="Advanced AI-powered face swapping and restoration service with monitoring",
        version="2.0.0",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
    )
    
    # Add rate limiting state only if enabled
    if RATE_LIMITING_ENABLED and limiter:
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
    """Setup application middleware with production-grade security."""
    
    # Production CORS configuration (strict)
    if settings.is_production:
        # Production: Strict CORS with specific domains only
        cors_origins = [
            "https://yourdomain.com",
            "https://www.yourdomain.com", 
            "https://app.yourdomain.com"
        ]
        cors_credentials = True
        cors_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
        cors_headers = [
            "Authorization",
            "Content-Type", 
            "X-Requested-With",
            "Accept",
            "Origin"
        ]
        logger.info("Production CORS configured", allowed_origins=cors_origins)
    else:
        # Development: Permissive CORS
        cors_origins = settings.allowed_origins
        cors_credentials = True
        cors_methods = ["GET", "POST", "PUT", "DELETE"]
        cors_headers = ["*"]
        logger.info("Development CORS configured", allowed_origins=cors_origins)
    
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=cors_credentials,
        allow_methods=cors_methods,
        allow_headers=cors_headers,
        max_age=3600 if settings.is_production else 600,  # Cache preflight longer in prod
    )
    
    # Trusted host middleware (production only)
    if settings.is_production:
        # Configure trusted hosts for production
        trusted_hosts = [
            "yourdomain.com",
            "*.yourdomain.com",
            "api.yourdomain.com",
            "app.yourdomain.com"
        ]
        
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=trusted_hosts
        )
        logger.info("Trusted host middleware enabled", hosts=trusted_hosts)


def setup_monitoring(app: FastAPI):
    """Setup comprehensive monitoring with Prometheus and custom metrics."""
    
    # Initialize Sentry for error tracking
    init_sentry()
    
    # Custom middleware for request metrics
    @app.middleware("http")
    async def metrics_middleware(request: Request, call_next):
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Record metrics
        duration = time.time() - start_time
        method = request.method
        endpoint = request.url.path
        status_code = str(response.status_code)
        
        increment_http_requests(method, endpoint, status_code)
        observe_http_request_duration(method, endpoint, duration)
        
        return response
    
    # Setup Prometheus instrumentator
    instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        should_instrument_requests_inprogress=True,
        excluded_handlers=["/metrics", "/healthz", "/readyz"],
        env_var_name="ENABLE_METRICS",
        inprogress_name="oneshot_requests_inprogress",
        inprogress_labels=True,
    )
    
    instrumentator.instrument(app)
    
    # Custom metrics endpoint
    @app.get("/metrics")
    async def get_metrics():
        """Expose Prometheus metrics."""
        return metrics.get_metrics_response()


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
    
    # Import all routers
    from apps.api.routers import auth, jobs, uploads, credits
    
    # Include routers with API prefix
    app.include_router(auth.router, prefix="/api")
    app.include_router(jobs.router, prefix="/api")
    app.include_router(uploads.router, prefix="/api")
    app.include_router(credits.router, prefix="/api")
    
    # Enhanced health check endpoints (without rate limiting if Redis unavailable)
    if RATE_LIMITING_ENABLED:
        @app.get("/healthz")
        @limiter.limit("200/minute")
        async def health_check(request: Request):
            """Basic health check endpoint."""
            logger.info("Health check requested", remote_addr=get_remote_address(request))
            return await basic_health_check()
        
        @app.get("/readyz")
        @limiter.limit("100/minute")
        async def readiness_check_endpoint(request: Request):
            """Comprehensive readiness check with dependency verification."""
            logger.info("Readiness check requested", remote_addr=get_remote_address(request))
            return await readiness_check()
        
        @app.get("/health")
        @limiter.limit("100/minute")
        async def legacy_health_check(request: Request):
            """Legacy health check endpoint."""
            return await basic_health_check()
        
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
    else:
        @app.get("/healthz")
        async def health_check(request: Request):
            """Basic health check endpoint."""
            logger.info("Health check requested", remote_addr=get_remote_address(request))
            return await basic_health_check()
        
        @app.get("/readyz")
        async def readiness_check_endpoint(request: Request):
            """Comprehensive readiness check with dependency verification."""
            logger.info("Readiness check requested", remote_addr=get_remote_address(request))
            return await readiness_check()
        
        @app.get("/health")
        async def legacy_health_check(request: Request):
            """Legacy health check endpoint."""
            return await basic_health_check()
        
        @app.get("/")
        async def root(request: Request):
            """Root endpoint with API information."""
            return {
                "message": "OneShot Face Swapper API v2.0",
                "version": "2.0.0",
                "docs": "/docs" if settings.is_development else "Contact admin for API documentation",
                "features": [
                    "Advanced AI Processing",
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
                   supabase_url=settings.supabase_url[:30] + "...")
        
        # Test Supabase connection
        try:
            from apps.core.supabase_client import supabase_client
            if supabase_client.health_check():
                logger.info("Supabase connection healthy")
            else:
                logger.warning("Supabase connection check failed")
        except Exception as e:
            logger.error("Supabase connection error", error=str(e))
        
        logger.info("OneShot API v2.0 started successfully")
    
    @app.on_event("shutdown")
    async def shutdown_event():
        """Application shutdown event."""
        logger.info("OneShot API v2.0 shutting down")


# Create application instance
app = create_application()