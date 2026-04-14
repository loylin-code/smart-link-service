# Error Handling Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance error handling with HTTP status code mapping and unified error response format.

**Architecture:** Add status_code property to exceptions, create RequestIDMiddleware, update exception handlers with proper status codes and response format.

**Tech Stack:** FastAPI, Starlette middleware, Pydantic

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `core/exceptions.py` | Modify | Add status_code class attribute |
| `gateway/middleware/request_id.py` | Create | RequestIDMiddleware for tracing |
| `gateway/middleware/__init__.py` | Modify | Export RequestIDMiddleware |
| `gateway/main.py` | Modify | Register middleware, update handlers |
| `tests/unit/test_error_handling.py` | Create | Unit tests for error responses |

---

### Task 1: Add status_code to Exception Classes

**Files:**
- Modify: `core/exceptions.py`

- [ ] **Step 1: Add status_code to SmartLinkException base class**

Edit `core/exceptions.py` line 7-19, add status_code class attribute:

```python
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
```

- [ ] **Step 2: Add status_code to each exception subclass**

Edit each exception class to set its specific status_code:

```python
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
```

- [ ] **Step 3: Run import test**

Run: `python -c "from core.exceptions import AuthenticationError, NotFoundError; print('OK')"`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add core/exceptions.py
git commit -m "feat(exceptions): add status_code property for HTTP status mapping"
```

---

### Task 2: Create RequestIDMiddleware

**Files:**
- Create: `gateway/middleware/request_id.py`
- Modify: `gateway/middleware/__init__.py`

- [ ] **Step 1: Create gateway/middleware/request_id.py**

```python
"""
Request ID Middleware - Adds unique identifier to each request
"""
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware that generates a unique request ID for each request.
    
    The request ID is:
    - Stored in request.state.request_id
    - Added to response headers as X-Request-ID
    - Available to exception handlers for error responses
    """
    
    async def dispatch(self, request: Request, call_next):
        # Generate unique request ID
        request_id = f"req_{uuid.uuid4().hex[:16]}"
        
        # Store in request state for access in handlers
        request.state.request_id = request_id
        
        # Process request
        response = await call_next(request)
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response
```

- [ ] **Step 2: Update gateway/middleware/__init__.py exports**

Add RequestIDMiddleware to exports:

```python
from gateway.middleware.request_id import RequestIDMiddleware

__all__ = [
    "AuthMiddleware",
    "LoggingMiddleware",
    "RateLimitMiddleware",
    "RequestIDMiddleware",  # NEW
]
```

- [ ] **Step 3: Run import test**

Run: `python -c "from gateway.middleware import RequestIDMiddleware; print('OK')"`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add gateway/middleware/request_id.py gateway/middleware/__init__.py
git commit -m "feat(middleware): add RequestIDMiddleware for request tracing"
```

---

### Task 3: Update Exception Handlers in main.py

**Files:**
- Modify: `gateway/main.py`

- [ ] **Step 1: Add imports for datetime and RequestIDMiddleware**

At top of `gateway/main.py`, add imports:

```python
from datetime import datetime
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException
from gateway.middleware import AuthMiddleware, LoggingMiddleware, RateLimitMiddleware, RequestIDMiddleware
```

- [ ] **Step 2: Add RequestIDMiddleware to middleware stack**

Edit middleware registration (around line 267), add RequestIDMiddleware first:

```python
# Add custom middleware (order matters: first added = last executed)
app.add_middleware(RequestIDMiddleware)  # First - generates request_id
app.add_middleware(LoggingMiddleware)
app.add_middleware(AuthMiddleware)
if settings.RATE_LIMIT_ENABLED:
    app.add_middleware(RateLimitMiddleware)
```

- [ ] **Step 3: Update SmartLinkException handler**

Replace existing handler (around line 274-284):

```python
@app.exception_handler(SmartLinkException)
async def smartlink_exception_handler(request: Request, exc: SmartLinkException):
    """Handle custom exceptions with proper HTTP status codes"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "details": exc.details,
            "timestamp": int(datetime.utcnow().timestamp() * 1000),
            "requestId": getattr(request.state, "request_id", "unknown"),
            "path": str(request.url.path)
        }
    )
```

- [ ] **Step 4: Add HTTPException handler**

Add after SmartLinkException handler:

```python
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle FastAPI HTTPExceptions with unified format"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": f"HTTP_{exc.status_code}",
            "message": exc.detail,
            "details": {},
            "timestamp": int(datetime.utcnow().timestamp() * 1000),
            "requestId": getattr(request.state, "request_id", "unknown"),
            "path": str(request.url.path)
        }
    )
```

- [ ] **Step 5: Update general exception handler**

Replace existing handler (around line 287-307):

```python
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    request_id = getattr(request.state, "request_id", "unknown")
    
    # Log the error with request context
    import logging
    logger = logging.getLogger(__name__)
    logger.exception(
        f"Unexpected error: {exc}",
        extra={
            "request_id": request_id,
            "path": str(request.url.path)
        }
    )
    
    if settings.DEBUG:
        import traceback
        return JSONResponse(
            status_code=500,
            content={
                "code": "INTERNAL_ERROR",
                "message": str(exc),
                "details": {"traceback": traceback.format_exc()},
                "timestamp": int(datetime.utcnow().timestamp() * 1000),
                "requestId": request_id,
                "path": str(request.url.path)
            }
        )
    
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "details": {},
            "timestamp": int(datetime.utcnow().timestamp() * 1000),
            "requestId": request_id,
            "path": str(request.url.path)
        }
    )
```

- [ ] **Step 6: Run import test**

Run: `python -c "from gateway.main import app; print('OK')"`
Expected: OK

- [ ] **Step 7: Commit**

```bash
git add gateway/main.py
git commit -m "feat(error-handling): update exception handlers with status codes and unified format"
```

---

### Task 4: Create Unit Tests

**Files:**
- Create: `tests/unit/test_error_handling.py`

- [ ] **Step 1: Create tests/unit/test_error_handling.py**

```python
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
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/unit/test_error_handling.py -v`
Expected: PASS (18 tests)

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_error_handling.py
git commit -m "test(error-handling): add unit tests for exception status codes"
```

---

### Task 5: Run Full Test Suite

**Files:**
- All modified files

- [ ] **Step 1: Run all unit tests**

Run: `pytest tests/unit/ -v`
Expected: All tests PASS

- [ ] **Step 2: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat(error-handling): complete error handling enhancement

- HTTP status code mapping for all exception types
- Unified error response format with requestId, timestamp, path
- RequestIDMiddleware for request tracing
- RateLimitError exception added
- Unit tests for exception status codes

Error handling enhancement complete."
```

---

## Self-Review Checklist

| Spec Section | Covered by Task |
|--------------|-----------------|
| HTTP Status Code Table | Task 1, Task 4 |
| Unified Response Format | Task 3 |
| RequestIDMiddleware | Task 2 |
| Enhanced Exception Handlers | Task 3 |
| Test Coverage | Task 4, Task 5 |

**Placeholder Scan:** No TBD/TODO

**Type Consistency:** status_code used consistently across all exception classes