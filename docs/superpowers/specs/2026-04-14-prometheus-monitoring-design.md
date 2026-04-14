# Prometheus Monitoring Integration Design Specification

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:writing-plans to create implementation plan after user approves this spec.

**Created:** 2026-04-14
**Status:** Draft
**Scope:** Phase 3 - Prometheus Monitoring (Embedded Mode)

---

## 1. Overview

### 1.1 Purpose

Integrate Prometheus monitoring into SmartLink backend for observability and performance tracking. Embedded mode - metrics endpoint within existing FastAPI application.

### 1.2 Current State

- No metrics collection exists
- No `/metrics` endpoint
- No observability infrastructure

### 1.3 Target State

- Prometheus metrics endpoint at `/metrics`
- HTTP request metrics auto-collected via middleware
- Agent execution metrics tracked
- WebSocket connection metrics tracked
- Database query metrics tracked
- Grafana dashboard configurations (pre-built)

---

## 2. Architecture

### 2.1 Integration Mode

**Embedded Mode** - Metrics endpoint in main FastAPI app

```
+-----------------------------------------------------------------------------+
|                         FastAPI Application                                  |
+-----------------------------------------------------------------------------+
|                                                                             |
|  +-----------+  +-----------+  +-----------+  +-----------+  +-----------+ |
|  | /api/v1/* |  | /health   |  | /metrics  |  | /ws/chat  |  | /docs     | |
|  | Business  |  | Health    |  | Prometheus|  | WebSocket |  | OpenAPI   | |
|  | API       |  | Check     |  | Metrics   |  | Handler   |  | Docs      | |
|  +-----------+  +-----------+  +-----------+  +-----------+  +-----------+ |
|                                                                             |
|  +-----------------------------------------------------------------------+ |
|  |                      Middleware Stack                                 | |
|  |  RequestIDMiddleware → MetricsMiddleware → LoggingMiddleware → Auth  | |
|  +-----------------------------------------------------------------------+ |
|                                                                             |
+-----------------------------------------------------------------------------+
```

### 2.2 Metrics Flow

```
Request → MetricsMiddleware → Handler → Response
                 ↓
         Collect Metrics:
         - Request count
         - Latency
         - Error count
         - In-flight requests
                 ↓
         Store in Prometheus Registry
                 ↓
         /metrics endpoint → Prometheus Server → Grafana
```

---

## 3. Metrics Categories

### 3.1 HTTP Metrics

| Metric Name | Type | Description | Labels |
|-------------|------|-------------|--------|
| `http_requests_total` | Counter | Total HTTP requests | method, path, status |
| `http_request_duration_seconds` | Histogram | Request latency | method, path |
| `http_requests_in_progress` | Gauge | Active requests | method |
| `http_response_size_bytes` | Histogram | Response size | method, path |

### 3.2 Agent Metrics

| Metric Name | Type | Description | Labels |
|-------------|------|-------------|--------|
| `agent_executions_total` | Counter | Total agent executions | agent_type, status |
| `agent_execution_duration_seconds` | Histogram | Execution time | agent_type |
| `agent_llm_calls_total` | Counter | LLM API calls | model, provider |
| `agent_llm_tokens_total` | Counter | Token usage | model, type(input/output) |
| `agent_llm_errors_total` | Counter | LLM errors | model, error_type |

### 3.3 WebSocket Metrics

| Metric Name | Type | Description | Labels |
|-------------|------|-------------|--------|
| `websocket_connections_active` | Gauge | Active connections | - |
| `websocket_connections_total` | Counter | Total connections | - |
| `websocket_messages_total` | Counter | Total messages | direction(in/out) |
| `websocket_errors_total` | Counter | WebSocket errors | error_type |

### 3.4 Database Metrics

| Metric Name | Type | Description | Labels |
|-------------|------|-------------|--------|
| `db_queries_total` | Counter | Database queries | operation, table |
| `db_query_duration_seconds` | Histogram | Query time | operation |
| `db_connections_active` | Gauge | Active connections | - |
| `db_errors_total` | Counter | Database errors | error_type |

### 3.5 MCP Metrics

| Metric Name | Type | Description | Labels |
|-------------|------|-------------|--------|
| `mcp_tool_calls_total` | Counter | MCP tool calls | server_name, tool_name |
| `mcp_tool_duration_seconds` | Histogram | Tool execution time | tool_name |
| `mcp_server_connections` | Gauge | Connected servers | server_name |

---

## 4. Implementation Structure

### 4.1 File Structure

| File | Action | Purpose |
|------|--------|---------|
| `gateway/middleware/metrics.py` | Create | MetricsMiddleware + custom metrics |
| `gateway/main.py` | Modify | Register middleware, add /metrics endpoint |
| `pyproject.toml` | Modify | Add prometheus-client dependency |
| `config/grafana/dashboards/` | Create | Grafana dashboard JSON configs |

### 4.2 MetricsMiddleware

```python
# gateway/middleware/metrics.py

from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import time

# HTTP Metrics
HTTP_REQUESTS_TOTAL = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'path', 'status']
)

HTTP_REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'path'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
)

HTTP_REQUESTS_IN_PROGRESS = Gauge(
    'http_requests_in_progress',
    'HTTP requests currently being processed',
    ['method']
)

class MetricsMiddleware(BaseHTTPMiddleware):
    """Auto-collect HTTP metrics for all requests"""
    
    async def dispatch(self, request: Request, call_next):
        # Skip metrics endpoint itself
        if request.url.path == '/metrics':
            return await call_next(request)
        
        method = request.method
        path = request.url.path
        
        # Track in-progress
        HTTP_REQUESTS_IN_PROGRESS.labels(method=method).inc()
        
        start_time = time.time()
        
        try:
            response = await call_next(request)
            status = response.status_code
            
            # Record metrics
            HTTP_REQUESTS_TOTAL.labels(
                method=method, 
                path=path, 
                status=status
            ).inc()
            
            duration = time.time() - start_time
            HTTP_REQUEST_DURATION.labels(
                method=method,
                path=path
            ).observe(duration)
            
            return response
            
        except Exception as e:
            # Record error
            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                path=path,
                status=500
            ).inc()
            raise
            
        finally:
            HTTP_REQUESTS_IN_PROGRESS.labels(method=method).dec()
```

