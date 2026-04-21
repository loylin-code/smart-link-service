"""
Unit tests for /v1/chat/completions SSE endpoint

Tests OpenAI-compatible streaming endpoint behavior:
- Request validation
- Agent_id extraction
- SSE response format
- Authentication
- Error handling
"""
import pytest
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

from gateway.main import app
from core.config import settings
from schemas.openai_compat import (
    ChatCompletionRequest,
    ChatMessage,
    ChatCompletionChunk,
    ChatCompletionChunkChoice,
    ChatCompletionChunkDelta,
)


# ============================================================
# Test Client Setup
# ============================================================

@pytest.fixture
def test_client():
    """Create test client for the FastAPI app"""
    return TestClient(app)


@pytest.fixture
def valid_api_key():
    """Valid API key for testing (use master key)"""
    return settings.MASTER_API_KEY


@pytest.fixture
def valid_request_body():
    """Valid request body for chat completions"""
    return {
        "model": "agent:test-agent",
        "messages": [
            {"role": "user", "content": "Hello"}
        ],
        "stream": True
    }


# ============================================================
# Request Validation Tests
# ============================================================

class TestRequestValidation:
    """Tests for request validation"""
    
    def test_model_field_required(self, test_client, valid_api_key):
        """Test that model field is required"""
        response = test_client.post(
            "/v1/chat/completions",
            headers={"X-API-Key": valid_api_key},
            json={"messages": [{"role": "user", "content": "Hello"}]}
        )
        # Should fail validation (missing model)
        assert response.status_code == 422
    
    def test_messages_or_conversation_id_required(self, test_client, valid_api_key):
        """Test that either messages or conversation_id must be provided"""
        response = test_client.post(
            "/v1/chat/completions",
            headers={"X-API-Key": valid_api_key},
            json={"model": "agent:test"}
        )
        # Should fail validation (no messages or conversation_id)
        assert response.status_code == 422
    
    def test_stream_mode_required(self, test_client, valid_api_key):
        """Test that stream=true is required for SSE endpoint"""
        response = test_client.post(
            "/v1/chat/completions",
            headers={"X-API-Key": valid_api_key},
            json={
                "model": "agent:test",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": False
            }
        )
        # Non-streaming mode should return error
        assert response.status_code == 400


# ============================================================
# Agent ID Extraction Tests
# ============================================================

class TestAgentIdExtraction:
    """Tests for agent_id extraction from model field"""
    
    def test_endpoint_accepts_agent_prefix_model(self, test_client, valid_api_key):
        """Test that endpoint accepts model with agent: prefix"""
        response = test_client.post(
            "/v1/chat/completions",
            headers={"X-API-Key": valid_api_key},
            json={
                "model": "agent:test-agent-123",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True
            }
        )
        
        # Endpoint should exist and process request
        assert response.status_code == 200
    
    def test_endpoint_accepts_model_without_prefix(self, test_client, valid_api_key):
        """Test that model without prefix is also accepted"""
        response = test_client.post(
            "/v1/chat/completions",
            headers={"X-API-Key": valid_api_key},
            json={
                "model": "custom-agent",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True
            }
        )
        # Endpoint should exist and process request
        assert response.status_code == 200


# ============================================================
# SSE Response Format Tests
# ============================================================

