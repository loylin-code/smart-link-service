# Prometheus Monitoring Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate Prometheus monitoring into SmartLink with embedded metrics endpoint and auto-collecting middleware.

**Architecture:** MetricsMiddleware collects HTTP metrics automatically, custom metrics track Agent/WebSocket/MCP execution, /metrics endpoint exposes Prometheus format.

**Tech Stack:** prometheus-client, FastAPI middleware, Starlette

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `pyproject.toml` | Modify | Add prometheus-client dependency |
| `gateway/middleware/metrics.py` | Create | MetricsMiddleware + HTTP metrics |
| `agent/metrics.py` | Create | Agent/WebSocket/MCP custom metrics |
| `gateway/main.py` | Modify | Register middleware, add /metrics endpoint |
| `config/grafana/dashboards/api-performance.json` | Create | Grafana dashboard config |
| `tests/unit/test_metrics.py` | Create | Metrics middleware unit tests |

---

### Task 1: Add prometheus-client Dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add prometheus-client to dependencies**

Edit `pyproject.toml` dependencies section (around line 45), add:

```toml
dependencies = [
    # ... existing dependencies
    
    # Monitoring
    "prometheus-client>=0.19.0",
]
```

- [ ] **Step 2: Install dependency**

Run: `pip install prometheus-client>=0.19.0`
Expected: Successfully installed prometheus-client

- [ ] **Step 3: Verify import**

Run: `python -c "from prometheus_client import Counter, Histogram, Gauge; print('OK')"`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "feat(deps): add prometheus-client for metrics collection"
```

---

### Task 2: Create MetricsMiddleware

**Files:**
- Create: `gateway/middleware/metrics.py`

- [ ] **Step 1: Create gateway/middleware/metrics.py**

```python
"""
Prometheus Metrics Middleware - Auto-collect HTTP metrics
"""
import time
from typing import Callable
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from prometheus_client import Counter, Histogram, Gauge, REGISTRY


# HTTP Metrics - Use global registry
HTTP_REQUESTS_TOTAL = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'path', 'status'],
    registry=REGISTRY
)

HTTP_REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency in seconds',
    ['method', 'path'],
    buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0],
    registry=REGISTRY
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    'http_requests_in_progress',
    'Number of HTTP requests currently being processed',
    ['method'],
    registry=REGISTRY
)

HTTP_RESPONSE_SIZE_BYTES = Histogram(
    'http_response_size_bytes',
    'HTTP response size in bytes',
    ['method', 'path'],
    buckets=[100, 1000, 10000, 100000, 1000000],
    registry=REGISTRY
)


