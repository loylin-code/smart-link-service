# Observability Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance observability with structured JSON logging, audit trail, and mixed stdout/file output.

**Architecture:** Create core/logging module with StructuredFormatter, get_logger helper, and AuditLogger. Enhance LoggingMiddleware with structured output.

**Tech Stack:** Python logging module, RotatingFileHandler, JSON

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `core/logging/__init__.py` | Create | get_logger helper with dual output |
| `core/logging/formatter.py` | Create | StructuredFormatter for JSON |
| `core/logging/audit.py` | Create | AuditLogger for sensitive operations |
| `core/config.py` | Modify | Add logging config variables |
| `gateway/middleware/logging.py` | Modify | Enhance with structured logging |
| `tests/unit/test_logging.py` | Create | Unit tests for logging |

---

### Task 1: Create StructuredFormatter

**Files:**
- Create: `core/logging/__init__.py` (empty placeholder)
- Create: `core/logging/formatter.py`

- [ ] **Step 1: Create core/logging directory**

```bash
mkdir -p core/logging
```

- [ ] **Step 2: Create core/logging/__init__.py placeholder**

```python
"""
Core logging module - structured JSON logging
"""
```

- [ ] **Step 3: Create core/logging/formatter.py**

```python
"""
Structured JSON log formatter
"""
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
      "request_id": "...",
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
        
        # Add extra fields from record
        extra_fields = [
            'request_id', 'tenant_id', 'user_id', 
            'path', 'method', 'status', 'duration_ms',
            'trace_id', 'span_id', 'extra',
            'action', 'resource_type', 'resource_id', 'changes',
            'ip_address', 'user_agent',
            'error_type', 'error_message', 'stack_trace',
        ]
        
        for field in extra_fields:
            if hasattr(record, field):
                log_data[field] = getattr(record, field)
        
        # Add exception info if present
        if record.exc_info:
            log_data['error_type'] = record.exc_info[0].__name__ if record.exc_info[0] else None
            log_data['error_message'] = str(record.exc_info[1]) if record.exc_info[1] else None
            log_data['stack_trace'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)
```

- [ ] **Step 4: Verify import**

