"""
Enhanced health check system with detailed timings and dependency monitoring.
"""

import asyncio
import time
from typing import Dict, Any, Optional
import structlog
from sqlalchemy import text
from redis import Redis
import boto3
from botocore.exceptions import BotoCoreError, ClientError
import httpx

from apps.db.session import get_session
from apps.core.settings import settings
from .prometheus_metrics import observe_health_check_duration, set_health_check_status

logger = structlog.get_logger(__name__)
# Global settings instance
settings = settings


class HealthCheckResult:
    """Result of a health check with timing and status information."""
    
    def __init__(self, service: str, healthy: bool, duration_ms: float, 
                 details: Optional[Dict[str, Any]] = None, error: Optional[str] = None):
        self.service = service
        self.healthy = healthy
        self.duration_ms = duration_ms
        self.details = details or {}
        self.error = error
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "service": self.service,
            "healthy": self.healthy,
            "duration_ms": round(self.duration_ms, 2),
            "details": self.details,
            "error": self.error,
        }


class HealthChecker:
    """Comprehensive health checking system with configurable thresholds."""
    
    def __init__(self):
        # Health check thresholds (in milliseconds)
        self.thresholds = {
            "database": 1000,  # 1 second
            "redis": 500,      # 500ms
            "storage": 2000,   # 2 seconds
            "provider": 5000,  # 5 seconds
        }
        
        # Failure thresholds
        self.failure_thresholds = {
            "database": 3,  # Fail after 3 consecutive failures
            "redis": 3,
            "storage": 2,
            "provider": 1,
        }
        
        self.failure_counts = {service: 0 for service in self.thresholds.keys()}
    
    async def check_database(self) -> HealthCheckResult:
        """Check database connectivity and response time."""
        start_time = time.time()
        
        try:
            # Use a simple query to test connectivity
            session = next(get_session())
            result = session.execute(text("SELECT 1"))
            row = result.fetchone()
                
            if row and row[0] == 1:
                duration_ms = (time.time() - start_time) * 1000
                healthy = duration_ms < self.thresholds["database"]
                
                details = {
                    "connection": "ok",
                    "query_test": "passed",
                    "threshold_ms": self.thresholds["database"],
                }
                
                if healthy:
                    self.failure_counts["database"] = 0
                else:
                    self.failure_counts["database"] += 1
                
                observe_health_check_duration("readiness", "database", duration_ms / 1000)
                set_health_check_status("database", healthy)
                
                return HealthCheckResult(
                    service="database",
                    healthy=healthy,
                    duration_ms=duration_ms,
                    details=details
                )
            else:
                raise Exception("Database query test failed")
                    
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.failure_counts["database"] += 1
            
            observe_health_check_duration("readiness", "database", duration_ms / 1000)
            set_health_check_status("database", False)
            
            return HealthCheckResult(
                service="database",
                healthy=False,
                duration_ms=duration_ms,
                error=str(e)
            )
    
    async def check_redis(self) -> HealthCheckResult:
        """Check Redis connectivity and response time."""
        start_time = time.time()
        redis_client = None
        
        try:
            redis_client = Redis.from_url(settings.redis_url)
            
            # Test basic connectivity
            pong = redis_client.ping()
            
            if pong:
                duration_ms = (time.time() - start_time) * 1000
                healthy = duration_ms < self.thresholds["redis"]
                
                # Get Redis info
                # info = redis_client.info()
                
                details = {
                    "connection": "ok",
                    "ping_test": "passed",
                    "threshold_ms": self.thresholds["redis"],
                }
                
                if healthy:
                    self.failure_counts["redis"] = 0
                else:
                    self.failure_counts["redis"] += 1
                
                observe_health_check_duration("readiness", "redis", duration_ms / 1000)
                set_health_check_status("redis", healthy)
                
                return HealthCheckResult(
                    service="redis",
                    healthy=healthy,
                    duration_ms=duration_ms,
                    details=details
                )
            else:
                raise Exception("Redis ping failed")
                
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.failure_counts["redis"] += 1
            
            observe_health_check_duration("readiness", "redis", duration_ms / 1000)
            set_health_check_status("redis", False)
            
            return HealthCheckResult(
                service="redis",
                healthy=False,
                duration_ms=duration_ms,
                error=str(e)
            )
        finally:
            if redis_client:
                try:
                    redis_client.close()
                except:
                    pass
    
    async def check_storage(self) -> HealthCheckResult:
        """Check S3/R2 storage connectivity and response time."""
        start_time = time.time()
        
        try:
            # Create S3 client
            s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.s3_key,
                aws_secret_access_key=settings.s3_secret,
                region_name=settings.s3_region,
                endpoint_url=getattr(settings, 's3_endpoint_url', None),
            )
            
            # Test bucket access
            response = s3_client.head_bucket(Bucket=settings.s3_bucket_name)
            
            duration_ms = (time.time() - start_time) * 1000
            healthy = duration_ms < self.thresholds["storage"]
            
            details = {
                "connection": "ok",
                "bucket_access": "passed",
                "bucket_name": settings.s3_bucket_name,
                "threshold_ms": self.thresholds["storage"],
            }
            
            if healthy:
                self.failure_counts["storage"] = 0
            else:
                self.failure_counts["storage"] += 1
            
            observe_health_check_duration("readiness", "storage", duration_ms / 1000)
            set_health_check_status("storage", healthy)
            
            return HealthCheckResult(
                service="storage",
                healthy=healthy,
                duration_ms=duration_ms,
                details=details
            )
            
        except (BotoCoreError, ClientError, Exception) as e:
            duration_ms = (time.time() - start_time) * 1000
            self.failure_counts["storage"] += 1
            
            observe_health_check_duration("readiness", "storage", duration_ms / 1000)
            set_health_check_status("storage", False)
            
            return HealthCheckResult(
                service="storage",
                healthy=False,
                duration_ms=duration_ms,
                error=str(e)
            )
    
    async def check_gpu_provider(self) -> HealthCheckResult:
        """Check GPU provider connectivity and response time."""
        start_time = time.time()
        
        try:
            provider_type = settings.gpu_provider
            
            if provider_type == "comfy_local":
                # Check ComfyUI local endpoint
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(f"{settings.comfy_local_url}/system_stats")
                    response.raise_for_status()
                    
                    stats = response.json()
                    duration_ms = (time.time() - start_time) * 1000
                    healthy = duration_ms < self.thresholds["provider"]
                    
                    details = {
                        "provider": "comfy_local",
                        "endpoint": settings.comfy_local_url,
                        "status": "ok",
                        "gpu_info": stats.get("devices", []),
                        "threshold_ms": self.thresholds["provider"],
                    }
                    
            elif provider_type == "runpod":
                # Check RunPod API connectivity
                async with httpx.AsyncClient(timeout=10.0) as client:
                    headers = {"Authorization": f"Bearer {settings.runpod_api_key}"}
                    response = await client.get(
                        f"https://api.runpod.ai/v2/{settings.runpod_endpoint_id}/health",
                        headers=headers
                    )
                    response.raise_for_status()
                    
                    duration_ms = (time.time() - start_time) * 1000
                    healthy = duration_ms < self.thresholds["provider"]
                    
                    details = {
                        "provider": "runpod",
                        "endpoint_id": settings.runpod_endpoint_id,
                        "status": "ok",
                        "threshold_ms": self.thresholds["provider"],
                    }
            else:
                raise Exception(f"Unknown provider type: {provider_type}")
            
            if healthy:
                self.failure_counts["provider"] = 0
            else:
                self.failure_counts["provider"] += 1
            
            observe_health_check_duration("readiness", "provider", duration_ms / 1000)
            set_health_check_status("provider", healthy)
            
            return HealthCheckResult(
                service="provider",
                healthy=healthy,
                duration_ms=duration_ms,
                details=details
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            self.failure_counts["provider"] += 1
            
            observe_health_check_duration("readiness", "provider", duration_ms / 1000)
            set_health_check_status("provider", False)
            
            return HealthCheckResult(
                service="provider",
                healthy=False,
                duration_ms=duration_ms,
                error=str(e)
            )
    
    async def check_all(self) -> Dict[str, Any]:
        """Run all health checks and return comprehensive status."""
        start_time = time.time()
        
        # Run all checks concurrently
        checks = await asyncio.gather(
            self.check_database(),
            self.check_redis(),
            self.check_storage(),
            self.check_gpu_provider(),
            return_exceptions=True
        )
        
        total_duration = (time.time() - start_time) * 1000
        
        results = {}
        overall_healthy = True
        
        for check in checks:
            if isinstance(check, HealthCheckResult):
                results[check.service] = check.to_dict()
                if not check.healthy:
                    overall_healthy = False
            else:
                # Handle exceptions
                service_name = "unknown"
                results[service_name] = {
                    "service": service_name,
                    "healthy": False,
                    "duration_ms": 0,
                    "error": str(check)
                }
                overall_healthy = False
        
        # Check failure thresholds
        for service, count in self.failure_counts.items():
            threshold = self.failure_thresholds.get(service, 3)
            if count >= threshold:
                overall_healthy = False
                if service in results:
                    results[service]["consecutive_failures"] = count
                    results[service]["failure_threshold"] = threshold
        
        return {
            "healthy": overall_healthy,
            "timestamp": time.time(),
            "total_duration_ms": round(total_duration, 2),
            "services": results,
            "failure_counts": self.failure_counts,
        }


# Global health checker instance
health_checker = HealthChecker()


async def basic_health_check() -> Dict[str, Any]:
    """Basic health check for /healthz endpoint."""
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "service": "oneshot-face-swapper",
        "version": settings.app_version,
    }


async def readiness_check() -> Dict[str, Any]:
    """Comprehensive readiness check for /readyz endpoint."""
    return await health_checker.check_all()