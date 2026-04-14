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