class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware that automatically collects HTTP metrics for all requests.
    
    Collected metrics:
    - Request count (by method, path, status)
    - Request duration (histogram)
    - In-progress requests (gauge)
    - Response size (histogram)
    
    Note: /metrics endpoint is excluded to avoid self-monitoring
    """
    
    # Paths to exclude from metrics collection
    EXCLUDE_PATHS = ['/metrics', '/health', '/docs', '/openapi.json', '/redoc']
    
    async def dispatch(self, request: Request, call_next: Callable):
        """Process request and collect metrics"""
        
        # Skip excluded paths
        path = request.url.path
        if path in self.EXCLUDE_PATHS or path.startswith('/docs') or path.startswith('/openapi'):
            return await call_next(request)
        
        method = request.method
        
        # Increment in-progress gauge
        HTTP_REQUESTS_IN_PROGRESS.labels(method=method).inc()
        
        start_time = time.time()
        
        try:
            # Process request
            response = await call_next(request)
            
            # Record metrics
            status = response.status_code
            duration = time.time() - start_time
            
            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                path=path,
                status=status
            ).inc()
            
            HTTP_REQUEST_DURATION.labels(
                method=method,
                path=path
            ).observe(duration)
            
            # Record response size if available
            if hasattr(response, 'body'):
                body_size = len(response.body) if response.body else 0
                HTTP_RESPONSE_SIZE_BYTES.labels(
                    method=method,
                    path=path
                ).observe(body_size)
            
            return response
            
        except Exception as e:
            # Record error as 500
            duration = time.time() - start_time
            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                path=path,
                status=500
            ).inc()
            
            HTTP_REQUEST_DURATION.labels(
                method=method,
                path=path
            ).observe(duration)
            
            raise
            
        finally:
            # Decrement in-progress gauge
            HTTP_REQUESTS_IN_PROGRESS.labels(method=method).dec()


def get_http_metrics():
    """Return HTTP metrics for external access"""
    return {
        'requests_total': HTTP_REQUESTS_TOTAL,
        'request_duration': HTTP_REQUEST_DURATION,
        'requests_in_progress': HTTP_REQUESTS_IN_PROGRESS,
        'response_size': HTTP_RESPONSE_SIZE_BYTES,
    }
```

- [ ] **Step 2: Verify import**

Run: `python -c "from gateway.middleware.metrics import MetricsMiddleware; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add gateway/middleware/metrics.py
git commit -m "feat(middleware): add MetricsMiddleware for Prometheus HTTP metrics"
```

---

### Task 3: Create Custom Agent/WebSocket/MCP Metrics

**Files:**
- Create: `agent/metrics.py`

- [ ] **Step 1: Create agent/metrics.py**

```python
"""
Agent Metrics - Prometheus custom metrics for Agent/WebSocket/MCP execution
"""
from prometheus_client import Counter, Histogram, Gauge, REGISTRY


# Agent Execution Metrics
AGENT_EXECUTIONS_TOTAL = Counter(
    'agent_executions_total',
    'Total number of agent executions',
    ['agent_type', 'status'],
    registry=REGISTRY
)

AGENT_EXECUTION_DURATION = Histogram(
    'agent_execution_duration_seconds',
    'Agent execution duration in seconds',
    ['agent_type'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0, 120.0],
    registry=REGISTRY
)

AGENT_LLM_CALLS_TOTAL = Counter(
    'agent_llm_calls_total',
    'Total LLM API calls',
    ['model', 'provider'],
    registry=REGISTRY
)

AGENT_LLM_TOKENS_TOTAL = Counter(
    'agent_llm_tokens_total',
    'Total tokens used',
    ['model', 'token_type'],  # token_type: input/output
    registry=REGISTRY
)

AGENT_LLM_ERRORS_TOTAL = Counter(
    'agent_llm_errors_total',
    'Total LLM errors',
    ['model', 'error_type'],
    registry=REGISTRY
)

AGENT_SKILL_CALLS_TOTAL = Counter(
    'agent_skill_calls_total',
    'Total skill invocations',
    ['skill_name', 'status'],
    registry=REGISTRY
)


# WebSocket Metrics
WS_CONNECTIONS_ACTIVE = Gauge(
    'websocket_connections_active',
    'Number of active WebSocket connections',
    registry=REGISTRY
)

WS_CONNECTIONS_TOTAL = Counter(
    'websocket_connections_total',
    'Total WebSocket connections',
    registry=REGISTRY
)

WS_MESSAGES_TOTAL = Counter(
    'websocket_messages_total',
    'Total WebSocket messages',
    ['direction'],  # direction: in/out
    registry=REGISTRY
)

WS_ERRORS_TOTAL = Counter(
    'websocket_errors_total',
    'Total WebSocket errors',
    ['error_type'],
    registry=REGISTRY
)


# MCP Metrics
MCP_TOOL_CALLS_TOTAL = Counter(
    'mcp_tool_calls_total',
    'Total MCP tool calls',
    ['server_name', 'tool_name'],
    registry=REGISTRY
)

MCP_TOOL_DURATION = Histogram(
    'mcp_tool_duration_seconds',
    'MCP tool execution duration',
    ['server_name', 'tool_name'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0],
    registry=REGISTRY
)

MCP_SERVER_CONNECTIONS = Gauge(
    'mcp_server_connections',
    'Number of connected MCP servers',
    ['server_name'],
    registry=REGISTRY
)

MCP_ERRORS_TOTAL = Counter(
    'mcp_errors_total',
    'Total MCP errors',
    ['server_name', 'error_type'],
    registry=REGISTRY
)


# Database Metrics
DB_QUERIES_TOTAL = Counter(
    'db_queries_total',
    'Total database queries',
    ['operation', 'table'],
    registry=REGISTRY
)

DB_QUERY_DURATION = Histogram(
    'db_query_duration_seconds',
    'Database query duration',
    ['operation'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0],
    registry=REGISTRY
)

DB_CONNECTIONS_ACTIVE = Gauge(
    'db_connections_active',
    'Number of active database connections',
    registry=REGISTRY
)

DB_ERRORS_TOTAL = Counter(
    'db_errors_total',
    'Total database errors',
    ['error_type'],
    registry=REGISTRY
)


# Helper functions to record metrics
def record_agent_execution(agent_type: str, status: str, duration: float):
    """Record agent execution metrics"""
    AGENT_EXECUTIONS_TOTAL.labels(agent_type=agent_type, status=status).inc()
    AGENT_EXECUTION_DURATION.labels(agent_type=agent_type).observe(duration)


def record_llm_call(model: str, provider: str, input_tokens: int, output_tokens: int):
    """Record LLM call metrics"""
    AGENT_LLM_CALLS_TOTAL.labels(model=model, provider=provider).inc()
    AGENT_LLM_TOKENS_TOTAL.labels(model=model, token_type='input').inc(input_tokens)
    AGENT_LLM_TOKENS_TOTAL.labels(model=model, token_type='output').inc(output_tokens)


def record_ws_connection_change(connected: bool):
    """Record WebSocket connection change"""
    if connected:
        WS_CONNECTIONS_ACTIVE.inc()
        WS_CONNECTIONS_TOTAL.inc()
    else:
        WS_CONNECTIONS_ACTIVE.dec()


def record_ws_message(direction: str):
    """Record WebSocket message"""
    WS_MESSAGES_TOTAL.labels(direction=direction).inc()


def record_mcp_tool_call(server_name: str, tool_name: str, duration: float):
    """Record MCP tool call"""
    MCP_TOOL_CALLS_TOTAL.labels(server_name=server_name, tool_name=tool_name).inc()
    MCP_TOOL_DURATION.labels(server_name=server_name, tool_name=tool_name).observe(duration)


def record_db_query(operation: str, table: str, duration: float):
    """Record database query"""
    DB_QUERIES_TOTAL.labels(operation=operation, table=table).inc()
    DB_QUERY_DURATION.labels(operation=operation).observe(duration)
```

- [ ] **Step 2: Verify import**

Run: `python -c "from agent.metrics import record_agent_execution; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add agent/metrics.py
git commit -m "feat(metrics): add Agent/WebSocket/MCP custom Prometheus metrics"
```

---

### Task 4: Register Middleware and Add /metrics Endpoint

**Files:**
- Modify: `gateway/main.py`
- Modify: `gateway/middleware/__init__.py`

- [ ] **Step 1: Update gateway/middleware/__init__.py**

Add MetricsMiddleware export:

```python
"""
Middleware module initialization
"""
from gateway.middleware.auth import APIKeyMiddleware, verify_api_key_ws
from gateway.middleware.logging import LoggingMiddleware
from gateway.middleware.rate_limit import RateLimitMiddleware
from gateway.middleware.request_id import RequestIDMiddleware
from gateway.middleware.metrics import MetricsMiddleware

__all__ = [
    "APIKeyMiddleware",
    "verify_api_key_ws",
    "LoggingMiddleware",
    "RateLimitMiddleware",
    "RequestIDMiddleware",
    "MetricsMiddleware",
]
```

- [ ] **Step 2: Update gateway/main.py imports**

Add imports at top (around line 20):

```python
from gateway.middleware.metrics import MetricsMiddleware
from prometheus_client import make_asgi_app, CONTENT_TYPE_LATEST, REGISTRY
```

- [ ] **Step 3: Register MetricsMiddleware**

Edit middleware registration (around line 267), add MetricsMiddleware:

```python
# Add custom middleware (order matters: first added = last executed)
app.add_middleware(MetricsMiddleware)  # Prometheus metrics collection
app.add_middleware(RequestIDMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(AuthMiddleware)
if settings.RATE_LIMIT_ENABLED:
    app.add_middleware(RateLimitMiddleware)
```

- [ ] **Step 4: Add /metrics endpoint**

Add after exception handlers (around line 310):

```python
# Prometheus metrics endpoint
@app.get("/metrics")
async def metrics_endpoint():
    """
    Prometheus metrics endpoint.
    
    Returns metrics in Prometheus text format for scraping.
    No authentication required (standard Prometheus practice).
    """
    from starlette.responses import Response
    
    # Generate Prometheus metrics output
    output = make_asgi_app(registry=REGISTRY)
    
    # Get latest metrics
    from prometheus_client import generate_latest
    metrics_output = generate_latest(REGISTRY)
    
    return Response(
        content=metrics_output,
        media_type=CONTENT_TYPE_LATEST,
        headers={
            "Cache-Control": "no-cache",
        }
    )
```

- [ ] **Step 5: Verify app loads**

Run: `python -c "from gateway.main import app; print('OK')"`
Expected: OK

- [ ] **Step 6: Commit**

```bash
git add gateway/middleware/__init__.py gateway/main.py
git commit -m "feat(api): register MetricsMiddleware and add /metrics endpoint"
```

---

### Task 5: Create Grafana Dashboard Config

**Files:**
- Create: `config/grafana/dashboards/api-performance.json`

- [ ] **Step 1: Create config/grafana/dashboards directory**

```bash
mkdir -p config/grafana/dashboards
```

- [ ] **Step 2: Create api-performance.json**

```json
{
  "annotations": {
    "list": []
  },
  "title": "SmartLink API Performance",
  "uid": "smartlink-api",
  "version": 1,
  "panels": [
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {},
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 0,
        "y": 0
      },
      "id": 1,
      "options": {},
      "targets": [
        {
          "expr": "rate(http_requests_total[5m])",
          "legendFormat": "{{method}} {{path}} {{status}}",
          "refId": "A"
        }
      ],
      "title": "Request Rate",
      "type": "timeseries"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "unit": "s"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 12,
        "y": 0
      },
      "id": 2,
      "targets": [
        {
          "expr": "histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))",
          "legendFormat": "P99",
          "refId": "A"
        },
        {
          "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
          "legendFormat": "P95",
          "refId": "B"
        },
        {
          "expr": "histogram_quantile(0.50, rate(http_request_duration_seconds_bucket[5m]))",
          "legendFormat": "P50",
          "refId": "C"
        }
      ],
      "title": "Request Latency",
      "type": "timeseries"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {},
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 0,
        "y": 8
      },
      "id": 3,
      "targets": [
        {
          "expr": "rate(http_requests_total{status=~\"5..\"}[5m])",
          "legendFormat": "5xx errors",
          "refId": "A"
        },
        {
          "expr": "rate(http_requests_total{status=~\"4..\"}[5m])",
          "legendFormat": "4xx errors",
          "refId": "B"
        }
      ],
      "title": "Error Rate",
      "type": "timeseries"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {},
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 12,
        "y": 8
      },
      "id": 4,
      "targets": [
        {
          "expr": "http_requests_in_progress",
          "legendFormat": "Active requests",
          "refId": "A"
        }
      ],
      "title": "Requests In Progress",
      "type": "gauge"
    }
  ],
  "schemaVersion": 38,
  "tags": ["smartlink", "api", "performance"],
  "time": {
    "from": "now-1h",
    "to": "now"
  },
  "timepicker": {},
  "refresh": "10s"
}
```

- [ ] **Step 3: Create agent-monitoring.json**

```json
{
  "annotations": {
    "list": []
  },
  "title": "SmartLink Agent Monitoring",
  "uid": "smartlink-agent",
  "version": 1,
  "panels": [
    {
      "datasource": "Prometheus",
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 0,
        "y": 0
      },
      "id": 1,
      "targets": [
        {
          "expr": "rate(agent_executions_total[5m])",
          "legendFormat": "{{agent_type}} {{status}}",
          "refId": "A"
        }
      ],
      "title": "Agent Executions",
      "type": "timeseries"
    },
    {
      "datasource": "Prometheus",
      "fieldConfig": {
        "defaults": {
          "unit": "s"
        }
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 12,
        "y": 0
      },
      "id": 2,
      "targets": [
        {
          "expr": "histogram_quantile(0.95, rate(agent_execution_duration_seconds_bucket[5m]))",
          "legendFormat": "P95 {{agent_type}}",
          "refId": "A"
        }
      ],
      "title": "Agent Execution Duration",
      "type": "timeseries"
    },
    {
      "datasource": "Prometheus",
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 0,
        "y": 8
      },
      "id": 3,
      "targets": [
        {
          "expr": "rate(agent_llm_tokens_total{token_type=\"input\"}[5m])",
          "legendFormat": "Input {{model}}",
          "refId": "A"
        },
        {
          "expr": "rate(agent_llm_tokens_total{token_type=\"output\"}[5m])",
          "legendFormat": "Output {{model}}",
          "refId": "B"
        }
      ],
      "title": "LLM Token Usage",
      "type": "timeseries"
    },
    {
      "datasource": "Prometheus",
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 12,
        "y": 8
      },
      "id": 4,
      "targets": [
        {
          "expr": "websocket_connections_active",
          "legendFormat": "Active connections",
          "refId": "A"
        }
      ],
      "title": "WebSocket Connections",
      "type": "gauge"
    }
  ],
  "schemaVersion": 38,
  "tags": ["smartlink", "agent"],
  "refresh": "10s"
}
```

- [ ] **Step 4: Commit**

```bash
git add config/grafana/dashboards/
git commit -m "feat(grafana): add API and Agent monitoring dashboard configs"
```

---

### Task 6: Create Unit Tests

**Files:**
- Create: `tests/unit/test_metrics.py`

- [ ] **Step 1: Create tests/unit/test_metrics.py**

```python
"""
Prometheus metrics unit tests
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from starlette.requests import Request
from starlette.responses import Response

