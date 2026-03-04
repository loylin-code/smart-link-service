"""
Custom exception classes for SmartLink
"""
from typing import Any, Dict, Optional


class SmartLinkException(Exception):
    """Base exception for SmartLink"""
    
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
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, code="AUTHENTICATION_ERROR")


class AuthorizationError(SmartLinkException):
    """Authorization failed"""
    
    def __init__(self, message: str = "Access denied"):
        super().__init__(message, code="AUTHORIZATION_ERROR")


class NotFoundError(SmartLinkException):
    """Resource not found"""
    
    def __init__(self, resource: str, identifier: str):
        super().__init__(
            f"{resource} with id '{identifier}' not found",
            code="NOT_FOUND",
            details={"resource": resource, "identifier": identifier}
        )


class ValidationError(SmartLinkException):
    """Validation error"""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="VALIDATION_ERROR", details=details)


class LLMError(SmartLinkException):
    """LLM related error"""
    
    def __init__(self, message: str, provider: Optional[str] = None):
        details = {"provider": provider} if provider else {}
        super().__init__(message, code="LLM_ERROR", details=details)


class AgentError(SmartLinkException):
    """Agent execution error"""
    
    def __init__(self, message: str, agent_id: Optional[str] = None):
        details = {"agent_id": agent_id} if agent_id else {}
        super().__init__(message, code="AGENT_ERROR", details=details)


class SkillError(SmartLinkException):
    """Skill execution error"""
    
    def __init__(self, skill_name: str, message: str):
        super().__init__(
            f"Skill '{skill_name}' failed: {message}",
            code="SKILL_ERROR",
            details={"skill_name": skill_name}
        )


class MCPError(SmartLinkException):
    """MCP related error"""
    
    def __init__(self, message: str, server_name: Optional[str] = None):
        details = {"server_name": server_name} if server_name else {}
        super().__init__(message, code="MCP_ERROR", details=details)


class DatabaseError(SmartLinkException):
    """Database operation error"""
    
    def __init__(self, message: str, operation: Optional[str] = None):
        details = {"operation": operation} if operation else {}
        super().__init__(message, code="DATABASE_ERROR", details=details)


class RedisError(SmartLinkException):
    """Redis operation error"""
    
    def __init__(self, message: str, operation: Optional[str] = None):
        details = {"operation": operation} if operation else {}
        super().__init__(message, code="REDIS_ERROR", details=details)