### 4.3 Custom Metrics Setup

```python
# agent/metrics.py

from prometheus_client import Counter, Histogram, Gauge

# Agent Metrics
AGENT_EXECUTIONS_TOTAL = Counter(
    'agent_executions_total',
    'Total agent executions',
    ['agent_type', 'status']
)

AGENT_EXECUTION_DURATION = Histogram(
    'agent_execution_duration_seconds',
    'Agent execution time',
    ['agent_type'],
    buckets=[0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
)

AGENT_LLM_CALLS_TOTAL = Counter(
    'agent_llm_calls_total',
    'LLM API calls',
    ['model', 'provider']
)

AGENT_LLM_TOKENS_TOTAL = Counter(
    'agent_llm_tokens_total',
    'Token usage',
    ['model', 'type']  # type: input/output
)

# WebSocket Metrics
WS_CONNECTIONS_ACTIVE = Gauge(
    'websocket_connections_active',
    'Active WebSocket connections'
)

WS_MESSAGES_TOTAL = Counter(
    'websocket_messages_total',
    'WebSocket messages',
    ['direction']
)

# MCP Metrics
MCP_TOOL_CALLS_TOTAL = Counter(
    'mcp_tool_calls_total',
    'MCP tool calls',
    ['server_name', 'tool_name']
)
```

### 4.4 Metrics Endpoint

```python
# gateway/main.py

from prometheus_client import make_asgi_app, CONTENT_TYPE_LATEST
from starlette.responses import Response

# Add metrics middleware
app.add_middleware(MetricsMiddleware)

# Metrics endpoint
metrics_app = make_asgi_app()

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(
        content=metrics_app.generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
```

---

## 5. Grafana Dashboards

### 5.1 API Performance Dashboard

```json
{
  "title": "SmartLink API Performance",
  "panels": [
    {
      "title": "Request Rate",
      "type": "graph",
      "targets": [
        {
          "expr": "rate(http_requests_total[5m])",
          "legendFormat": "{{method}} {{path}}"
        }
      ]
    },
    {
      "title": "Request Latency (P99)",
      "type": "graph",
      "targets": [
        {
          "expr": "histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))"
        }
      ]
    },
    {
      "title": "Error Rate",
      "type": "graph",
      "targets": [
        {
          "expr": "rate(http_requests_total{status=~\"5..\"}[5m])"
        }
      ]
    }
  ]
}
```

### 5.2 Agent Execution Dashboard

```json
{
  "title": "SmartLink Agent Monitoring",
  "panels": [
    {
      "title": "Agent Executions",
      "type": "graph",
      "targets": [
        {
          "expr": "rate(agent_executions_total[5m])",
          "legendFormat": "{{agent_type}}"
        }
      ]
    },
    {
      "title": "LLM Token Usage",
      "type": "graph",
      "targets": [
        {
          "expr": "rate(agent_llm_tokens_total[5m])",
          "legendFormat": "{{model}} {{type}}"
        }
      ]
    }
  ]
}
```

---

## 6. Configuration

### 6.1 Prometheus Server Config

```yaml
# prometheus.yml (external)
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'smartlink'
    static_configs:
      - targets: ['smartlink:8000']
    metrics_path: '/metrics'
```

### 6.2 Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `METRICS_ENABLED` | true | Enable/disable metrics |
| `METRICS_PATH` | /metrics | Metrics endpoint path |

---

## 7. Implementation Tasks

| Task | Files | Purpose |
|------|-------|---------|
| Task 1 | `pyproject.toml` | Add prometheus-client dependency |
| Task 2 | `gateway/middleware/metrics.py` | Create MetricsMiddleware |
| Task 3 | `agent/metrics.py` | Create custom metrics definitions |
| Task 4 | `gateway/main.py` | Register middleware, add /metrics endpoint |
| Task 5 | `config/grafana/dashboards/*.json` | Create Grafana dashboard configs |
| Task 6 | `tests/unit/test_metrics.py` | Unit tests for metrics middleware |

---

## 8. Test Coverage

| Test | Purpose |
|------|---------|
| test_metrics_endpoint_returns_prometheus_format | Verify /metrics endpoint |
| test_metricsmiddleware_collects_request_metrics | Verify HTTP metrics collection |
| test_agent_metrics_increment_on_execution | Verify Agent metrics |
| test_websocket_metrics_track_connections | Verify WebSocket metrics |

---

## 9. Self-Review Checklist

| Item | Status |
|------|--------|
| Placeholder scan | ✅ No TBD/TODO |
| Internal consistency | ✅ Metrics names consistent |
| Scope check | ✅ Prometheus integration only |
| Ambiguity check | ✅ Clear implementation tasks |

---

## 10. Notes

- Metrics endpoint accessible without authentication (standard Prometheus practice)
- Middleware added before AuthMiddleware to collect metrics for all requests
- Custom metrics use singleton pattern (Prometheus global registry)
- Grafana dashboards are JSON configs for manual import