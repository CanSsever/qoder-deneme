"""
Tests for payments and webhooks functionality.

Tests cover:
- Superwall webhook signature verification
- Idempotent event handling
- Subscription creation and updates
- Entitlement management through webhooks
"""

import hashlib
import hmac
import json
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from apps.api.main import app
from apps.core.settings import settings
from apps.db.models.subscription import Subscription, UserEntitlement
from apps.db.models.user import User
from tests.conftest import TestHelpers


class TestSuperwallWebhooks:
    """Test Superwall webhook processing."""
    
    def setup_method(self):
        """Setup test data."""
        self.client = TestClient(app)
        self.webhook_url = "/api/v1/webhooks/superwall"
        self.test_secret = "test_webhook_secret_123"
        
        # Mock settings for testing
        self.original_secret = settings.superwall_signing_secret
        settings.superwall_signing_secret = self.test_secret
    
    def teardown_method(self):
        """Cleanup after test."""
        settings.superwall_signing_secret = self.original_secret
    
    def generate_signature(self, payload: str) -> str:
        """Generate HMAC signature for testing."""
        signature = hmac.new(
            self.test_secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return f"sha256={signature}"
    
    def test_webhook_signature_validation_success(self, test_user):
        """Test successful webhook signature validation."""
        payload = {
            "event": "subscription_start",
            "event_id": "evt_test_123",
            "user_id": str(test_user.id),
            "product_id": "pro_monthly",
            "subscription_id": "sub_123",
            "status": "active",
            "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat() + "Z"
        }
        
        payload_str = json.dumps(payload)
        signature = self.generate_signature(payload_str)
        
        response = self.client.post(
            self.webhook_url,
            data=payload_str,
            headers={
                "Content-Type": "application/json",
                "X-Superwall-Signature": signature
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "subscription_id" in data
    
    def test_webhook_signature_validation_failure(self, test_user):
        """Test webhook signature validation failure."""
        payload = {
            "event": "subscription_start",
            "event_id": "evt_test_456",
            "user_id": str(test_user.id),
            "product_id": "pro_monthly"
        }
        
        payload_str = json.dumps(payload)
        wrong_signature = "sha256=wrong_signature"
        
        response = self.client.post(
            self.webhook_url,
            data=payload_str,
            headers={
                "Content-Type": "application/json",
                "X-Superwall-Signature": wrong_signature
            }
        )
        
        assert response.status_code == 401
        assert "Invalid signature" in response.json()["detail"]
    
    def test_webhook_missing_signature_header(self, test_user):
        """Test webhook with missing signature header."""
        payload = {
            "event": "subscription_start",
            "event_id": "evt_test_789",
            "user_id": str(test_user.id),
            "product_id": "pro_monthly"
        }
        
        response = self.client.post(
            self.webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 400
        assert "Missing signature header" in response.json()["detail"]
    
    def test_webhook_idempotent_processing(self, test_user):
        """Test idempotent webhook processing."""
        payload = {
            "event": "subscription_start",
            "event_id": "evt_idempotent_123",
            "user_id": str(test_user.id),
            "product_id": "pro_monthly",
            "status": "active"
        }
        
        payload_str = json.dumps(payload)
        signature = self.generate_signature(payload_str)
        headers = {
            "Content-Type": "application/json",
            "X-Superwall-Signature": signature
        }
        
        # First request
        response1 = self.client.post(self.webhook_url, data=payload_str, headers=headers)
        assert response1.status_code == 200
        
        # Second request with same event_id
        response2 = self.client.post(self.webhook_url, data=payload_str, headers=headers)
        assert response2.status_code == 200
        
        data2 = response2.json()
        assert data2["message"] == "Event already processed"
    
    def test_subscription_start_event(self, test_user, session):
        """Test subscription start event processing."""
        payload = {
            "event": "subscription_start",
            "event_id": "evt_start_123",
            "user_id": str(test_user.id),
            "product_id": "pro_monthly",
            "subscription_id": "sub_pro_123",
            "status": "active",
            "expires_at": (datetime.utcnow() + timedelta(days=30)).isoformat() + "Z"
        }
        
        payload_str = json.dumps(payload)
        signature = self.generate_signature(payload_str)
        
        response = self.client.post(
            self.webhook_url,
            data=payload_str,
            headers={
                "Content-Type": "application/json",
                "X-Superwall-Signature": signature
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        
        # Verify subscription was created
        subscription = session.exec(
            select(Subscription).where(Subscription.event_id == "evt_start_123")
        ).first()
        
        assert subscription is not None
        assert subscription.user_id == str(test_user.id)
        assert subscription.product_id == "pro_monthly"
        assert subscription.status == "active"
        
        # Verify entitlement was created
        entitlement = session.exec(
            select(UserEntitlement).where(
                UserEntitlement.user_id == str(test_user.id),
                UserEntitlement.plan_code == "pro"
            )
        ).first()
        
        assert entitlement is not None
        assert entitlement.is_active()
    
    def test_subscription_end_event(self, test_user, session):
        """Test subscription end event processing."""
        # First create an active subscription
        start_payload = {
            "event": "subscription_start",
            "event_id": "evt_start_for_end_123",
            "user_id": str(test_user.id),
            "product_id": "pro_monthly",
            "status": "active"
        }
        
        start_payload_str = json.dumps(start_payload)
        start_signature = self.generate_signature(start_payload_str)
        
        self.client.post(
            self.webhook_url,
            data=start_payload_str,
            headers={
                "Content-Type": "application/json",
                "X-Superwall-Signature": start_signature
            }
        )
        
        # Now end the subscription
        end_payload = {
            "event": "subscription_end",
            "event_id": "evt_end_123",
            "user_id": str(test_user.id),
            "product_id": "pro_monthly",
            "subscription_id": "sub_pro_123",
            "status": "cancelled"
        }
        
        end_payload_str = json.dumps(end_payload)
        end_signature = self.generate_signature(end_payload_str)
        
        response = self.client.post(
            self.webhook_url,
            data=end_payload_str,
            headers={
                "Content-Type": "application/json",
                "X-Superwall-Signature": end_signature
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["action"] == "deactivated"
    
    def test_webhook_invalid_json(self):
        """Test webhook with invalid JSON payload."""
        invalid_payload = "invalid json"
        signature = self.generate_signature(invalid_payload)
        
        response = self.client.post(
            self.webhook_url,
            data=invalid_payload,
            headers={
                "Content-Type": "application/json",
                "X-Superwall-Signature": signature
            }
        )
        
        assert response.status_code == 400
        assert "Invalid JSON payload" in response.json()["detail"]
    
    def test_webhook_missing_required_fields(self):
        """Test webhook with missing required fields."""
        payload = {
            "event": "subscription_start",
            # Missing event_id, user_id, product_id
        }
        
        payload_str = json.dumps(payload)
        signature = self.generate_signature(payload_str)
        
        response = self.client.post(
            self.webhook_url,
            data=payload_str,
            headers={
                "Content-Type": "application/json",
                "X-Superwall-Signature": signature
            }
        )
        
        assert response.status_code == 400
        assert "Missing required fields" in response.json()["detail"]
    
    def test_webhook_user_not_found(self):
        """Test webhook for non-existent user."""
        payload = {
            "event": "subscription_start",
            "event_id": "evt_no_user_123",
            "user_id": "non_existent_user_id",
            "product_id": "pro_monthly"
        }
        
        payload_str = json.dumps(payload)
        signature = self.generate_signature(payload_str)
        
        response = self.client.post(
            self.webhook_url,
            data=payload_str,
            headers={
                "Content-Type": "application/json",
                "X-Superwall-Signature": signature
            }
        )
        
        assert response.status_code == 404
        assert "User not found" in response.json()["detail"]


class TestWebhookHealth:
    """Test webhook health endpoint."""
    
    def test_webhook_health_endpoint(self):
        """Test webhook health check."""
        client = TestClient(app)
        response = client.get("/api/v1/webhooks/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data
        assert "signature_verification" in data