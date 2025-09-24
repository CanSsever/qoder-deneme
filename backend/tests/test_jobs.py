"""Tests for job management endpoints"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session
from unittest.mock import patch

from apps.db.models.user import User
from apps.db.models.job import Job


class TestJobs:
    """Test job management functionality"""

    def test_create_job_success(self, client: TestClient, auth_headers: dict, test_user: User):
        """Test successful job creation"""
        job_data = {
            "source_url": "https://example.com/source.jpg",
            "target_url": "https://example.com/target.jpg",
            "job_type": "face_swap",
            "params": {
                "face_restore": True,
                "upscale": 2,
                "swap_strength": 0.8
            }
        }
        
        with patch('apps.worker.tasks.process_ai_job.delay') as mock_task:
            mock_task.return_value.id = "test-task-id"
            
            response = client.post("/api/v1/jobs", json=job_data, headers=auth_headers)
        
        assert response.status_code == 201
        data = response.json()
        assert data["source_url"] == job_data["source_url"]
        assert data["target_url"] == job_data["target_url"]
        assert data["status"] == "pending"
        assert data["job_type"] == job_data["job_type"]
        assert data["params"] == job_data["params"]
        assert "id" in data

    def test_create_job_insufficient_credits(self, client: TestClient, auth_headers: dict, test_session: Session, test_user: User):
        """Test job creation with insufficient credits"""
        # Set user credits to 0
        test_user.credits = 0
        test_session.add(test_user)
        test_session.commit()
        
        job_data = {
            "source_url": "https://example.com/source.jpg",
            "target_url": "https://example.com/target.jpg",
            "job_type": "face_swap",
            "params": {"face_restore": True}
        }
        
        response = client.post("/api/v1/jobs", json=job_data, headers=auth_headers)
        
        assert response.status_code == 402
        assert "insufficient credits" in response.json()["detail"].lower()

    def test_create_job_invalid_params(self, client: TestClient, auth_headers: dict):
        """Test job creation with invalid parameters"""
        job_data = {
            "source_url": "https://example.com/source.jpg",
            "target_url": "https://example.com/target.jpg",
            "job_type": "face_swap",
            "params": {
                "upscale": 10,  # Invalid upscale value (max is 4)
                "swap_strength": 1.5  # Invalid strength value (max is 1.0)
            }
        }
        
        response = client.post("/api/v1/jobs", json=job_data, headers=auth_headers)
        
        assert response.status_code == 422

    def test_create_job_rate_limit_exceeded(self, client: TestClient, auth_headers: dict, test_session: Session, test_user: User):
        """Test job creation when daily rate limit is exceeded"""
        # Create multiple jobs to exceed daily limit for free plan
        job_data = {
            "source_url": "https://example.com/source.jpg",
            "target_url": "https://example.com/target.jpg",
            "job_type": "face_swap",
            "params": {"face_restore": True}
        }
        
        # Create 5 jobs (free plan limit)
        for i in range(5):
            job = Job(
                user_id=test_user.id,
                source_url=f"https://example.com/source{i}.jpg",
                target_url=f"https://example.com/target{i}.jpg",
                status="completed",
                job_type="face_swap"
            )
            test_session.add(job)
        test_session.commit()
        
        with patch('apps.worker.tasks.process_ai_job.delay') as mock_task:
            mock_task.return_value.id = "test-task-id"
            response = client.post("/api/v1/jobs", json=job_data, headers=auth_headers)
        
        assert response.status_code == 429
        assert "daily limit" in response.json()["detail"].lower()

    def test_get_job_success(self, client: TestClient, auth_headers: dict, test_job: Job):
        """Test successful job retrieval"""
        response = client.get(f"/api/v1/jobs/{test_job.id}", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(test_job.id)
        assert data["status"] == test_job.status
        assert data["job_type"] == test_job.job_type

    def test_get_job_not_found(self, client: TestClient, auth_headers: dict):
        """Test getting non-existent job"""
        response = client.get("/api/v1/jobs/nonexistent-id", headers=auth_headers)
        
        assert response.status_code == 404

    def test_get_job_unauthorized(self, client: TestClient, test_job: Job):
        """Test getting job without authentication"""
        response = client.get(f"/api/v1/jobs/{test_job.id}")
        
        assert response.status_code == 401

    def test_get_jobs_list(self, client: TestClient, auth_headers: dict, test_job: Job):
        """Test getting user's jobs list"""
        response = client.get("/api/v1/jobs", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(job["id"] == str(test_job.id) for job in data)