"""
Application settings and configuration management.
"""
from typing import List, Optional
from pydantic_settings import BaseSettings
from pydantic import field_validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    database_url: str
    
    # JWT Configuration
    jwt_secret: str
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
    
    # Application Settings
    default_credits: int = 10
    max_file_size_mb: int = 10
    environment: str = "development"
    
    # CORS Settings
    allowed_origins: str = "http://localhost:3000,http://localhost:8081"
    
    # Logging
    log_level: str = "INFO"
    
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
    
    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()