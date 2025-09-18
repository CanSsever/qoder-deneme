"""Integration tests for complete workflows"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
from unittest.mock import patch
import time

from apps.db.models.user import User
from apps.db.models.job import Job


class TestIntegration:
    """Test complete workflows"""

    def test_complete_job_workflow(self, client: TestClient, auth_headers: dict, test_user: User, test_session: Session):
        """Test complete job creation → processing → completion workflow"""
        
        # 1. Generate presigned URL for upload
        with patch('apps.services.uploads.S3UploadService.generate_presigned_url') as mock_presigned:
            mock_presigned.return_value = "https://example.com/presigned-url"
            
            upload_response = client.post(
                "/api/v1/uploads/presign",
                json={
                    "file_name": "source.jpg",
                    "content_type": "image/jpeg",
                    "file_size": 1024
                },
                headers=auth_headers
            )
        
        assert upload_response.status_code == 200
        upload_data = upload_response.json()
        source_url = upload_data["file_url"]
        
        # 2. Create another presigned URL for target
        with patch('apps.services.uploads.S3UploadService.generate_presigned_url') as mock_presigned:
            mock_presigned.return_value = "https://example.com/presigned-url-2"
            
            target_response = client.post(
                "/api/v1/uploads/presign",
                json={
                    "file_name": "target.jpg",
                    "content_type": "image/jpeg",
                    "file_size": 1024
                },
                headers=auth_headers
            )
        
        assert target_response.status_code == 200
        target_data = target_response.json()
        target_url = target_data["file_url"]
        
        # 3. Create job
        job_data = {
            "source_url": source_url,
            "target_url": target_url,
            "job_type": "face_swap",
            "params": {
                "face_restore": True,
                "upscale": 2,
                "swap_strength": 0.8
            }
        }
        
        initial_credits = test_user.credits
        
        with patch('apps.worker.tasks.process_ai_job.delay') as mock_task:
            mock_task.return_value.id = "test-task-id"
            
            job_response = client.post("/api/v1/jobs", json=job_data, headers=auth_headers)
        
        assert job_response.status_code == 201
        job_data_response = job_response.json()
        job_id = job_data_response["id"]
        
        # 4. Check that credits were deducted
        test_session.refresh(test_user)
        assert test_user.credits < initial_credits
        
        # 5. Check job status
        status_response = client.get(f"/api/v1/jobs/{job_id}", headers=auth_headers)
        assert status_response.status_code == 200
        
        status_data = status_response.json()
        assert status_data["status"] == "pending"
        assert status_data["job_type"] == "face_swap"
        assert status_data["params"]["face_restore"] is True

    def test_user_authentication_flow(self, client: TestClient, test_user: User):
        """Test complete user authentication flow"""
        
        # 1. Login
        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "testpass123"}
        )
        
        assert login_response.status_code == 200
        login_data = login_response.json()
        token = login_data["access_token"]
        
        # 2. Use token to access protected endpoint
        headers = {"Authorization": f"Bearer {token}"}
        me_response = client.get("/api/v1/auth/me", headers=headers)
        
        assert me_response.status_code == 200
        me_data = me_response.json()
        assert me_data["email"] == test_user.email

    def test_error_handling_workflow(self, client: TestClient, auth_headers: dict):
        """Test error handling across different scenarios"""
        
        # 1. Try to create job with invalid params
        invalid_job_data = {
            "source_url": "https://example.com/source.jpg",
            "target_url": "https://example.com/target.jpg", 
            "job_type": "face_swap",
            "params": {
                "upscale": 10,  # Invalid value
                "swap_strength": 2.0  # Invalid value
            }
        }
        
        response = client.post("/api/v1/jobs", json=invalid_job_data, headers=auth_headers)
        assert response.status_code == 422
        
        # 2. Try to access non-existent job
        response = client.get("/api/v1/jobs/non-existent-id", headers=auth_headers)
        assert response.status_code == 404
        
        # 3. Try to upload invalid file type
        response = client.post(
            "/api/v1/uploads/presign",
            json={
                "file_name": "document.pdf",
                "content_type": "application/pdf",
                "file_size": 1024
            },
            headers=auth_headers
        )
        assert response.status_code == 422

    def test_metrics_endpoint(self, client: TestClient):
        """Test that metrics endpoint is accessible"""
        response = client.get("/metrics")
        
        assert response.status_code == 200
        # Check that it returns Prometheus metrics format
        assert "http_requests_total" in response.text or "python_info" in response.text

    def test_health_endpoint(self, client: TestClient):
        """Test health check endpoint"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"