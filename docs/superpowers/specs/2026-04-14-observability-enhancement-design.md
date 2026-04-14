# Observability Enhancement Design Specification

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:writing-plans to create implementation plan after user approves this spec.

**Created:** 2026-04-14
**Status:** Draft
**Scope:** Phase 3 - Observability Enhancement (Structured Logging + Audit)

---

## 1. Overview

### 1.1 Purpose

Enhance SmartLink's observability infrastructure with:
1. **Structured JSON Logging** - Replace print() with Python logging module, JSON format
2. **Mixed Output** - stdout + file dual output
3. **Audit Logging** - Separate audit trail for sensitive operations
4. **Tracing Headers** - Reserve trace_id/span_id for future distributed tracing

### 1.2 Current State

**gateway/middleware/logging.py:**
- Uses print() for logging (not structured)
- Simple text format: "GET /api/v1/agents - Status: 200 - Duration: 0.150s"
- No JSON format
- No request_id correlation
- No audit separation

**core/config.py:**
- LOG_LEVEL: str = "INFO"
- LOG_FORMAT: str = "json" (configured but not used)

### 1.3 Target State

```
Logging Architecture:
├── stdout → JSON logs (container/system collection)
├── logs/app.log → JSON logs (local debugging)
├── logs/audit.log → JSON audit trail (sensitive operations)
└── logs/error.log → JSON error logs (error aggregation)
```

---

## 2. JSON Log Format

### 2.1 Standard Log Structure

```json
{
  "timestamp": "2026-04-14T10:30:00.123Z",
  "level": "INFO",
  "logger": "gateway.middleware.logging",
  "message": "Request processed successfully",
  "request_id": "req_abc123def456",
  "tenant_id": "tenant_001",
  "user_id": "user_001",
  "path": "/api/v1/agents",
  "method": "GET",
  "status": 200,
  "duration_ms": 150,
  "trace_id": null,
  "span_id": null,
  "extra": {
    "agent_id": "agent_001",
    "model": "gpt-4"
  }
}
```

### 2.2 Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| timestamp | string | Yes | ISO 8601 timestamp with milliseconds |
| level | string | Yes | Log level: DEBUG/INFO/WARNING/ERROR/CRITICAL |
| logger | string | Yes | Python logger name |
| message | string | Yes | Human-readable message |
| request_id | string | Yes | Unique request identifier |
| tenant_id | string | No | Tenant identifier (multi-tenant) |
| user_id | string | No | User identifier (authenticated) |
| path | string | No | Request path |
| method | string | No | HTTP method |
| status | int | No | HTTP status code |
| duration_ms | int | No | Request duration in milliseconds |
| trace_id | string | No | Distributed tracing ID (reserved) |
| span_id | string | No | Span identifier (reserved) |
| extra | object | No | Additional context |

### 2.3 Audit Log Structure

```json
{
  "timestamp": "2026-04-14T10:30:00.123Z",
  "level": "INFO",
  "logger": "audit",
  "message": "Agent created",
  "request_id": "req_abc123",
  "tenant_id": "tenant_001",
  "user_id": "user_001",
  "action": "agent.create",
  "resource_type": "Agent",
  "resource_id": "agent_001",
  "changes": {
    "name": "Customer Service Agent",
    "model": "gpt-4"
  },
  "ip_address": "192.168.1.100",
  "user_agent": "Mozilla/5.0..."
}
```

### 2.4 Error Log Structure

```json
{
  "timestamp": "2026-04-14T10:30:00.123Z",
  "level": "ERROR",
  "logger": "agent.llm.client",
  "message": "LLM API call failed",
  "request_id": "req_abc123",
  "error_type": "LLMError",
  "error_code": "LLM_ERROR",
  "error_message": "Rate limit exceeded",
  "stack_trace": "Traceback...",
  "extra": {
    "model": "gpt-4",
    "provider": "openai"
  }
}
```

---

## 3. Logging Configuration

### 3.1 Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| LOG_LEVEL | INFO | Minimum log level |
| LOG_FORMAT | json | Log format: json/text |
| LOG_DIR | logs | Log directory |
| LOG_MAX_SIZE | 10MB | Max log file size |
| LOG_BACKUP_COUNT | 5 | Number of backup files |
| LOG_STDOUT | true | Enable stdout output |
| LOG_FILE | true | Enable file output |

### 3.2 Log File Rotation

- **Max size**: 10MB per file
- **Backup count**: 5 files
- **Rotation**: Automatic when max size reached
- **Compression**: Optional (future)

---

## 4. LoggingMiddleware Enhancement

