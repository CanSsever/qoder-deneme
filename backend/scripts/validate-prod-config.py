#!/usr/bin/env python3
"""
Production Configuration Validation Script

This script validates that the production environment is properly configured
and secure before GA launch.
"""
import os
import sys
import json
from pathlib import Path

# Add the parent directory to the path so we can import our modules
sys.path.append(str(Path(__file__).parent.parent))

from apps.core.settings import Settings


def validate_secrets():
    """Validate that all secrets have been properly rotated."""
    issues = []
    settings = Settings()
    
    # Check JWT secret
    if settings.jwt_secret == "your-super-secret-jwt-key-change-this-in-production":
        issues.append("❌ JWT_SECRET: Still using default value - SECURITY RISK")
    elif len(settings.jwt_secret) < 32:
        issues.append("⚠️  JWT_SECRET: Should be at least 32 characters long")
    else:
        print("✅ JWT_SECRET: Properly configured")
    
    # Check HMAC secret
    if not settings.hmac_secret:
        issues.append("❌ HMAC_SECRET: Not configured - required for webhooks")
    elif settings.hmac_secret == "your-webhook-hmac-secret":
        issues.append("❌ HMAC_SECRET: Still using default value - SECURITY RISK")
    else:
        print("✅ HMAC_SECRET: Properly configured")
    
    # Check Superwall secrets
    if not settings.superwall_secret:
        issues.append("❌ SUPERWALL_SECRET: Not configured")
    elif settings.superwall_secret == "your-superwall-secret-key":
        issues.append("❌ SUPERWALL_SECRET: Still using default value")
    else:
        print("✅ SUPERWALL_SECRET: Properly configured")
    
    if not settings.superwall_signing_secret:
        issues.append("❌ SUPERWALL_SIGNING_SECRET: Not configured")
    elif settings.superwall_signing_secret == "your-superwall-signing-secret":
        issues.append("❌ SUPERWALL_SIGNING_SECRET: Still using default value")
    else:
        print("✅ SUPERWALL_SIGNING_SECRET: Properly configured")
    
    return issues


def validate_providers():
    """Validate GPU provider configuration."""
    issues = []
    settings = Settings()
    
    if not settings.enforce_real_providers:
        issues.append("❌ ENFORCE_REAL_PROVIDERS: Should be enabled in production")
    else:
        print("✅ ENFORCE_REAL_PROVIDERS: Enabled")
    
    if settings.gpu_provider == "mock":
        issues.append("❌ GPU_PROVIDER: Should not use mock provider in production")
    elif settings.gpu_provider == "runpod":
        if not settings.runpod_api_key:
            issues.append("❌ RUNPOD_API_KEY: Required when using RunPod provider")
        if not settings.runpod_endpoint_id:
            issues.append("❌ RUNPOD_ENDPOINT_ID: Required when using RunPod provider")
        if settings.runpod_api_key and settings.runpod_endpoint_id:
            print("✅ RunPod: Properly configured")
    elif settings.gpu_provider == "comfy_local":
        if not settings.comfy_local_url or "localhost" in settings.comfy_local_url:
            issues.append("⚠️  COMFY_LOCAL_URL: Should point to production ComfyUI instance")
        else:
            print("✅ ComfyUI: Properly configured")
    
    return issues


def validate_security():
    """Validate security configuration."""
    issues = []
    settings = Settings()
    
    if not settings.is_production:
        issues.append("❌ ENVIRONMENT: Should be set to 'production'")
    else:
        print("✅ ENVIRONMENT: Set to production")
    
    if settings.enable_docs:
        issues.append("❌ ENABLE_DOCS: Should be disabled in production")
    else:
        print("✅ API Docs: Disabled")
    
    if settings.safe_mode:
        issues.append("❌ SAFE_MODE: Should be disabled in production")
    else:
        print("✅ Safe Mode: Disabled")
    
    if not settings.force_https:
        issues.append("❌ FORCE_HTTPS: Should be enabled in production")
    else:
        print("✅ HTTPS: Enforced")
    
    if settings.enable_debug:
        issues.append("❌ ENABLE_DEBUG: Should be disabled in production")
    else:
        print("✅ Debug Mode: Disabled")
    
    # Check CORS origins
    localhost_origins = [origin for origin in settings.allowed_origins if "localhost" in origin]
    if localhost_origins:
        issues.append(f"❌ ALLOWED_ORIGINS: Contains localhost origins: {localhost_origins}")
    else:
        print("✅ CORS Origins: Production domains only")
    
    if settings.dev_billing_mode != "live":
        issues.append("❌ DEV_BILLING_MODE: Should be 'live' in production")
    else:
        print("✅ Billing Mode: Live")
    
    return issues


def validate_monitoring():
    """Validate monitoring and observability configuration."""
    issues = []
    settings = Settings()
    
    if not settings.sentry_dsn:
        issues.append("⚠️  SENTRY_DSN: Not configured - monitoring recommended")
    else:
        print("✅ Sentry: Configured")
    
    if not settings.enable_metrics:
        issues.append("⚠️  ENABLE_METRICS: Should be enabled for monitoring")
    else:
        print("✅ Metrics: Enabled")
    
    if settings.log_level not in ["INFO", "WARNING", "ERROR"]:
        issues.append(f"⚠️  LOG_LEVEL: '{settings.log_level}' may be too verbose for production")
    else:
        print("✅ Log Level: Appropriate for production")
    
    return issues


def validate_infrastructure():
    """Validate infrastructure configuration."""
    issues = []
    settings = Settings()
    
    # Check database URL
    if "localhost" in settings.database_url or "sqlite" in settings.database_url:
        issues.append("❌ DATABASE_URL: Should point to production database")
    else:
        print("✅ Database: Production configuration")
    
    # Check Redis URL
    if "localhost" in settings.redis_url:
        issues.append("❌ REDIS_URL: Should point to production Redis instance")
    else:
        print("✅ Redis: Production configuration")
    
    # Check S3 configuration
    if not settings.s3_bucket or "test" in settings.s3_bucket or "dev" in settings.s3_bucket:
        issues.append("❌ S3_BUCKET: Should be production bucket")
    else:
        print("✅ S3 Bucket: Production configuration")
    
    return issues


def main():
    """Run all production validation checks."""
    print("🚀 Production Configuration Validation")
    print("=" * 50)
    
    all_issues = []
    
    print("\n📋 Validating Secrets...")
    all_issues.extend(validate_secrets())
    
    print("\n🔧 Validating GPU Providers...")
    all_issues.extend(validate_providers())
    
    print("\n🔒 Validating Security Configuration...")
    all_issues.extend(validate_security())
    
    print("\n📊 Validating Monitoring...")
    all_issues.extend(validate_monitoring())
    
    print("\n🏗️  Validating Infrastructure...")
    all_issues.extend(validate_infrastructure())
    
    print("\n" + "=" * 50)
    
    if not all_issues:
        print("🎉 All validation checks passed!")
        print("✅ Configuration is ready for production deployment")
        return 0
    else:
        print(f"❌ Found {len(all_issues)} configuration issues:")
        for issue in all_issues:
            print(f"   {issue}")
        
        critical_issues = [issue for issue in all_issues if "❌" in issue]
        warning_issues = [issue for issue in all_issues if "⚠️" in issue]
        
        if critical_issues:
            print(f"\n🚨 {len(critical_issues)} critical issues must be fixed before production deployment")
            return 1
        elif warning_issues:
            print(f"\n⚠️  {len(warning_issues)} warnings found - review recommended")
            return 0
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)