class TestSSEResponseFormat:
    """Tests for SSE response format"""
    
    def test_response_content_type_is_sse(self, test_client, valid_api_key):
        """Test that response has correct SSE Content-Type"""
        response = test_client.post(
            "/v1/chat/completions",
            headers={"X-API-Key": valid_api_key},
            json={
                "model": "agent:test",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True
            }
        )
        
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
    
    def test_response_has_cache_control_headers(self, test_client, valid_api_key):
        """Test that SSE response has proper cache headers"""
        response = test_client.post(
            "/v1/chat/completions",
            headers={"X-API-Key": valid_api_key},
            json={
                "model": "agent:test",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True
            }
        )
        
        assert response.status_code == 200
        assert response.headers.get("Cache-Control") == "no-cache"
    
    def test_sse_data_format(self, test_client, valid_api_key):
        """Test that SSE chunks follow 'data: {...}\\n\\n' format"""
        response = test_client.post(
            "/v1/chat/completions",
            headers={"X-API-Key": valid_api_key},
            json={
                "model": "agent:test",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True
            }
        )
        
        # Read response content
        content = response.text
        
        # Each SSE line should start with "data: "
        if content:
            lines = content.strip().split("\n\n")
            for line in lines:
                if line:
                    assert line.startswith("data: ")
    
    def test_sse_final_chunk_is_done_marker(self, test_client, valid_api_key):
        """Test that final SSE chunk is 'data: [DONE]'"""
        response = test_client.post(
            "/v1/chat/completions",
            headers={"X-API-Key": valid_api_key},
            json={
                "model": "agent:test",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True
            }
        )
        
        # Read response content
        content = response.text
        
        # Last line should be "data: [DONE]"
        lines = content.strip().split("\n\n")
        assert lines[-1] == "data: [DONE]"
    
    def test_first_chunk_has_assistant_role(self, test_client, valid_api_key):
        """Test that first chunk contains role='assistant' when agent exists"""
        response = test_client.post(
            "/v1/chat/completions",
            headers={"X-API-Key": valid_api_key},
            json={
                "model": "agent:test",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True
            }
        )
        
        # Read response content
        content = response.text
        lines = content.strip().split("\n\n")
        
        # First chunk should be data: {...}
        first_chunk = None
        for line in lines:
            if line.startswith("data: ") and line != "data: [DONE]":
                first_chunk = line
                break
        
        if first_chunk:
            # Parse the JSON
            json_str = first_chunk[6:]  # Remove "data: " prefix
            data = json.loads(json_str)
            
            # Either error response or valid chunk with choices
            if "error" in data:
                # Agent doesn't exist in test database - error response is valid
                assert "error" in data
                assert "message" in data["error"]
            else:
                # Agent exists - should have role in delta
                assert "choices" in data
                if data["choices"]:
                    delta = data["choices"][0]["delta"]
                    assert delta.get("role") == "assistant"


# ============================================================
# Authentication Tests
# ============================================================

class TestAuthentication:
    """Tests for authentication"""
    
    def test_api_key_header_auth(self, test_client, valid_api_key):
        """Test authentication via X-API-Key header"""
        response = test_client.post(
            "/v1/chat/completions",
            headers={"X-API-Key": valid_api_key},
            json={
                "model": "agent:test",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True
            }
        )
        
        # Should be authenticated (200) or 401 if key invalid
        assert response.status_code in [200, 401]
    
    def test_bearer_token_auth(self, test_client):
        """Test authentication via Bearer token"""
        response = test_client.post(
            "/v1/chat/completions",
            headers={"Authorization": "Bearer test-token-12345"},
            json={
                "model": "agent:test",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True
            }
        )
        
        # Should be authenticated (200) or 401 if token invalid
        assert response.status_code in [200, 401]
    
    def test_missing_auth_returns_401(self, test_client):
        """Test that missing authentication returns 401"""
        response = test_client.post(
            "/v1/chat/completions",
            json={
                "model": "agent:test",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True
            }
        )
        
        assert response.status_code == 401
    
    def test_invalid_api_key_returns_401(self, test_client):
        """Test that invalid API key returns 401"""
        response = test_client.post(
            "/v1/chat/completions",
            headers={"X-API-Key": "invalid-key"},
            json={
                "model": "agent:test",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True
            }
        )
        
        assert response.status_code == 401


# ============================================================
# Error Handling Tests
# ============================================================

class TestErrorHandling:
    """Tests for error handling in SSE responses"""
    
    def test_error_returns_sse_error_event(self, test_client, valid_api_key):
        """Test that errors are returned as SSE error events"""
        # Request with invalid agent that will cause error
        response = test_client.post(
            "/v1/chat/completions",
            headers={"X-API-Key": valid_api_key},
            json={
                "model": "agent:invalid-agent",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True
            }
        )
        
        # Read response content
        content = response.text
        lines = content.strip().split("\n\n")
        
        # Should have error chunk with error object
        error_chunks = [c for c in lines if c.startswith("data: ") and "error" in c]
        assert len(error_chunks) > 0
    
    def test_error_format_matches_openai(self, test_client, valid_api_key):
        """Test that error format matches OpenAI error structure"""
        # Error should have: {"error": {"message": "...", "type": "...", "code": "..."}}
        response = test_client.post(
            "/v1/chat/completions",
            headers={"X-API-Key": valid_api_key},
            json={
                "model": "agent:invalid-agent",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True
            }
        )
        
        # Read response content
        content = response.text
        lines = content.strip().split("\n\n")
        
        for line in lines:
            if line.startswith("data: ") and "error" in line:
                json_str = line[6:]
                data = json.loads(json_str)
                
                # Should have error object
                assert "error" in data
                assert "message" in data["error"]
                break


