"""
Custom exception classes for SmartLink
"""
from typing import Any, Dict, Optional


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
    """MCP related error"""
    status_code = 500
    code = "MCP_ERROR"
    
    def __init__(self, message: str, server_name: Optional[str] = None):
        details = {"server_name": server_name} if server_name else {}
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