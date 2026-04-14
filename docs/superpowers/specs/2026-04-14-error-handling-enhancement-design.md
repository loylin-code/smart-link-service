# Error Handling Enhancement Design Specification

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:writing-plans to create implementation plan after user approves this spec.

**Created:** 2026-04-14
**Status:** Draft
**Scope:** Core Enhancement - HTTP Status Mapping + Unified Error Response

---

## 1. Overview

### 1.1 Purpose

Enhance SmartLink's error handling system with:
1. **HTTP Status Code Mapping** - Return correct HTTP status codes based on exception type
2. **Unified Error Response Format** - Add `timestamp`, `request_id`, `path` to all error responses

### 1.2 Current State

**core/exceptions.py:**
- `SmartLinkException` base class with `code`, `message`, `details`
- 12 exception subclasses defined

**gateway/main.py:**
- `smartlink_exception_handler` - Returns 400 for all SmartLinkException
- `general_exception_handler` - Returns 500 for all other exceptions

**Issues:**
- All custom exceptions return 400 (incorrect for 401, 403, 404, etc.)
- No `request_id` for tracing
- No `timestamp` in response
- Missing `path` for debugging

---

## 2. HTTP Status Code Mapping

### 2.1 Status Code Table

| Exception Class | HTTP Status | Status Name |
|-----------------|-------------|-------------|
| AuthenticationError | 401 | Unauthorized |
| AuthorizationError | 403 | Forbidden |
| NotFoundError | 404 | Not Found |
| SessionNotFoundError | 404 | Not Found |
| ValidationError | 400 | Bad Request |
| QuotaExceededError | 429 | Too Many Requests |
| RateLimitError (new) | 429 | Too Many Requests |
| LLMError | 500 | Internal Server Error |
| AgentError | 500 | Internal Server Error |
| SkillError | 500 | Internal Server Error |
| MCPError | 500 | Internal Server Error |
| DatabaseError | 503 | Service Unavailable |
| RedisError | 503 | Service Unavailable |
| SmartLinkException (default) | 400 | Bad Request |

### 2.2 Implementation Approach

Add `status_code` property to each exception class:

```python
class SmartLinkException(Exception):
    """Base exception for SmartLink"""
    status_code = 400  # Default
    
    def __init__(self, message: str, code: str = None, details: dict = None):
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
```

---

## 3. Unified Error Response Format

### 3.1 Response Structure

```json
{
  "code": "NOT_FOUND",
  "message": "Agent with id 'agent_123' not found",
  "details": {
    "resource": "Agent",
    "identifier": "agent_123"
  },
  "timestamp": 1709123456789,
  "requestId": "req_abc123def456",
  "path": "/api/v1/agents/agent_123"
}
```

### 3.2 Fields

| Field | Type | Description |
|-------|------|-------------|
| code | string | Error code from exception |
| message | string | Human-readable error message |
| details | object | Additional context (optional) |
| timestamp | integer | Unix timestamp in milliseconds |
| requestId | string | Unique request identifier |
| path | string | Request path that caused the error |

---

## 4. Request ID Middleware

### 4.1 Purpose

Add unique identifier to each request for tracing and debugging.

### 4.2 Implementation

Create `RequestIDMiddleware`:
- Generate `request_id` using `uuid.uuid4().hex[:16]`
- Store in `request.state.request_id`
- Add to response headers: `X-Request-ID`
- Pass to error handlers via `request.state`

```python
class RequestIDMiddleware:
    async def dispatch(self, request, call_next):
        request_id = f"req_{uuid.uuid4().hex[:16]}"
        request.state.request_id = request_id
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
```

---

## 5. Enhanced Exception Handler

### 5.1 Updated Handler

```python
@app.exception_handler(SmartLinkException)
async def smartlink_exception_handler(request: Request, exc: SmartLinkException):
    """Handle custom exceptions with proper status codes"""
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

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle FastAPI HTTPExceptions"""
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

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    logger.exception(f"Unexpected error: {exc}", extra={
        "request_id": getattr(request.state, "request_id", "unknown"),
        "path": str(request.url.path)
    })
    
    if settings.DEBUG:
        return JSONResponse(
            status_code=500,
            content={
                "code": "INTERNAL_ERROR",
                "message": str(exc),
                "details": {"traceback": traceback.format_exc()},
                "timestamp": int(datetime.utcnow().timestamp() * 1000),
                "requestId": getattr(request.state, "request_id", "unknown"),
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
            "requestId": getattr(request.state, "request_id", "unknown"),
            "path": str(request.url.path)
        }
    )
```

---

## 6. Structured Logging Enhancement

### 6.1 Log Format

```json
{
  "level": "ERROR",
  "timestamp": "2026-04-14T10:30:00Z",
  "message": "Agent execution failed",
  "request_id": "req_abc123",
  "user_id": "user_001",
  "tenant_id": "tenant_001",
  "error_code": "AGENT_ERROR",
  "error_details": {"agent_id": "agent_123"},
  "stack_trace": "..."
}
```

### 6.2 Logging Middleware Update

Update `LoggingMiddleware` to:
- Include `request_id` in all logs
- Include `tenant_id` from `request.state.tenant_context`
- Use JSON format when `LOG_FORMAT=json`

---

## 7. Implementation Tasks

| Task | Files | Purpose |
|------|-------|---------|
| Task 1 | `core/exceptions.py` | Add status_code property to all exceptions |
| Task 2 | `gateway/middleware/request_id.py` | Create RequestIDMiddleware |
| Task 3 | `gateway/main.py` | Register middleware, update exception handlers |
| Task 4 | `gateway/middleware/logging.py` | Update logging format |
| Task 5 | `tests/unit/test_error_handling.py` | Add unit tests |

---

## 8. Test Coverage

| Test | Purpose |
|------|---------|
| test_authentication_error_returns_401 | Verify 401 status |
| test_authorization_error_returns_403 | Verify 403 status |
| test_not_found_error_returns_404 | Verify 404 status |
| test_validation_error_returns_400 | Verify 400 status |
| test_quota_exceeded_returns_429 | Verify 429 status |
| test_llm_error_returns_500 | Verify 500 status |
| test_database_error_returns_503 | Verify 503 status |
| test_error_response_has_request_id | Verify requestId in response |
| test_error_response_has_timestamp | Verify timestamp in response |
| test_error_response_has_path | Verify path in response |

---

## 9. Future Iterations (Not in Scope)

- **Retry Mechanism** - Automatic retry for transient failures
- **Circuit Breaker** - Prevent cascading failures
- **Rate Limiting** - Per-user request limits
- **Error Analytics** - Track error frequency and patterns

---

## 10. Self-Review Checklist

| Item | Status |
|------|--------|
| Placeholder scan | ✅ No TBD/TODO |
| Internal consistency | ✅ Status codes match exception types |
| Scope check | ✅ Core enhancement only |
| Ambiguity check | ✅ Clear implementation tasks |