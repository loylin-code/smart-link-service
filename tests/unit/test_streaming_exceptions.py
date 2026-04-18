"""
Tests for streaming exception types
"""
import pytest
from core.exceptions import (
    StreamError,
    AuthenticationError,
    RateLimitError,
    AgentNotFoundError,
    ExecutionNotFoundError,
    LLMStreamError,
    ToolExecutionError,
    ContextLengthExceededError,
    StreamTimeoutError,
    StreamCancelledError,
)


class TestStreamError:
    """Test StreamError base class"""

    def test_stream_error_creation(self):
        """Test creating StreamError with all parameters"""
        exc = StreamError(
            message="Stream failed",
            error_type="server_error",
            error_code="internal_error",
            agent_id="agent_123",
            execution_id="exec_456",
        )
        assert exc.message == "Stream failed"
        assert exc.error_type == "server_error"
        assert exc.error_code == "internal_error"
        assert exc.agent_id == "agent_123"
        assert exc.execution_id == "exec_456"

    def test_stream_error_defaults(self):
        """Test StreamError default values"""
        exc = StreamError(message="Test error")
        assert exc.message == "Test error"
        assert exc.error_type == "server_error"
        assert exc.error_code == "internal_error"
        assert exc.agent_id is None
        assert exc.execution_id is None

    def test_stream_error_is_exception(self):
        """Test StreamError is an Exception subclass"""
        exc = StreamError(message="Test")
        assert isinstance(exc, Exception)


class TestAuthenticationError:
    """Test AuthenticationError"""

    def test_authentication_error_creation(self):
        """Test creating AuthenticationError"""
        exc = AuthenticationError(message="Invalid API key")
        assert exc.message == "Invalid API key"
        assert exc.error_type == "invalid_request_error"
        assert exc.error_code == "invalid_api_key"

    def test_authentication_error_defaults(self):
        """Test AuthenticationError default message"""
        exc = AuthenticationError()
        assert exc.message == "Authentication failed"
        assert exc.error_type == "invalid_request_error"
        assert exc.error_code == "invalid_api_key"

    def test_authentication_error_inherits_stream_error(self):
        """Test AuthenticationError inherits from StreamError"""
        exc = AuthenticationError()
        assert isinstance(exc, StreamError)


class TestRateLimitError:
    """Test RateLimitError"""

    def test_rate_limit_error_creation(self):
        """Test creating RateLimitError with retry_after"""
        exc = RateLimitError(message="Rate limit exceeded", retry_after=60)
        assert exc.message == "Rate limit exceeded"
        assert exc.error_type == "rate_limit_error"
        assert exc.error_code == "rate_limit_exceeded"
        assert exc.retry_after == 60

    def test_rate_limit_error_defaults(self):
        """Test RateLimitError default values"""
        exc = RateLimitError()
        assert exc.message == "Rate limit exceeded"
        assert exc.error_type == "rate_limit_error"
        assert exc.error_code == "rate_limit_exceeded"
        assert exc.retry_after is None

    def test_rate_limit_error_inherits_stream_error(self):
        """Test RateLimitError inherits from StreamError"""
        exc = RateLimitError()
        assert isinstance(exc, StreamError)


class TestAgentNotFoundError:
    """Test AgentNotFoundError"""

    def test_agent_not_found_creation(self):
        """Test creating AgentNotFoundError with agent_id"""
        exc = AgentNotFoundError(agent_id="agent_123")
        assert "agent_123" in exc.message
        assert exc.error_type == "invalid_request_error"
        assert exc.error_code == "agent_not_found"
        assert exc.agent_id == "agent_123"

    def test_agent_not_found_inherits_stream_error(self):
        """Test AgentNotFoundError inherits from StreamError"""
        exc = AgentNotFoundError(agent_id="test")
        assert isinstance(exc, StreamError)