### 4.1 Implementation

```python
# gateway/middleware/logging.py

import time
import logging
import json
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from core.config import settings
from core.logging import get_logger, StructuredFormatter

logger = get_logger("gateway.middleware.logging")


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Enhanced logging middleware with structured JSON format.
    
    Features:
    - JSON structured logging
    - request_id correlation
    - duration tracking
    - stdout + file dual output
    """
    
    EXCLUDE_PATHS = ['/health', '/metrics', '/docs', '/openapi.json']
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with structured logging"""
        
        # Skip excluded paths
        if request.url.path in self.EXCLUDE_PATHS:
            return await call_next(request)
        
        # Get request context
        request_id = getattr(request.state, 'request_id', 'unknown')
        tenant_id = getattr(request.state, 'tenant_id', None)
        user_id = getattr(request.state, 'user_id', None)
        
        start_time = time.time()
        
        # Log request start
        logger.info(
            "Request started",
            extra={
                'request_id': request_id,
                'tenant_id': tenant_id,
                'user_id': user_id,
                'path': request.url.path,
                'method': request.method,
            }
        )
        
        try:
            response = await call_next(request)
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Log request completed
            logger.info(
                "Request completed",
                extra={
                    'request_id': request_id,
                    'tenant_id': tenant_id,
                    'user_id': user_id,
                    'path': request.url.path,
                    'method': request.method,
                    'status': response.status_code,
                    'duration_ms': duration_ms,
                }
            )
            
            response.headers["X-Process-Time"] = str(duration_ms)
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            
            logger.error(
                "Request failed",
                extra={
                    'request_id': request_id,
                    'tenant_id': tenant_id,
                    'user_id': user_id,
                    'path': request.url.path,
                    'method': request.method,
                    'duration_ms': duration_ms,
                    'error_type': type(e).__name__,
                    'error_message': str(e),
                },
                exc_info=True
            )
            
            raise
```

---

## 5. Audit Logging Service

### 5.1 AuditLogger Class

```python
# core/logging/audit.py

import logging
from typing import Optional, Dict, Any
from datetime import datetime

from core.logging import get_logger

audit_logger = get_logger("audit", file_name="audit.log")


class AuditLogger:
    """
    Audit trail logger for sensitive operations.
    
    Audit events:
    - user.login/user.logout
    - agent.create/agent.update/agent.delete
    - api_key.create/api_key.delete
    - mcp_server.connect/mcp_server.disconnect
    - permission.grant/permission.revoke
    """
    
    @staticmethod
    def log(
        action: str,
        resource_type: str,
        resource_id: str,
        request_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        changes: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """Log audit event"""
        
        audit_logger.info(
            f"{action} - {resource_type}:{resource_id}",
            extra={
                'request_id': request_id,
                'tenant_id': tenant_id,
                'user_id': user_id,
                'action': action,
                'resource_type': resource_type,
                'resource_id': resource_id,
                'changes': changes or {},
                'ip_address': ip_address,
                'user_agent': user_agent,
                'timestamp': datetime.utcnow().isoformat() + 'Z',
            }
        )
```

### 5.2 Audit Event Types

| Event | Description |
|-------|-------------|
| user.login | User authenticated |
| user.logout | User session ended |
| agent.create | Agent created |
| agent.update | Agent configuration changed |
| agent.delete | Agent deleted |
| agent.activate | Agent activated |
| agent.pause | Agent paused |
| api_key.create | API key generated |
| api_key.delete | API key revoked |
| mcp_server.connect | MCP server connected |
| mcp_server.disconnect | MCP server disconnected |
| permission.grant | Permission granted |
| permission.revoke | Permission revoked |

---

## 6. Core Logging Module

### 6.1 StructuredFormatter

```python
# core/logging/formatter.py

import json
import logging
from datetime import datetime


class StructuredFormatter(logging.Formatter):
    """
    JSON structured log formatter.
    
    Output format:
    {
      "timestamp": "2026-04-14T10:30:00Z",
      "level": "INFO",
      "logger": "...",
      "message": "...",
      ...
    }
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        
        log_data = {
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        
        # Add extra fields
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id
        if hasattr(record, 'tenant_id'):
            log_data['tenant_id'] = record.tenant_id
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id
        if hasattr(record, 'path'):
            log_data['path'] = record.path
        if hasattr(record, 'method'):
            log_data['method'] = record.method
        if hasattr(record, 'status'):
            log_data['status'] = record.status
        if hasattr(record, 'duration_ms'):
            log_data['duration_ms'] = record.duration_ms
        if hasattr(record, 'trace_id'):
            log_data['trace_id'] = record.trace_id
        if hasattr(record, 'span_id'):
            log_data['span_id'] = record.span_id
        if hasattr(record, 'extra'):
            log_data['extra'] = record.extra
        
        # Add exception info if present
        if record.exc_info:
            log_data['error_type'] = record.exc_info[0].__name__ if record.exc_info[0] else None
            log_data['error_message'] = str(record.exc_info[1]) if record.exc_info[1] else None
            log_data['stack_trace'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)
```