Run: `python -c "from core.logging.formatter import StructuredFormatter; print('OK')"`
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add core/logging/
git commit -m "feat(logging): add StructuredFormatter for JSON log format"
```

---

### Task 2: Create get_logger Helper

**Files:**
- Modify: `core/logging/__init__.py`

- [ ] **Step 1: Update core/logging/__init__.py**

```python
"""
Core logging module - structured JSON logging with dual output
"""
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
        name: Logger name (e.g., 'gateway.middleware.logging')
        file_name: Optional separate file name (e.g., 'audit.log')
        level: Optional log level override
    
    Returns:
        Configured logger instance with stdout and file handlers
    """
    
    logger = logging.getLogger(name)
    
    # Set level
    log_level = level or getattr(settings, 'LOG_LEVEL', 'INFO')
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # Clear existing handlers (avoid duplicate logs)
    logger.handlers.clear()
    
    # Create formatter
    formatter = StructuredFormatter()
    
    # Stdout handler (for container log collection)
    if getattr(settings, 'LOG_STDOUT', True):
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(formatter)
        stdout_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        logger.addHandler(stdout_handler)
    
    # File handler (for local debugging and audit)
    if getattr(settings, 'LOG_FILE', True):
        log_dir = getattr(settings, 'LOG_DIR', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        file = file_name or 'app.log'
        file_path = os.path.join(log_dir, file)
        
        max_bytes = getattr(settings, 'LOG_MAX_SIZE', 10 * 1024 * 1024)  # 10MB
        backup_count = getattr(settings, 'LOG_BACKUP_COUNT', 5)
        
        file_handler = RotatingFileHandler(
            file_path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(getattr(logging, log_level.upper(), logging.INFO))
        logger.addHandler(file_handler)
    
    # Prevent propagation to root logger
    logger.propagate = False
    
    return logger
```

- [ ] **Step 2: Verify import**

Run: `python -c "from core.logging import get_logger; logger = get_logger('test'); print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add core/logging/__init__.py
git commit -m "feat(logging): add get_logger helper with stdout/file dual output"
```

---

### Task 3: Create AuditLogger

**Files:**
- Create: `core/logging/audit.py`

- [ ] **Step 1: Create core/logging/audit.py**

```python
"""
Audit logging for sensitive operations
"""
from typing import Optional, Dict, Any
from datetime import datetime

from core.logging import get_logger

# Separate audit logger with dedicated file
audit_logger = get_logger('audit', file_name='audit.log', level='INFO')


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
        """
        Log audit event.
        
        Args:
            action: Action type (e.g., 'agent.create')
            resource_type: Resource type (e.g., 'Agent')
            resource_id: Resource identifier
            request_id: Request ID for correlation
            tenant_id: Tenant identifier
            user_id: User identifier
            changes: Dict of changes made
            ip_address: Client IP address
            user_agent: Client user agent
        """
        
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
            }
        )
    
    @staticmethod
    def log_login(request_id: str, user_id: str, tenant_id: Optional[str] = None, 
                  ip_address: Optional[str] = None, user_agent: Optional[str] = None):
        """Log user login"""
        AuditLogger.log(
            action='user.login',
            resource_type='User',
            resource_id=user_id,
            request_id=request_id,
            tenant_id=tenant_id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    
    @staticmethod
    def log_logout(request_id: str, user_id: str, tenant_id: Optional[str] = None):
        """Log user logout"""
        AuditLogger.log(
            action='user.logout',
            resource_type='User',
            resource_id=user_id,
            request_id=request_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )
    
    @staticmethod
    def log_agent_create(request_id: str, agent_id: str, name: str, 
                         tenant_id: Optional[str] = None, user_id: Optional[str] = None,
                         changes: Optional[Dict[str, Any]] = None):
        """Log agent creation"""
        AuditLogger.log(
            action='agent.create',
            resource_type='Agent',
            resource_id=agent_id,
            request_id=request_id,
            tenant_id=tenant_id,
            user_id=user_id,
            changes={'name': name, **(changes or {})},
        )
    
    @staticmethod
    def log_agent_delete(request_id: str, agent_id: str,
                          tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """Log agent deletion"""
        AuditLogger.log(
            action='agent.delete',
            resource_type='Agent',
            resource_id=agent_id,
            request_id=request_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )
    
    @staticmethod
    def log_mcp_connect(request_id: str, server_name: str,
                         tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """Log MCP server connection"""
        AuditLogger.log(
            action='mcp_server.connect',
            resource_type='MCPServer',
            resource_id=server_name,
            request_id=request_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )
    
    @staticmethod
    def log_mcp_disconnect(request_id: str, server_name: str,
                            tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """Log MCP server disconnection"""
        AuditLogger.log(
            action='mcp_server.disconnect',
            resource_type='MCPServer',
            resource_id=server_name,
            request_id=request_id,
            tenant_id=tenant_id,
            user_id=user_id,
        )
```

- [ ] **Step 2: Verify import**

Run: `python -c "from core.logging.audit import AuditLogger; AuditLogger.log('test', 'Test', '123', 'req_1'); print('OK')"`
Expected: OK (and logs/test.log created)

- [ ] **Step 3: Commit**

```bash
git add core/logging/audit.py
git commit -m "feat(logging): add AuditLogger for sensitive operation tracking"
```

---

### Task 4: Add Logging Config Variables

**Files:**
- Modify: `core/config.py`

- [ ] **Step 1: Add logging configuration to Settings class**

Find the LOG_LEVEL and LOG_FORMAT lines in `core/config.py` and replace with expanded logging config:

```python
    # Logging Configuration
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Log level: DEBUG/INFO/WARNING/ERROR/CRITICAL"
    )
    LOG_FORMAT: str = Field(
        default="json",
        description="Log format: 'json' for structured, 'text' for plain"
    )
    LOG_DIR: str = Field(
        default="logs",
        description="Directory for log files"
    )
    LOG_STDOUT: bool = Field(
        default=True,
        description="Enable stdout logging (for container collection)"
    )
    LOG_FILE: bool = Field(
        default=True,
        description="Enable file logging"
    )
    LOG_MAX_SIZE: int = Field(
        default=10 * 1024 * 1024,  # 10MB
        description="Maximum log file size in bytes"
    )
    LOG_BACKUP_COUNT: int = Field(
        default=5,
        description="Number of backup log files to keep"
    )
```

- [ ] **Step 2: Verify settings load**

Run: `python -c "from core.config import settings; print(settings.LOG_LEVEL, settings.LOG_DIR)"`
Expected: INFO logs

- [ ] **Step 3: Commit**

```bash
git add core/config.py
git commit -m "feat(config): add logging configuration variables"
```

---

### Task 5: Enhance LoggingMiddleware

**Files:**
- Modify: `gateway/middleware/logging.py`

- [ ] **Step 1: Replace existing LoggingMiddleware implementation**

Replace entire file with:

```python
"""
Request logging middleware with structured JSON format
"""
import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from core.logging import get_logger

logger = get_logger("gateway.middleware.logging")


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Enhanced logging middleware with structured JSON format.
    
    Features:
    - JSON structured logging
    - request_id correlation from RequestIDMiddleware
    - tenant_id and user_id context
    - duration tracking in milliseconds
    - stdout + file dual output
    
    Note: Requires RequestIDMiddleware to be registered before this middleware
    """
    
    # Paths to exclude from logging
    EXCLUDE_PATHS = ['/health', '/metrics', '/docs', '/openapi.json', '/redoc']
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with structured logging"""
        
        # Skip excluded paths
        path = request.url.path
        if path in self.EXCLUDE_PATHS or path.startswith('/docs') or path.startswith('/openapi'):
            return await call_next(request)
        
        # Get context from request state (set by RequestIDMiddleware)
        request_id = getattr(request.state, 'request_id', 'unknown')
        tenant_id = getattr(request.state, 'tenant_id', None)
        user_id = getattr(request.state, 'user_id', None)
        
        start_time = time.time()
        
        # Log request started
        logger.info(
            "Request started",
            extra={
                'request_id': request_id,
                'tenant_id': tenant_id,
                'user_id': user_id,
                'path': path,
                'method': request.method,
            }
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Log request completed
            logger.info(
                "Request completed",
                extra={
                    'request_id': request_id,
                    'tenant_id': tenant_id,
                    'user_id': user_id,
                    'path': path,
                    'method': request.method,
                    'status': response.status_code,
                    'duration_ms': duration_ms,
                }
            )
            
            # Add timing and request_id headers
            response.headers["X-Process-Time"] = str(duration_ms)
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Log request failed
            logger.error(
                "Request failed",
                extra={
                    'request_id': request_id,
                    'tenant_id': tenant_id,
                    'user_id': user_id,
                    'path': path,
                    'method': request.method,
                    'status': 500,
                    'duration_ms': duration_ms,
                },
                exc_info=True
            )
            
            raise
```

- [ ] **Step 2: Verify app loads**

Run: `python -c "from gateway.main import app; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add gateway/middleware/logging.py
git commit -m "feat(logging): enhance LoggingMiddleware with structured JSON format"
```

---

### Task 6: Create Unit Tests

**Files:**
- Create: `tests/unit/test_logging.py`

- [ ] **Step 1: Create tests/unit/test_logging.py**

```python
"""
Logging module unit tests
"""
import pytest
import logging
import json
import os

from core.logging import get_logger
from core.logging.formatter import StructuredFormatter
from core.logging.audit import AuditLogger


class TestStructuredFormatter:
    """Test StructuredFormatter JSON output"""
    
    def test_formatter_outputs_json(self):
        """Formatter should output valid JSON"""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='Test message',
            args=(),
            exc_info=None
        )
        
        output = formatter.format(record)
        
        # Should be valid JSON
        data = json.loads(output)
        assert 'timestamp' in data
        assert 'level' in data
        assert data['level'] == 'INFO'
        assert 'message' in data
        assert data['message'] == 'Test message'
    
    def test_formatter_includes_extra_fields(self):
        """Formatter should include extra fields from record"""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='Test message',
            args=(),
            exc_info=None
        )
        
        # Add extra fields
        record.request_id = 'req_123'
        record.path = '/api/v1/test'
        record.method = 'GET'
        
        output = formatter.format(record)
        data = json.loads(output)
        
        assert data['request_id'] == 'req_123'
        assert data['path'] == '/api/v1/test'
        assert data['method'] == 'GET'
    
    def test_formatter_handles_exception(self):
        """Formatter should handle exception info"""
        formatter = StructuredFormatter()
        
        try:
            raise ValueError("Test error")
        except ValueError:
            record = logging.LogRecord(
                name='test',
                level=logging.ERROR,
                pathname='test.py',
                lineno=1,
                msg='Error occurred',
                args=(),
                exc_info=True
            )
            
            output = formatter.format(record)
            data = json.loads(output)
            
            assert 'error_type' in data
            assert data['error_type'] == 'ValueError'
            assert 'error_message' in data
            assert 'Test error' in data['error_message']
            assert 'stack_trace' in data


class TestGetLogger:
    """Test get_logger helper"""
    
    def test_get_logger_returns_logger(self):
        """get_logger should return a Logger instance"""
        logger = get_logger('test_logger')
        assert isinstance(logger, logging.Logger)
    
    def test_get_logger_has_handlers(self):
        """get_logger should configure handlers"""
        logger = get_logger('test_logger')
        assert len(logger.handlers) > 0
    
    def test_get_logger_sets_level(self):
        """get_logger should set correct log level"""
        logger = get_logger('test_logger', level='DEBUG')
        assert logger.level == logging.DEBUG
    
    def test_get_logger_creates_log_directory(self):
        """get_logger should create log directory if not exists"""
        # Clean up any existing logs directory
        if os.path.exists('logs'):
            import shutil
            shutil.rmtree('logs')
        
        logger = get_logger('test_logger')
        
        # logs directory should be created
        assert os.path.exists('logs')


class TestAuditLogger:
    """Test AuditLogger"""
    
    def test_audit_logger_exists(self):
        """AuditLogger should be importable"""
        from core.logging.audit import AuditLogger
        assert AuditLogger is not None
    
    def test_audit_logger_log_method_exists(self):
        """AuditLogger.log should be callable"""
        assert callable(AuditLogger.log)
    
    def test_audit_logger_helper_methods_exist(self):
        """AuditLogger should have helper methods"""
        assert callable(AuditLogger.log_login)
        assert callable(AuditLogger.log_logout)
        assert callable(AuditLogger.log_agent_create)
        assert callable(AuditLogger.log_agent_delete)
        assert callable(AuditLogger.log_mcp_connect)
        assert callable(AuditLogger.log_mcp_disconnect)
    
    def test_audit_logger_creates_separate_file(self):
        """AuditLogger should log to separate audit.log file"""
        AuditLogger.log(
            action='test.action',
            resource_type='Test',
            resource_id='test_123',
            request_id='req_test'
        )
        
        # audit.log should exist in logs directory
        assert os.path.exists('logs/audit.log')


class TestLoggingMiddleware:
    """Test LoggingMiddleware behavior"""
    
    def test_loggingmiddleware_excludes_paths(self):
        """LoggingMiddleware should exclude certain paths"""
        from gateway.middleware.logging import LoggingMiddleware
        
        middleware = LoggingMiddleware(None)
        assert '/health' in middleware.EXCLUDE_PATHS
        assert '/metrics' in middleware.EXCLUDE_PATHS
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/unit/test_logging.py -v`
Expected: PASS (12 tests)

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_logging.py
git commit -m "test(logging): add unit tests for StructuredFormatter and AuditLogger"
```

---

### Task 7: Run Full Test Suite

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
git commit -m "feat(observability): complete structured logging and audit enhancement

- StructuredFormatter for JSON log format
- get_logger with stdout + file dual output
- AuditLogger for sensitive operation tracking
- LoggingMiddleware with structured output
- Log rotation configuration (10MB, 5 backups)
- 12 unit tests for logging module

Phase 3 Observability Enhancement complete."
```

---

## Self-Review Checklist

| Spec Section | Covered by Task |
|--------------|-----------------|
| 2.1 Standard Log Structure | Task 1 |
| 2.2 Field Definitions | Task 1 |
| 2.3 Audit Log Structure | Task 3 |
| 3.1 Environment Variables | Task 4 |
| 3.2 Log File Rotation | Task 2 |
| 4 LoggingMiddleware | Task 5 |
| 5 AuditLogger | Task 3 |
| 6 Core Logging Module | Task 1, Task 2 |
| 9 Test Coverage | Task 6 |

**Placeholder Scan:** No TBD/TODO

**Type Consistency:** All extra fields consistent across formatter, middleware, audit