class TestExecutionNotFoundError:
    """Test ExecutionNotFoundError"""

    def test_execution_not_found_creation(self):
        """Test creating ExecutionNotFoundError with execution_id"""
        exc = ExecutionNotFoundError(execution_id="exec_456")
        assert "exec_456" in exc.message
        assert exc.error_type == "invalid_request_error"
        assert exc.error_code == "execution_not_found"
        assert exc.execution_id == "exec_456"

    def test_execution_not_found_inherits_stream_error(self):
        """Test ExecutionNotFoundError inherits from StreamError"""
        exc = ExecutionNotFoundError(execution_id="test")
        assert isinstance(exc, StreamError)


class TestLLMStreamError:
    """Test LLMStreamError"""

    def test_llm_stream_error_creation(self):
        """Test creating LLMStreamError with provider"""
        exc = LLMStreamError(message="LLM stream failed", provider="openai")
        assert exc.message == "LLM stream failed"
        assert exc.error_type == "server_error"
        assert exc.error_code == "llm_stream_error"
        assert exc.provider == "openai"

    def test_llm_stream_error_defaults(self):
        """Test LLMStreamError default values"""
        exc = LLMStreamError()
        assert exc.message == "LLM stream error"
        assert exc.error_type == "server_error"
        assert exc.error_code == "llm_stream_error"
        assert exc.provider is None

    def test_llm_stream_error_inherits_stream_error(self):
        """Test LLMStreamError inherits from StreamError"""
        exc = LLMStreamError()
        assert isinstance(exc, StreamError)


class TestToolExecutionError:
    """Test ToolExecutionError"""

    def test_tool_execution_error_creation(self):
        """Test creating ToolExecutionError with tool_name"""
        exc = ToolExecutionError(
            message="Tool failed",
            tool_name="web_search",
            tool_call_id="call_123",
        )
        assert exc.message == "Tool failed"
        assert exc.error_type == "server_error"
        assert exc.error_code == "tool_execution_error"
        assert exc.tool_name == "web_search"
        assert exc.tool_call_id == "call_123"

    def test_tool_execution_error_defaults(self):
        """Test ToolExecutionError default values"""
        exc = ToolExecutionError(tool_name="test_tool")
        assert exc.message == "Tool execution error"
        assert exc.error_type == "server_error"
        assert exc.error_code == "tool_execution_error"
        assert exc.tool_name == "test_tool"
        assert exc.tool_call_id is None

    def test_tool_execution_error_inherits_stream_error(self):
        """Test ToolExecutionError inherits from StreamError"""
        exc = ToolExecutionError(tool_name="test")
        assert isinstance(exc, StreamError)


class TestContextLengthExceededError:
    """Test ContextLengthExceededError"""

    def test_context_length_exceeded_creation(self):
        """Test creating ContextLengthExceededError with max_tokens"""
        exc = ContextLengthExceededError(max_tokens=4096)
        assert "4096" in exc.message
        assert exc.error_type == "invalid_request_error"
        assert exc.error_code == "context_length_exceeded"

    def test_context_length_exceeded_inherits_stream_error(self):
        """Test ContextLengthExceededError inherits from StreamError"""
        exc = ContextLengthExceededError(max_tokens=4096)
        assert isinstance(exc, StreamError)


class TestStreamTimeoutError:
    """Test StreamTimeoutError"""

    def test_stream_timeout_creation(self):
        """Test creating StreamTimeoutError with timeout_seconds"""
        exc = StreamTimeoutError(timeout_seconds=30)
        assert "30" in exc.message
        assert exc.error_type == "server_error"
        assert exc.error_code == "stream_timeout"

    def test_stream_timeout_inherits_stream_error(self):
        """Test StreamTimeoutError inherits from StreamError"""
        exc = StreamTimeoutError(timeout_seconds=30)
        assert isinstance(exc, StreamError)


class TestStreamCancelledError:
    """Test StreamCancelledError"""

    def test_stream_cancelled_creation(self):
        """Test creating StreamCancelledError with execution_id"""
        exc = StreamCancelledError(execution_id="exec_789")
        assert exc.message == "Stream cancelled"
        assert exc.error_type == "server_error"
        assert exc.error_code == "stream_cancelled"
        assert exc.execution_id == "exec_789"

    def test_stream_cancelled_inherits_stream_error(self):
        """Test StreamCancelledError inherits from StreamError"""
        exc = StreamCancelledError(execution_id="test")
        assert isinstance(exc, StreamError)
