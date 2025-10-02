"""
Application settings and configuration management.
"""
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Supabase Configuration
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    supabase_jwt_secret: str
    
    # Database
    database_url: str
    
    # JWT Configuration (Supabase)
    jwt_secret: str  # This will be the Supabase JWT secret
    jwt_expiration_hours: int = 24
    jwt_algorithm: str = "HS256"
    
    # AWS S3 Configuration
    s3_bucket: str
    s3_key: str
    s3_secret: str
    s3_region: str = "us-east-1"
    
    # Redis Configuration
    redis_url: str = "redis://localhost:6379"
    
    # Payment Configuration
    superwall_secret: str
    superwall_signing_secret: str = ""
    
    # Entitlements Configuration
    entitlements_default_plan: str = "free"
    dev_billing_mode: str = "mock"  # "mock" or "live"
    
    # Daily Limits (fallback if no entitlements found)
    fallback_daily_job_limit: int = 5
    fallback_concurrent_job_limit: int = 1
    fallback_max_side_limit: int = 512
    
    # Application Settings
    default_credits: int = 10
    max_file_size_mb: int = 10
    environment: str = "development"
    
    # CORS Settings
    allowed_origins: str = "http://localhost:3000,http://localhost:8081"
    
    # Logging
    log_level: str = "INFO"
    
    # Monitoring & Observability
    sentry_dsn: str = ""
    sentry_traces_sample_rate: float = 0.1
    sentry_profiles_sample_rate: float = 0.1
    release_version: str = "v1.0.0"
    
    # Prometheus Metrics
    enable_metrics: bool = True
    metrics_port: int = 8000
    
    # Application Version
    app_version: str = "2.0.0"
    
    # GPU Provider Configuration
    gpu_provider: str = "comfy_local"
    
    # ComfyUI Local Configuration
    comfy_local_url: str = "http://localhost:8188"
    
    # RunPod Configuration
    runpod_api_key: str = ""
    runpod_endpoint_id: str = ""
    
    # Output Configuration
    output_format: str = "png"
    output_quality: int = 95
    max_input_mb: int = 20
    
    # Security Configuration
    max_image_dimension: int = 8192
    min_image_dimension: int = 64
    
    # Webhook Configuration
    hmac_secret: str = ""
    webhook_timeout_seconds: int = 30
    webhook_retry_delays: str = "60,300,1800,7200"  # 1m, 5m, 30m, 2h
    
    # Privacy & Content Safety Configuration
    retention_days: int = 30
    nsfw_mode: str = "block"  # "block" or "flag"
    watermark_default: bool = True
    enable_exif_stripping: bool = True
    enable_watermark: bool = True
    enable_nsfw_detection: bool = True
    enable_consent_enforcement: bool = True
    
    # Privacy Detection Thresholds
    nsfw_confidence_threshold: float = 0.7
    skin_ratio_threshold: float = 0.35
    flesh_tone_threshold: float = 0.25
    
    # Production Security Configuration
    enable_docs: bool = True  # Disable API docs in production
    safe_mode: bool = True  # Enable safe mode for development
    force_https: bool = False  # Force HTTPS redirects
    enable_debug: bool = False  # Disable debug mode in production
    cors_credentials: bool = False  # Enable CORS credentials
    trusted_hosts: str = "*"  # Trusted host patterns
    
    # Provider Configuration
    enforce_real_providers: bool = False  # Enforce real GPU providers only
    disable_mock_providers: bool = False  # Disable mock providers
    
    # Replicate API Configuration
    replicate_api_token: str = ""
    replicate_upscale_model: str = "nightmareai/real-esrgan"
    
    # Secret Rotation
    jwt_secret_version: str = "v1"  # JWT secret version for rotation
    webhook_secret_version: str = "v1"  # Webhook secret version
    
    # Rate Limiting
    enable_rate_limiting: bool = True
    global_rate_limit: str = "1000/hour"  # Global API rate limit
    
    # Session Security
    secure_cookies: bool = False  # Enable secure cookie flags
    session_timeout_minutes: int = 60  # Session timeout
    
    @field_validator("allowed_origins")
    def validate_origins(cls, v):
        """Convert comma-separated origins string to list."""
        return [origin.strip() for origin in v.split(",")]
    
    @field_validator("webhook_retry_delays")
    def validate_webhook_delays(cls, v):
        """Convert comma-separated delay string to list of integers."""
        if not v:
            return [60, 300, 1800, 7200]
        return [int(delay.strip()) for delay in v.split(",")]
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"
    
    @property
    def s3_bucket_name(self) -> str:
        """Get S3 bucket name (alias for compatibility)."""
        return self.s3_bucket
    
    @property
    def is_secure_deployment(self) -> bool:
        """Check if deployment is secure for production."""
        return (
            self.is_production and
            not self.enable_docs and
            not self.safe_mode and
            self.force_https and
            not self.enable_debug and
            self.enforce_real_providers
        )
    
    def validate_production_config(self) -> List[str]:
        """Validate production configuration and return list of issues."""
        issues = []
        
        if self.is_production:
            if self.enable_docs:
                issues.append("API documentation should be disabled in production")
            
            if self.safe_mode:
                issues.append("Safe mode should be disabled in production")
            
            if not self.force_https:
                issues.append("HTTPS should be enforced in production")
            
            if self.enable_debug:
                issues.append("Debug mode should be disabled in production")
            
            if "localhost" in str(self.allowed_origins):
                issues.append("Localhost origins should be removed in production")
            
            if self.dev_billing_mode == "mock":
                issues.append("Billing mode should be 'live' in production")
            
            if not self.enforce_real_providers:
                issues.append("Real GPU providers should be enforced in production")
            
            if self.jwt_secret == "your-super-secret-jwt-key-change-this-in-production":
                issues.append("JWT secret must be changed from default value")
            
            if len(self.jwt_secret) < 32:
                issues.append("JWT secret should be at least 32 characters long")
        
        return issues
    
    def get_production_checklist(self) -> dict:
        """Get production readiness checklist."""
        checklist = {
            "configuration": {
                "environment_set_to_production": self.environment == "production",
                "docs_disabled": not self.enable_docs,
                "safe_mode_disabled": not self.safe_mode,
                "https_enforced": self.force_https,
                "debug_disabled": not self.enable_debug,
                "real_providers_enforced": self.enforce_real_providers,
            },
            "security": {
                "jwt_secret_rotated": self.jwt_secret != "your-super-secret-jwt-key-change-this-in-production",
                "cors_configured": "localhost" not in str(self.allowed_origins),
                "https_only_cookies": self.secure_cookies,
                "billing_live_mode": self.dev_billing_mode == "live",
            },
            "monitoring": {
                "sentry_configured": bool(self.sentry_dsn),
                "metrics_enabled": self.enable_metrics,
                "logging_configured": self.log_level in ["INFO", "WARNING", "ERROR"],
            }
        }
        
        # Calculate overall readiness
        all_checks = []
        for category in checklist.values():
            all_checks.extend(category.values())
        
        checklist["overall_ready"] = all(all_checks)
        checklist["ready_percentage"] = sum(all_checks) / len(all_checks) * 100
        
        return checklist
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()