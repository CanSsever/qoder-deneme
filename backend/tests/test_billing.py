"""Tests for billing functionality"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from apps.db.models.user import User


class TestBilling:
    """Test billing functionality"""

    def test_validate_receipt_success(self, client: TestClient, auth_headers: dict, test_user: User, test_session: Session):
        """Test successful receipt validation"""
        initial_credits = test_user.credits
        
        receipt_data = {
            "receipt_data": "fake_receipt_data_12345",
            "product_id": "credits_100",
            "platform": "ios"
        }
        
        response = client.post("/api/v1/billing/validate", json=receipt_data, headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "credits_added" in data
        assert "new_balance" in data
        assert data["new_balance"] > initial_credits

    def test_validate_receipt_invalid_receipt(self, client: TestClient, auth_headers: dict):
        """Test receipt validation with invalid receipt"""
        receipt_data = {
            "receipt_data": "invalid_receipt",
            "product_id": "credits_100",
            "platform": "ios"
        }
        
        response = client.post("/api/v1/billing/validate", json=receipt_data, headers=auth_headers)
        
        assert response.status_code == 400
        assert "Invalid receipt" in response.json()["detail"]

    def test_validate_receipt_invalid_platform(self, client: TestClient, auth_headers: dict):
        """Test receipt validation with invalid platform"""
        receipt_data = {
            "receipt_data": "fake_receipt_data_12345",
            "product_id": "credits_100",
            "platform": "invalid_platform"
        }
        
        response = client.post("/api/v1/billing/validate", json=receipt_data, headers=auth_headers)
        
        assert response.status_code == 422

    def test_validate_receipt_unauthorized(self, client: TestClient):
        """Test receipt validation without authentication"""
        receipt_data = {
            "receipt_data": "fake_receipt_data_12345",
            "product_id": "credits_100",
            "platform": "ios"
        }
        
        response = client.post("/api/v1/billing/validate", json=receipt_data)
        
        assert response.status_code == 401

    def test_validate_receipt_unknown_product(self, client: TestClient, auth_headers: dict):
        """Test receipt validation with unknown product ID"""
        receipt_data = {
            "receipt_data": "fake_receipt_data_12345",
            "product_id": "unknown_product",
            "platform": "ios"
        }
        
        response = client.post("/api/v1/billing/validate", json=receipt_data, headers=auth_headers)
        
        assert response.status_code == 400
        assert "Unknown product" in response.json()["detail"]

    def test_credit_deduction_on_job_creation(self, client: TestClient, auth_headers: dict, test_user: User, test_session: Session):
        """Test that credits are deducted when creating a job"""
        initial_credits = test_user.credits
        
        job_data = {
            "source_url": "https://example.com/source.jpg",
            "target_url": "https://example.com/target.jpg",
            "job_type": "face_swap",
            "params": {"face_restore": True}
        }
        
        from unittest.mock import patch
        with patch('apps.worker.tasks.process_ai_job.delay') as mock_task:
            mock_task.return_value.id = "test-task-id"
            
            response = client.post("/api/v1/jobs", json=job_data, headers=auth_headers)
        
        assert response.status_code == 201
        
        # Refresh user to check credits
        test_session.refresh(test_user)
        assert test_user.credits < initial_credits