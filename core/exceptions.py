"""
Custom exception classes for SmartLink
"""
from typing import Any, Dict, List, Optional


class SmartLinkException(Exception):
    """Base exception for SmartLink"""
    status_code = 400  # Default HTTP status code
    
    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code or "UNKNOWN_ERROR"
        self.details = details or {}
        super().__init__(self.message)


class AuthenticationError(SmartLinkException):
    """Authentication failed"""
    status_code = 401
    code = "AUTHENTICATION_ERROR"
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, code=self.code)


class AuthorizationError(SmartLinkException):
    """Authorization failed"""
    status_code = 403
    code = "AUTHORIZATION_ERROR"
    
    def __init__(self, message: str = "Access denied"):
        super().__init__(message, code=self.code)


class NotFoundError(SmartLinkException):
    """Resource not found"""
    status_code = 404
    code = "NOT_FOUND"
    
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            f"{resource} with id '{identifier}' not found",
            code=self.code,
            details={"resource": resource, "identifier": identifier}
        )


class ValidationError(SmartLinkException):
    """Validation error"""
    status_code = 400
    code = "VALIDATION_ERROR"
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code=self.code, details=details)


class LLMError(SmartLinkException):
    """LLM related error"""
    status_code = 500
    code = "LLM_ERROR"
    
    def __init__(self, message: str, provider: Optional[str] = None):
        details = {"provider": provider} if provider else {}
        super().__init__(message, code=self.code, details=details)


class AgentError(SmartLinkException):
    """Agent execution error"""
    status_code = 500
    code = "AGENT_ERROR"
    
    def __init__(self, message: str, agent_id: Optional[str] = None):
        details = {"agent_id": agent_id} if agent_id else {}
        super().__init__(message, code=self.code, details=details)


class SkillError(SmartLinkException):
    """Skill execution error"""
    status_code = 500
    code = "SKILL_ERROR"
    
    def __init__(self, skill_name: str, message: str):
        super().__init__(
            f"Skill '{skill_name}' failed: {message}",
            code=self.code,
            details={"skill_name": skill_name}
        )


class MCPError(SmartLinkException):
    """MCP error with recovery suggestions
    
    Attributes:
        message: Error message
        suggestions: List of recovery suggestions
        server_name: MCP Server name (optional)
        tool_name: MCP Tool name (optional)
    """
    status_code = 500
    code = "MCP_ERROR"
    
    def __init__(
        self,
        message: str,
        suggestions: Optional[List[str]] = None,
        server_name: Optional[str] = None,
        tool_name: Optional[str] = None
    ):
        details = {}
        if server_name:
            details["server_name"] = server_name
        if tool_name:
            details["tool_name"] = tool_name
        if suggestions:
            details["suggestions"] = suggestions
        self.suggestions = suggestions or []
        self.server_name = server_name
        self.tool_name = tool_name
        super().__init__(message, code=self.code, details=details)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            "error": self.message,
            "type": "mcp_error",
            "suggestions": self.suggestions,
            "server_name": self.server_name,
            "tool_name": self.tool_name
        }


class PluginLoadError(SmartLinkException):
    """Plugin loading error"""
    status_code = 500
    code = "PLUGIN_LOAD_ERROR"
    
    def __init__(
        self,
        message: str,
        plugin_name: Optional[str] = None,
        suggestions: Optional[List[str]] = None
    ):
        details = {}
        if plugin_name:
            details["plugin_name"] = plugin_name
        if suggestions:
            details["suggestions"] = suggestions
        self.suggestions = suggestions or []
        self.plugin_name = plugin_name
        super().__init__(message, code=self.code, details=details)


class DatabaseError(SmartLinkException):
    """Database operation error"""
    status_code = 503
    code = "DATABASE_ERROR"
    
    def __init__(self, message: str, operation: Optional[str] = None):
        details = {"operation": operation} if operation else {}
        super().__init__(message, code=self.code, details=details)


class RedisError(SmartLinkException):
    """Redis operation error"""
    status_code = 503
    code = "REDIS_ERROR"
    
    def __init__(self, message: str, operation: Optional[str] = None):
        details = {"operation": operation} if operation else {}
        super().__init__(message, code=self.code, details=details)


class SessionNotFoundError(SmartLinkException):
    """Session not found error"""
    status_code = 404
    code = "SESSION_NOT_FOUND"
    
    def __init__(self, session_id: str):
        super().__init__(
            f"Session '{session_id}' not found",
            code=self.code,
            details={"session_id": session_id}
        )