### 6.2 get_logger Helper

```python
# core/logging/__init__.py

import logging
import sys
import os
from logging.handlers import RotatingFileHandler
from typing import Optional

from core.config import settings
from core.logging.formatter import StructuredFormatter


def get_logger(
    name: str,
    file_name: Optional[str] = None,
    level: Optional[str] = None
) -> logging.Logger:
    """
    Get configured logger with structured JSON format.
    
    Args:
        name: Logger name
        file_name: Optional separate file name
        level: Optional log level override
    
    Returns:
        Configured logger instance
    """
    
    logger = logging.getLogger(name)
    
    # Set level
    log_level = level or settings.LOG_LEVEL
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Clear existing handlers
    logger.handlers.clear()
    
    formatter = StructuredFormatter()
    
    # Stdout handler
    if settings.LOG_STDOUT:
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(formatter)
        logger.addHandler(stdout_handler)
    
    # File handler
    if settings.LOG_FILE:
        log_dir = settings.LOG_DIR or "logs"
        os.makedirs(log_dir, exist_ok=True)
        
        file = file_name or "app.log"
        file_path = os.path.join(log_dir, file)
        
        file_handler = RotatingFileHandler(
            file_path,
            maxBytes=settings.LOG_MAX_SIZE or 10 * 1024 * 1024,
            backupCount=settings.LOG_BACKUP_COUNT or 5,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger
```

---

## 7. Integration Points

### 7.1 Use in Services

```python
# services/agent_service.py

from core.logging import get_logger
from core.logging.audit import AuditLogger

logger = get_logger("services.agent_service")

async def create_agent(...):
    logger.info("Creating agent", extra={'agent_name': name, 'model': model})
    
    # ... agent creation logic
    
    AuditLogger.log(
        action="agent.create",
        resource_type="Agent",
        resource_id=agent.id,
        request_id=request_id,
        tenant_id=tenant_id,
        user_id=user_id,
        changes={'name': name, 'model': model},
    )
```

### 7.2 Use in Agent Runtime

```python
# agent/core/orchestrator.py

from agent.metrics import record_agent_execution
from core.logging import get_logger

logger = get_logger("agent.orchestrator")

async def execute(...):
    logger.debug("Starting agent execution", extra={'agent_id': agent_id, 'input': input})
    
    # ... execution
    
    logger.info("Agent execution completed", extra={
        'agent_id': agent_id,
        'duration_ms': duration * 1000,
        'tokens_used': tokens,
    })
```

---

## 8. Implementation Tasks

| Task | Files | Purpose |
|------|-------|---------|
| Task 1 | `core/logging/__init__.py` | Create get_logger helper |
| Task 2 | `core/logging/formatter.py` | Create StructuredFormatter |
| Task 3 | `core/logging/audit.py` | Create AuditLogger |
| Task 4 | `core/config.py` | Add logging config variables |
| Task 5 | `gateway/middleware/logging.py` | Enhance LoggingMiddleware |
| Task 6 | Integrate into services | Add logging to key services |
| Task 7 | `tests/unit/test_logging.py` | Unit tests |

---

## 9. Test Coverage

| Test | Purpose |
|------|---------|
| test_structured_formatter_outputs_json | Verify JSON output |
| test_get_logger_returns_configured_logger | Verify logger setup |
| test_loggingmiddleware_logs_request_id | Verify request_id in logs |
| test_audit_logger_logs_audit_event | Verify audit format |

---

## 10. Self-Review Checklist

| Item | Status |
|------|--------|
| Placeholder scan | ✅ No TBD/TODO |
| Internal consistency | ✅ Log format consistent |
| Scope check | ✅ Logging enhancement only |
| Ambiguity check | ✅ Clear field definitions |

---

## 11. Notes

- stdout output for container log collection (Docker/K8s)
- File output for local debugging and audit retention
- Audit log separate from app log for compliance
- trace_id/span_id reserved for future distributed tracing (Jaeger/Zipkin)
- Log rotation prevents unlimited file growth