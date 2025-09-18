"""Tests for upload endpoints"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from apps.db.models.user import User


class TestUploads:
    """Test file upload functionality"""

    def test_generate_presigned_url_success(self, client: TestClient, auth_headers: dict):
        """Test successful presigned URL generation"""
        with patch('apps.services.uploads.S3UploadService.generate_presigned_url') as mock_presigned:
            mock_presigned.return_value = "https://example.com/presigned-url"
            
            response = client.post(
                "/api/v1/uploads/presign",
                json={
                    "file_name": "test.jpg",
                    "content_type": "image/jpeg",
                    "file_size": 1024
                },
                headers=auth_headers
            )
        
        assert response.status_code == 200
        data = response.json()
        assert "presigned_url" in data
        assert "file_url" in data
        assert data["presigned_url"] == "https://example.com/presigned-url"

    def test_generate_presigned_url_invalid_mime_type(self, client: TestClient, auth_headers: dict):
        """Test presigned URL generation with invalid MIME type"""
        response = client.post(
            "/api/v1/uploads/presign",
            json={
                "file_name": "test.pdf",
                "content_type": "application/pdf",
                "file_size": 1024
            },
            headers=auth_headers
        )
        
        assert response.status_code == 422
        assert "Invalid file type" in response.json()["detail"]

    def test_generate_presigned_url_file_too_large(self, client: TestClient, auth_headers: dict):
        """Test presigned URL generation with file too large"""
        response = client.post(
            "/api/v1/uploads/presign",
            json={
                "file_name": "large_file.jpg",
                "content_type": "image/jpeg",
                "file_size": 25 * 1024 * 1024  # 25MB, over the 20MB limit
            },
            headers=auth_headers
        )
        
        assert response.status_code == 422
        assert "File too large" in response.json()["detail"]

    def test_generate_presigned_url_unauthorized(self, client: TestClient):
        """Test presigned URL generation without authentication"""
        response = client.post(
            "/api/v1/uploads/presign",
            json={
                "file_name": "test.jpg",
                "content_type": "image/jpeg",
                "file_size": 1024
            }
        )
        
        assert response.status_code == 401

    def test_generate_presigned_url_invalid_file_extension(self, client: TestClient, auth_headers: dict):
        """Test presigned URL generation with invalid file extension"""
        response = client.post(
            "/api/v1/uploads/presign",
            json={
                "file_name": "test.gif",
                "content_type": "image/gif",
                "file_size": 1024
            },
            headers=auth_headers
        )
        
        assert response.status_code == 422
        assert "Invalid file type" in response.json()["detail"]

    def test_generate_presigned_url_empty_filename(self, client: TestClient, auth_headers: dict):
        """Test presigned URL generation with empty filename"""
        response = client.post(
            "/api/v1/uploads/presign",
            json={
                "file_name": "",
                "content_type": "image/jpeg",
                "file_size": 1024
            },
            headers=auth_headers
        )
        
        assert response.status_code == 422