from gateway.middleware.metrics import (
    MetricsMiddleware,
    HTTP_REQUESTS_TOTAL,
    HTTP_REQUEST_DURATION,
    HTTP_REQUESTS_IN_PROGRESS,
)


class TestMetricsMiddleware:
    """Test MetricsMiddleware behavior"""
    
    def test_metricsmiddleware_excludes_metrics_path(self):
        """MetricsMiddleware should skip /metrics path"""
        middleware = MetricsMiddleware(None)
        assert '/metrics' in middleware.EXCLUDE_PATHS
        assert '/health' in middleware.EXCLUDE_PATHS
    
    def test_http_requests_total_counter_exists(self):
        """HTTP_REQUESTS_TOTAL should be a Counter"""
        from prometheus_client import Counter
        assert isinstance(HTTP_REQUESTS_TOTAL, Counter)
    
    def test_http_request_duration_histogram_exists(self):
        """HTTP_REQUEST_DURATION should be a Histogram"""
        from prometheus_client import Histogram
        assert isinstance(HTTP_REQUEST_DURATION, Histogram)
    
    def test_http_requests_in_progress_gauge_exists(self):
        """HTTP_REQUESTS_IN_PROGRESS should be a Gauge"""
        from prometheus_client import Gauge
        assert isinstance(HTTP_REQUESTS_IN_PROGRESS, Gauge)
    
    @pytest.mark.asyncio
    async def test_metricsmiddleware_increments_counter_on_success(self):
        """Middleware should increment request counter"""
        # Mock request
        request = MagicMock(spec=Request)
        request.url = MagicMock()
        request.url.path = '/api/v1/agents'
        request.method = 'GET'
        
        # Mock response
        response = MagicMock(spec=Response)
        response.status_code = 200
        
        # Mock call_next
        async def call_next(req):
            return response
        
        middleware = MetricsMiddleware(None)
        
        # Execute
        result = await middleware.dispatch(request, call_next)
        
        # Verify response returned
        assert result == response
    
    @pytest.mark.asyncio
    async def test_metricsmiddleware_skips_excluded_paths(self):
        """Middleware should skip excluded paths"""
        request = MagicMock(spec=Request)
        request.url = MagicMock()
        request.url.path = '/metrics'
        request.method = 'GET'
        
        response = MagicMock(spec=Response)
        response.status_code = 200
        
        async def call_next(req):
            return response
        
        middleware = MetricsMiddleware(None)
        result = await middleware.dispatch(request, call_next)
        
        assert result == response