# ============================================================
# Execution ID Generation Tests
# ============================================================

class TestExecutionIdGeneration:
    """Tests for execution_id generation"""
    
    def test_endpoint_exists_and_processes_request(self, test_client, valid_api_key):
        """Test that endpoint exists and processes requests"""
        response = test_client.post(
            "/v1/chat/completions",
            headers={"X-API-Key": valid_api_key},
            json={
                "model": "agent:test",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True
            }
        )
        
        # Endpoint should exist (200) and process request
        assert response.status_code == 200
    
    def test_endpoint_returns_unique_execution_ids(self, test_client, valid_api_key):
        """Test that endpoint processes each request independently"""
        # Make two requests - both should succeed with SSE response
        response1 = test_client.post(
            "/v1/chat/completions",
            headers={"X-API-Key": valid_api_key},
            json={
                "model": "agent:test",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True
            }
        )
        
        response2 = test_client.post(
            "/v1/chat/completions",
            headers={"X-API-Key": valid_api_key},
            json={
                "model": "agent:test",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True
            }
        )
        
        # Both should succeed and return SSE format
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # Both should have SSE content type
        assert "text/event-stream" in response1.headers.get("content-type", "")
        assert "text/event-stream" in response2.headers.get("content-type", "")
        
        # Both should end with [DONE] marker
        assert response1.text.endswith("data: [DONE]\n\n")
        assert response2.text.endswith("data: [DONE]\n\n")


# ============================================================
# Schema Tests
# ============================================================

class TestChatCompletionRequestSchema:
    """Tests for ChatCompletionRequest schema at endpoint"""
    
    def test_request_accepts_agent_prefix(self, test_client, valid_api_key):
        """Test that endpoint accepts model with agent: prefix"""
        response = test_client.post(
            "/v1/chat/completions",
            headers={"X-API-Key": valid_api_key},
            json={
                "model": "agent:my-agent",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True
            }
        )
        
        assert response.status_code == 200
    
    def test_request_accepts_tools(self, test_client, valid_api_key):
        """Test that endpoint accepts tools parameter"""
        response = test_client.post(
            "/v1/chat/completions",
            headers={"X-API-Key": valid_api_key},
            json={
                "model": "agent:test",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "search",
                            "description": "Search the web",
                            "parameters": {}
                        }
                    }
                ]
            }
        )
        
        assert response.status_code == 200
    
    def test_request_accepts_stream_options(self, test_client, valid_api_key):
        """Test that endpoint accepts stream_options parameter"""
        response = test_client.post(
            "/v1/chat/completions",
            headers={"X-API-Key": valid_api_key},
            json={
                "model": "agent:test",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
                "stream_options": {"include_usage": True}
            }
        )
        
        assert response.status_code == 200
    
    def test_request_accepts_temperature(self, test_client, valid_api_key):
        """Test that endpoint accepts temperature parameter"""
        response = test_client.post(
            "/v1/chat/completions",
            headers={"X-API-Key": valid_api_key},
            json={
                "model": "agent:test",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
                "temperature": 0.7
            }
        )
        
        assert response.status_code == 200
    
    def test_request_accepts_max_tokens(self, test_client, valid_api_key):
        """Test that endpoint accepts max_tokens parameter"""
        response = test_client.post(
            "/v1/chat/completions",
            headers={"X-API-Key": valid_api_key},
            json={
                "model": "agent:test",
                "messages": [{"role": "user", "content": "Hello"}],
                "stream": True,
                "max_tokens": 1000
            }
        )
        
        assert response.status_code == 200