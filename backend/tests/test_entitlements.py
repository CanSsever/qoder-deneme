"""
Tests for entitlements service functionality.

Tests cover:
- User entitlement management
- Usage tracking and limits
- Daily limit enforcement
- Plan validation
"""

import pytest
from datetime import datetime, timedelta
from sqlmodel import Session, select

from apps.api.services.entitlements import EntitlementsService
from apps.db.models.subscription import UserEntitlement, UsageAggregate, PLAN_TEMPLATES
from apps.db.models.job import Job
from apps.db.models.user import User
from tests.conftest import TestHelpers


class TestEntitlementsService:
    """Test entitlements service functionality."""
    
    def test_get_user_entitlement_active(self, test_user, session):
        """Test getting active user entitlement."""
        # Create test entitlement
        entitlement = UserEntitlement(
            user_id=str(test_user.id),
            plan_code="pro",
            limits_json='{"daily_jobs": 50, "concurrent_jobs": 3, "max_side": 1024, "features": ["face_restore", "face_swap"]}',
            effective_from=datetime.utcnow() - timedelta(days=1),
            effective_to=None
        )
        session.add(entitlement)
        session.commit()
        
        with EntitlementsService(session) as service:
            result = service.get_user_entitlement(str(test_user.id))
            
        assert result is not None
        assert result.plan_code == "pro"
        assert result.is_active()
    
    def test_get_user_entitlement_none(self, test_user, session):
        """Test getting entitlement when none exists."""
        with EntitlementsService(session) as service:
            result = service.get_user_entitlement(str(test_user.id))
            
        assert result is None
    
    def test_get_user_limits_with_entitlement(self, test_user, session):
        """Test getting user limits with active entitlement."""
        # Create test entitlement
        entitlement = UserEntitlement(
            user_id=str(test_user.id),
            plan_code="premium",
            limits_json='{"daily_jobs": 200, "concurrent_jobs": 5, "max_side": 2048, "features": ["face_restore", "face_swap", "upscale"]}',
            effective_from=datetime.utcnow(),
            effective_to=None
        )
        session.add(entitlement)
        session.commit()
        
        with EntitlementsService(session) as service:
            limits = service.get_user_limits(str(test_user.id))
        
        assert limits["plan_code"] == "premium"
        assert limits["daily_jobs"] == 200
        assert limits["concurrent_jobs"] == 5
        assert limits["max_side"] == 2048
        assert "face_restore" in limits["features"]
        assert "face_swap" in limits["features"]
        assert "upscale" in limits["features"]
    
    def test_get_user_limits_fallback(self, test_user, session):
        """Test getting user limits with fallback to default."""
        with EntitlementsService(session) as service:
            limits = service.get_user_limits(str(test_user.id))
        
        # Should use default plan template
        assert limits["plan_code"] == "free"  # Default plan
        assert limits["daily_jobs"] == 5
        assert limits["concurrent_jobs"] == 1
        assert limits["max_side"] == 512
    
    def test_create_entitlement(self, test_user, session):
        """Test creating new entitlement."""
        with EntitlementsService(session) as service:
            entitlement = service.create_entitlement(
                user_id=str(test_user.id),
                plan_code="pro",
                effective_from=datetime.utcnow()
            )
        
        assert entitlement.user_id == str(test_user.id)
        assert entitlement.plan_code == "pro"
        assert entitlement.is_active()
        
        # Verify limits match template
        limits = entitlement.get_limits()
        expected_limits = PLAN_TEMPLATES["pro"]["limits"]
        assert limits == expected_limits
    
    def test_create_entitlement_invalid_plan(self, test_user, session):
        """Test creating entitlement with invalid plan code."""
        with EntitlementsService(session) as service:
            with pytest.raises(Exception):  # Should raise ValidationError
                service.create_entitlement(
                    user_id=str(test_user.id),
                    plan_code="invalid_plan"
                )
    
    def test_get_daily_usage_new(self, test_user, session):
        """Test getting daily usage for new day."""
        with EntitlementsService(session) as service:
            usage = service.get_daily_usage(str(test_user.id))
        
        assert usage.user_id == str(test_user.id)
        assert usage.jobs_created == 0
        assert usage.jobs_completed == 0
        assert usage.jobs_failed == 0
    
    def test_get_daily_usage_existing(self, test_user, session):
        """Test getting existing daily usage."""
        # Create existing usage record
        today = UsageAggregate.get_date_key()
        existing_usage = UsageAggregate(
            user_id=str(test_user.id),
            date=today,
            jobs_created=5,
            jobs_completed=3,
            jobs_failed=1
        )
        session.add(existing_usage)
        session.commit()
        
        with EntitlementsService(session) as service:
            usage = service.get_daily_usage(str(test_user.id))
        
        assert usage.jobs_created == 5
        assert usage.jobs_completed == 3
        assert usage.jobs_failed == 1
    
    def test_check_job_creation_limits_success(self, test_user, session):
        """Test job creation limits check - success case."""
        # Create pro entitlement
        entitlement = UserEntitlement(
            user_id=str(test_user.id),
            plan_code="pro",
            limits_json='{"daily_jobs": 50, "concurrent_jobs": 3, "max_side": 1024, "features": ["face_restore", "face_swap"]}',
            effective_from=datetime.utcnow(),
            effective_to=None
        )
        session.add(entitlement)
        session.commit()
        
        job_params = {
            "job_type": "face_restore",
            "max_side": 512
        }
        
        with EntitlementsService(session) as service:
            can_create, error_message = service.check_job_creation_limits(str(test_user.id), job_params)
        
        assert can_create is True
        assert error_message == ""
    
    def test_check_job_creation_limits_daily_exceeded(self, test_user, session):
        """Test job creation limits check - daily limit exceeded."""
        # Create free entitlement
        entitlement = UserEntitlement(
            user_id=str(test_user.id),
            plan_code="free",
            limits_json='{"daily_jobs": 5, "concurrent_jobs": 1, "max_side": 512, "features": ["face_restore"]}',
            effective_from=datetime.utcnow(),
            effective_to=None
        )
        session.add(entitlement)
        
        # Create usage record at daily limit
        today = UsageAggregate.get_date_key()
        usage = UsageAggregate(
            user_id=str(test_user.id),
            date=today,
            jobs_created=5  # At the daily limit
        )
        session.add(usage)
        session.commit()
        
        job_params = {"job_type": "face_restore"}
        
        with EntitlementsService(session) as service:
            can_create, error_message = service.check_job_creation_limits(str(test_user.id), job_params)
        
        assert can_create is False
        assert "Daily job limit exceeded" in error_message
    
    def test_check_job_creation_limits_concurrent_exceeded(self, test_user, session):
        """Test job creation limits check - concurrent limit exceeded."""
        # Create free entitlement
        entitlement = UserEntitlement(
            user_id=str(test_user.id),
            plan_code="free",
            limits_json='{"daily_jobs": 5, "concurrent_jobs": 1, "max_side": 512, "features": ["face_restore"]}',
            effective_from=datetime.utcnow(),
            effective_to=None
        )
        session.add(entitlement)
        
        # Create pending job
        job = Job(
            user_id=str(test_user.id),
            job_type="face_restore",
            status="pending"
        )
        session.add(job)
        session.commit()
        
        job_params = {"job_type": "face_restore"}
        
        with EntitlementsService(session) as service:
            can_create, error_message = service.check_job_creation_limits(str(test_user.id), job_params)
        
        assert can_create is False
        assert "Concurrent job limit exceeded" in error_message
    
    def test_check_job_creation_limits_max_side_exceeded(self, test_user, session):
        """Test job creation limits check - max_side parameter exceeded."""
        # Create free entitlement
        entitlement = UserEntitlement(
            user_id=str(test_user.id),
            plan_code="free",
            limits_json='{"daily_jobs": 5, "concurrent_jobs": 1, "max_side": 512, "features": ["face_restore"]}',
            effective_from=datetime.utcnow(),
            effective_to=None
        )
        session.add(entitlement)
        session.commit()
        
        job_params = {
            "job_type": "face_restore",
            "max_side": 1024  # Exceeds free plan limit
        }
        
        with EntitlementsService(session) as service:
            can_create, error_message = service.check_job_creation_limits(str(test_user.id), job_params)
        
        assert can_create is False
        assert "exceeds limit of 512" in error_message
    
    def test_check_job_creation_limits_feature_unavailable(self, test_user, session):
        """Test job creation limits check - feature not available."""
        # Create free entitlement (no face_swap feature)
        entitlement = UserEntitlement(
            user_id=str(test_user.id),
            plan_code="free",
            limits_json='{"daily_jobs": 5, "concurrent_jobs": 1, "max_side": 512, "features": ["face_restore"]}',
            effective_from=datetime.utcnow(),
            effective_to=None
        )
        session.add(entitlement)
        session.commit()
        
        job_params = {"job_type": "face_swap"}
        
        with EntitlementsService(session) as service:
            can_create, error_message = service.check_job_creation_limits(str(test_user.id), job_params)
        
        assert can_create is False
        assert "not available in free plan" in error_message
    
    def test_increment_job_usage(self, test_user, session):
        """Test incrementing job usage."""
        with EntitlementsService(session) as service:
            service.increment_job_usage(str(test_user.id), "face_restore")
            
            # Check usage was incremented
            usage = service.get_daily_usage(str(test_user.id))
            assert usage.jobs_created == 1
    
    def test_update_job_completion_success(self, test_user, session):
        """Test updating job completion statistics - success."""
        with EntitlementsService(session) as service:
            service.update_job_completion(str(test_user.id), "succeeded", processing_time_seconds=120)
            
            usage = service.get_daily_usage(str(test_user.id))
            assert usage.jobs_completed == 1
            assert usage.total_processing_time_seconds == 120
    
    def test_update_job_completion_failure(self, test_user, session):
        """Test updating job completion statistics - failure."""
        with EntitlementsService(session) as service:
            service.update_job_completion(str(test_user.id), "failed", processing_time_seconds=60)
            
            usage = service.get_daily_usage(str(test_user.id))
            assert usage.jobs_failed == 1
            assert usage.total_processing_time_seconds == 60
    
    def test_get_usage_summary(self, test_user, session):
        """Test getting usage summary."""
        # Create some usage data
        dates = [
            datetime.utcnow() - timedelta(days=2),
            datetime.utcnow() - timedelta(days=1),
            datetime.utcnow()
        ]
        
        for i, date in enumerate(dates):
            usage = UsageAggregate(
                user_id=str(test_user.id),
                date=UsageAggregate.get_date_key(date),
                jobs_created=i + 1,
                jobs_completed=i,
                jobs_failed=0,
                total_processing_time_seconds=(i + 1) * 60
            )
            session.add(usage)
        
        session.commit()
        
        with EntitlementsService(session) as service:
            summary = service.get_usage_summary(str(test_user.id), days=7)
        
        assert summary["user_id"] == str(test_user.id)
        assert summary["period_summary"]["total_jobs_created"] == 6  # 1+2+3
        assert summary["period_summary"]["total_jobs_completed"] == 3  # 0+1+2
        assert summary["today"]["jobs_created"] == 3
        assert len(summary["daily_usage"]) == 3