class QuotaExceededError(SmartLinkException):
    """Quota exceeded error"""
    status_code = 429
    code = "QUOTA_EXCEEDED"
    
    def __init__(self, message: str = "Quota exceeded"):
        super().__init__(message, code=self.code)


class RateLimitError(SmartLinkException):
    """Rate limit exceeded error"""
    status_code = 429
    code = "RATE_LIMIT_EXCEEDED"
    
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message, code=self.code)


# =============================================================================
# Streaming Exceptions
# =============================================================================


class StreamError(SmartLinkException):
    """Base exception for streaming errors"""
    status_code = 500
    code = "STREAM_ERROR"
    
    def __init__(
        self,
        message: str,
        error_type: str = "server_error",
        error_code: str = "internal_error",
        agent_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        details: Optional[dict] = None
    ):
        self.error_type = error_type
        self.error_code = error_code
        self.agent_id = agent_id
        self.execution_id = execution_id
        merged_details = {}
        if agent_id:
            merged_details["agent_id"] = agent_id
        if execution_id:
            merged_details["execution_id"] = execution_id
        if details:
            merged_details.update(details)
        super().__init__(message, code=self.code, details=merged_details if merged_details else None)


class AuthenticationError(StreamError):
    """Authentication error for streaming"""
    status_code = 401
    code = "AUTHENTICATION_ERROR"
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            error_type="invalid_request_error",
            error_code="invalid_api_key"
        )


class RateLimitError(StreamError):
    """Rate limit error for streaming"""
    status_code = 429
    code = "RATE_LIMIT_EXCEEDED"
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: Optional[int] = None
    ):
        super().__init__(
            message=message,
            error_type="rate_limit_error",
            error_code="rate_limit_exceeded"
        )
        self.retry_after = retry_after


class AgentNotFoundError(StreamError):
    """Agent not found error"""
    status_code = 404
    code = "AGENT_NOT_FOUND"
    
    def __init__(self, agent_id: str):
        super().__init__(
            message=f"Agent '{agent_id}' not found",
            error_type="invalid_request_error",
            error_code="agent_not_found",
            agent_id=agent_id
        )


class ExecutionNotFoundError(StreamError):
    """Execution not found error"""
    status_code = 404
    code = "EXECUTION_NOT_FOUND"
    
    def __init__(self, execution_id: str):
        super().__init__(
            message=f"Execution '{execution_id}' not found",
            error_type="invalid_request_error",
            error_code="execution_not_found",
            execution_id=execution_id
        )


class LLMStreamError(StreamError):
    """LLM streaming error"""
    status_code = 500
    code = "LLM_STREAM_ERROR"
    
    def __init__(
        self,
        message: str = "LLM stream error",
        provider: Optional[str] = None
    ):
        details = {"provider": provider} if provider else {}
        super().__init__(
            message=message,
            error_type="server_error",
            error_code="llm_stream_error",
            details=details
        )
        self.provider = provider


class ToolExecutionError(StreamError):
    """Tool execution error during streaming"""
    status_code = 500
    code = "TOOL_EXECUTION_ERROR"
    
    def __init__(
        self,
        message: str = "Tool execution error",
        tool_name: str = "",
        tool_call_id: Optional[str] = None
    ):
        details = {"tool_name": tool_name}
        if tool_call_id:
            details["tool_call_id"] = tool_call_id
        super().__init__(
            message=message,
            error_type="server_error",
            error_code="tool_execution_error",
            details=details
        )
        self.tool_name = tool_name
        self.tool_call_id = tool_call_id


class ContextLengthExceededError(StreamError):
    """Context length exceeded error"""
    status_code = 400
    code = "CONTEXT_LENGTH_EXCEEDED"
    
    def __init__(self, max_tokens: int):
        super().__init__(
            message=f"Context length exceeded. Maximum tokens: {max_tokens}",
            error_type="invalid_request_error",
            error_code="context_length_exceeded"
        )
        self.max_tokens = max_tokens


class StreamTimeoutError(StreamError):
    """Stream timeout error"""
    status_code = 504
    code = "STREAM_TIMEOUT"
    
    def __init__(self, timeout_seconds: int):
        super().__init__(
            message=f"Stream timeout after {timeout_seconds} seconds",
            error_type="server_error",
            error_code="stream_timeout"
        )
        self.timeout_seconds = timeout_seconds


class StreamCancelledError(StreamError):
    """Stream cancelled error"""
    status_code = 499
    code = "STREAM_CANCELLED"
    
    def __init__(self, execution_id: str):
        super().__init__(
            message="Stream cancelled",
            error_type="server_error",
            error_code="stream_cancelled",
            execution_id=execution_id
        )
        self.execution_id = execution_id