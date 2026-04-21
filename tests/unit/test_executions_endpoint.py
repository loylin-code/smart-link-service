"""
Unit tests for /v1/executions endpoints

Tests execution management API:
- Cancel execution
- Get execution status  
- List execution history

Uses simple test fixtures compatible with existing project setup.
"""
import pytest
from fastapi.testclient import TestClient

from gateway.main import app
from core.config import settings


# ============================================================
# Test Client Setup
# ============================================================

@pytest.fixture(scope="module")
def test_client():
    """Create test client for the FastAPI app (module scope to avoid repeated startup)"""
    return TestClient(app)


@pytest.fixture
def valid_api_key():
    """Valid API key for testing (use master key)"""
    return settings.MASTER_API_KEY


# ============================================================
# Cancel Execution Tests - POST /v1/executions/{execution_id}/cancel
# ============================================================

class TestCancelExecution:
    """Tests for cancel execution endpoint"""
    
    def test_cancel_execution_endpoint_exists(self, test_client, valid_api_key):
        """Test that cancel endpoint exists"""
        response = test_client.post(
            "/v1/executions/test-exec-id/cancel",
            headers={"X-API-Key": valid_api_key}
        )
        # Endpoint should exist - returns 404 for execution not found
        # or 200 if cancelled (depends on InterruptManager state)
        assert response.status_code in [200, 404]
    
    def test_cancel_not_found_returns_404(self, test_client, valid_api_key):
        """Test that cancel of non-existent execution returns 404"""
        response = test_client.post(
            "/v1/executions/nonexistent-exec-id/cancel",
            headers={"X-API-Key": valid_api_key}
        )
        # Should return 404 for not found (not registered in InterruptManager)
        assert response.status_code == 404
    
    def test_cancel_missing_auth_returns_401(self, test_client):
        """Test that cancel without auth returns 401"""
        response = test_client.post(
            "/v1/executions/test-exec-id/cancel"
        )
        assert response.status_code == 401
    
    def test_cancel_invalid_api_key_returns_401(self, test_client):
        """Test that cancel with invalid API key returns 401"""
        response = test_client.post(
            "/v1/executions/test-exec-id/cancel",
            headers={"X-API-Key": "invalid-key"}
        )
        assert response.status_code == 401


# ============================================================
# Get Execution Status Tests - GET /v1/executions/{execution_id}
# ============================================================

class TestGetExecutionStatus:
    """Tests for get execution status endpoint"""
    
    def test_get_execution_endpoint_exists(self, test_client, valid_api_key):
        """Test that get endpoint exists"""
        response = test_client.get(
            "/v1/executions/test-exec-id",
            headers={"X-API-Key": valid_api_key}
        )
        # Endpoint should exist - returns 404 for execution not found
        assert response.status_code == 404
    
    def test_get_not_found_returns_404(self, test_client, valid_api_key):
        """Test that get of non-existent execution returns 404"""
        response = test_client.get(
            "/v1/executions/nonexistent-exec-id",
            headers={"X-API-Key": valid_api_key}
        )
        assert response.status_code == 404
    
    def test_get_missing_auth_returns_401(self, test_client):
        """Test that get without auth returns 401"""
        response = test_client.get("/v1/executions/test-exec-id")
        assert response.status_code == 401
    
    def test_get_invalid_api_key_returns_401(self, test_client):
        """Test that get with invalid API key returns 401"""
        response = test_client.get(
            "/v1/executions/test-exec-id",
            headers={"X-API-Key": "invalid-key"}
        )
        assert response.status_code == 401


# ============================================================
# List Executions Tests - GET /v1/executions
# ============================================================

class TestListExecutions:
    """Tests for list executions endpoint"""
    
    def test_list_executions_endpoint_exists(self, test_client, valid_api_key):
        """Test that list endpoint exists"""
        response = test_client.get(
            "/v1/executions",
            headers={"X-API-Key": valid_api_key}
        )
        # Endpoint should exist and return 200 with empty list
        assert response.status_code == 200
    
    def test_list_executions_returns_paginated_structure(self, test_client, valid_api_key):
        """Test that list returns paginated structure"""
        response = test_client.get(
            "/v1/executions",
            headers={"X-API-Key": valid_api_key}
        )
        
        assert response.status_code == 200
        data = response.json()
        # Should have total and items fields per API spec
        assert "total" in data
        assert "items" in data
        assert isinstance(data["total"], int)
        assert isinstance(data["items"], list)
    
    def test_list_executions_accepts_agent_id_filter(self, test_client, valid_api_key):
        """Test that list accepts agent_id filter"""
        response = test_client.get(
            "/v1/executions?agent_id=agent-001",
            headers={"X-API-Key": valid_api_key}
        )
        assert response.status_code == 200
    
    def test_list_executions_accepts_status_filter(self, test_client, valid_api_key):
        """Test that list accepts status filter"""
        response = test_client.get(
            "/v1/executions?status=completed",
            headers={"X-API-Key": valid_api_key}
        )
        assert response.status_code == 200
    
    def test_list_executions_accepts_limit_param(self, test_client, valid_api_key):
        """Test that list accepts limit parameter"""
        response = test_client.get(
            "/v1/executions?limit=10",
            headers={"X-API-Key": valid_api_key}
        )
        assert response.status_code == 200
    
    def test_list_executions_accepts_offset_param(self, test_client, valid_api_key):
        """Test that list accepts offset parameter"""
        response = test_client.get(
            "/v1/executions?offset=5",
            headers={"X-API-Key": valid_api_key}
        )
        assert response.status_code == 200
    
    def test_list_executions_missing_auth_returns_401(self, test_client):
        """Test that list without auth returns 401"""
        response = test_client.get("/v1/executions")
        assert response.status_code == 401
    
    def test_list_executions_invalid_api_key_returns_401(self, test_client):
        """Test that list with invalid API key returns 401"""
        response = test_client.get(
            "/v1/executions",
            headers={"X-API-Key": "invalid-key"}
        )
        assert response.status_code == 401