class TestEntitlementsConvenienceFunctions:
    """Test convenience functions for entitlements."""
    
    def test_get_user_limits_function(self, test_user, session):
        """Test get_user_limits convenience function."""
        from apps.api.services.entitlements import get_user_limits
        
        limits = get_user_limits(str(test_user.id))
        assert isinstance(limits, dict)
        assert "plan_code" in limits
        assert "daily_jobs" in limits
    
    def test_check_job_limits_function(self, test_user, session):
        """Test check_job_limits convenience function."""
        from apps.api.services.entitlements import check_job_limits
        
        job_params = {"job_type": "face_restore", "max_side": 512}
        can_create, error_message = check_job_limits(str(test_user.id), job_params)
        
        assert isinstance(can_create, bool)
        assert isinstance(error_message, str)
    
    def test_increment_job_usage_function(self, test_user, session):
        """Test increment_job_usage convenience function."""
        from apps.api.services.entitlements import increment_job_usage
        
        # Should not raise an exception
        increment_job_usage(str(test_user.id), "face_restore")


class TestPlanTemplates:
    """Test plan template validation."""
    
    def test_plan_templates_structure(self):
        """Test that all plan templates have required structure."""
        required_fields = ["daily_jobs", "concurrent_jobs", "max_side", "features"]
        
        for plan_code, template in PLAN_TEMPLATES.items():
            assert "limits" in template
            limits = template["limits"]
            
            for field in required_fields:
                assert field in limits, f"Plan {plan_code} missing field {field}"
            
            # Test field types
            assert isinstance(limits["daily_jobs"], int)
            assert isinstance(limits["concurrent_jobs"], int)
            assert isinstance(limits["max_side"], int)
            assert isinstance(limits["features"], list)
            
            # Test reasonable values
            assert limits["daily_jobs"] > 0
            assert limits["concurrent_jobs"] > 0
            assert limits["max_side"] >= 64
    
    def test_plan_hierarchy(self):
        """Test that plan limits follow expected hierarchy."""
        free_limits = PLAN_TEMPLATES["free"]["limits"]
        pro_limits = PLAN_TEMPLATES["pro"]["limits"]
        premium_limits = PLAN_TEMPLATES["premium"]["limits"]
        
        # Pro should have more than free
        assert pro_limits["daily_jobs"] > free_limits["daily_jobs"]
        assert pro_limits["concurrent_jobs"] >= free_limits["concurrent_jobs"]
        assert pro_limits["max_side"] >= free_limits["max_side"]
        
        # Premium should have more than pro
        assert premium_limits["daily_jobs"] >= pro_limits["daily_jobs"]
        assert premium_limits["concurrent_jobs"] >= pro_limits["concurrent_jobs"]
        assert premium_limits["max_side"] >= pro_limits["max_side"]