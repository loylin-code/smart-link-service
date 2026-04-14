"""
Error handling unit tests - HTTP status codes and response format
"""
import pytest
from unittest.mock import MagicMock
from datetime import datetime

from core.exceptions import (
    SmartLinkException,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ValidationError,
    QuotaExceededError,
    RateLimitError,
    LLMError,
    AgentError,
    SkillError,
    MCPError,
    DatabaseError,
    RedisError,
    SessionNotFoundError
)


class TestExceptionStatusCodes:
    """Test exception classes have correct status_code"""
    
    def test_base_exception_has_400(self):
        """Base SmartLinkException should have status_code 400"""
        assert SmartLinkException.status_code == 400
    
    def test_authentication_error_has_401(self):
        """AuthenticationError should have status_code 401"""
        assert AuthenticationError.status_code == 401
    
    def test_authorization_error_has_403(self):
        """AuthorizationError should have status_code 403"""
        assert AuthorizationError.status_code == 403
    
    def test_not_found_error_has_404(self):
        """NotFoundError should have status_code 404"""
        assert NotFoundError.status_code == 404
    
    def test_session_not_found_has_404(self):
        """SessionNotFoundError should have status_code 404"""
        assert SessionNotFoundError.status_code == 404
    
    def test_validation_error_has_400(self):
        """ValidationError should have status_code 400"""
        assert ValidationError.status_code == 400
    
    def test_quota_exceeded_has_429(self):
        """QuotaExceededError should have status_code 429"""
        assert QuotaExceededError.status_code == 429
    
    def test_rate_limit_error_has_429(self):
        """RateLimitError should have status_code 429"""
        assert RateLimitError.status_code == 429
    
    def test_llm_error_has_500(self):
        """LLMError should have status_code 500"""
        assert LLMError.status_code == 500
    
    def test_agent_error_has_500(self):
        """AgentError should have status_code 500"""
        assert AgentError.status_code == 500
    
    def test_skill_error_has_500(self):
        """SkillError should have status_code 500"""
        assert SkillError.status_code == 500
    
    def test_mcp_error_has_500(self):
        """MCPError should have status_code 500"""
        assert MCPError.status_code == 500
    
    def test_database_error_has_503(self):
        """DatabaseError should have status_code 503"""
        assert DatabaseError.status_code == 503
    
    def test_redis_error_has_503(self):
        """RedisError should have status_code 503"""
        assert RedisError.status_code == 503


class TestExceptionAttributes:
    """Test exception attributes are set correctly"""
    
    def test_authentication_error_has_correct_code(self):
        exc = AuthenticationError()
        assert exc.code == "AUTHENTICATION_ERROR"
        assert exc.message == "Authentication failed"
    
    def test_not_found_error_has_resource_details(self):
        exc = NotFoundError("Agent", "agent_123")
        assert exc.code == "NOT_FOUND"
        assert exc.details["resource"] == "Agent"
        assert exc.details["identifier"] == "agent_123"
    
    def test_llm_error_has_provider_details(self):
        exc = LLMError("Model failed", provider="openai")
        assert exc.code == "LLM_ERROR"
        assert exc.details["provider"] == "openai"
    
    def test_rate_limit_error_is_defined(self):
        """RateLimitError should be a valid exception"""
        exc = RateLimitError("Too many requests")
        assert exc.code == "RATE_LIMIT_EXCEEDED"
        assert exc.message == "Too many requests"