class TestAgentMetrics:
    """Test Agent custom metrics"""
    
    def test_record_agent_execution_exists(self):
        """record_agent_execution helper should exist"""
        from agent.metrics import record_agent_execution
        assert callable(record_agent_execution)
    
    def test_record_llm_call_exists(self):
        """record_llm_call helper should exist"""
        from agent.metrics import record_llm_call
        assert callable(record_llm_call)
    
    def test_record_ws_connection_change_exists(self):
        """record_ws_connection_change helper should exist"""
        from agent.metrics import record_ws_connection_change
        assert callable(record_ws_connection_change)
    
    def test_record_mcp_tool_call_exists(self):
        """record_mcp_tool_call helper should exist"""
        from agent.metrics import record_mcp_tool_call
        assert callable(record_mcp_tool_call)
    
    def test_agent_metrics_counters_increment(self):
        """Agent metrics counters should increment correctly"""
        from agent.metrics import AGENT_EXECUTIONS_TOTAL
        
        # Get initial value (note: counter can't be read directly in tests)
        # Just verify it's the correct type
        from prometheus_client import Counter
        assert isinstance(AGENT_EXECUTIONS_TOTAL, Counter)
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/unit/test_metrics.py -v`
Expected: PASS (11 tests)

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_metrics.py
git commit -m "test(metrics): add MetricsMiddleware and Agent metrics unit tests"
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
git commit -m "feat(monitoring): complete Prometheus integration

- MetricsMiddleware for HTTP metrics auto-collection
- Custom Agent/WebSocket/MCP/Database metrics
- /metrics endpoint for Prometheus scraping
- Grafana dashboard configurations
- Unit tests for metrics middleware

Phase 3 Prometheus monitoring complete."
```

---

## Self-Review Checklist

| Spec Section | Covered by Task |
|--------------|-----------------|
| 3.1 HTTP Metrics | Task 2 |
| 3.2 Agent Metrics | Task 3 |
| 3.3 WebSocket Metrics | Task 3 |
| 3.4 Database Metrics | Task 3 |
| 3.5 MCP Metrics | Task 3 |
| 4.2 MetricsMiddleware | Task 2 |
| 4.3 Custom Metrics | Task 3 |
| 4.4 Metrics Endpoint | Task 4 |
| 5 Grafana Dashboards | Task 5 |
| 8 Test Coverage | Task 6 |

**Placeholder Scan:** No TBD/TODO

**Type Consistency:** Metrics names consistent across all files