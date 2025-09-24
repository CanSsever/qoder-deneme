"""Tests for authentication endpoints"""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from apps.db.models.user import User


class TestAuth:
    """Test authentication functionality"""

    def test_login_success(self, client: TestClient, test_user: User):
        """Test successful login"""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "testpass123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_invalid_credentials(self, client: TestClient, test_user: User):
        """Test login with invalid credentials"""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": test_user.email, "password": "wrongpassword"}
        )
        
        assert response.status_code == 401
        assert "Incorrect username or password" in response.json()["detail"]

    def test_login_nonexistent_user(self, client: TestClient):
        """Test login with non-existent user"""
        response = client.post(
            "/api/v1/auth/login",
            json={"email": "nonexistent@example.com", "password": "password"}
        )
        
        assert response.status_code == 401

    def test_get_current_user(self, client: TestClient, auth_headers: dict, test_user: User):
        """Test getting current user info"""
        response = client.get("/api/v1/auth/me", headers=auth_headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert data["credits"] == test_user.credits
        assert data["is_active"] == test_user.is_active

    def test_get_current_user_unauthorized(self, client: TestClient):
        """Test getting current user without authentication"""
        response = client.get("/api/v1/auth/me")
        
        assert response.status_code == 401

    def test_get_current_user_invalid_token(self, client: TestClient):
        """Test getting current user with invalid token"""
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid_token"}
        )
        
        assert response.status_code == 401