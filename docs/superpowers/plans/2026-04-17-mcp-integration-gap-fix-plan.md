# MCP Integration Gap Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix implementation gaps to make MCP integration fully match the design spec

**Architecture:** Add missing model fields, fix schema consistency, implement retry logic, and enhance error handling - all following existing patterns

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic v2, pytest, asyncio

---

## File Structure

### New Files

| Path | Responsibility |
|------|---------------|
| `tests/unit/test_mcp_model_fields.py` | Test MCPServer new fields |
| `tests/unit/test_mcp_tools_endpoint.py` | Test `/tools` API endpoint |
| `tests/unit/test_mcp_retry_logic.py` | Test retry mixin behavior |
| `tests/unit/test_mcp_error_suggestions.py` | Test MCPError suggestions |

### Modified Files

| Path | Modification |
|------|-------------|
| `models/application.py` | Add `last_connected_at`, `last_error`, `prompts` to MCPServer |
| `schemas/mcp.py` | Add `prompts` to MCPServerResponse |
| `gateway/api/v1/mcp_servers.py` | Add GET `/tools` endpoint |
| `agent/mcp/client.py` | Add MCPRetryMixin and integrate into clients |
| `core/exceptions.py` | Extend MCPError with suggestions |
| `config/mcp_servers.yml` | Update with usable examples |

---

## Task 1: MCPServer Model Fields

**Files:**
- Modify: `models/application.py:292-324`
- Create: `tests/unit/test_mcp_model_fields.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_mcp_model_fields.py
"""Tests for MCPServer model fields"""
import pytest
from models.application import MCPServer, ResourceStatus
from datetime import datetime


class TestMCPServerFields:
    """Tests for MCPServer model field presence"""
    
    def test_mcp_server_has_last_connected_at_field(self):
        """MCPServer should have last_connected_at field"""
        # Check field exists on model
        assert hasattr(MCPServer, 'last_connected_at')
        # Check field type is DateTime
        from sqlalchemy import DateTime
        column = MCPServer.__table__.columns.get('last_connected_at')
        assert column is not None
        assert isinstance(column.type, DateTime)
    
    def test_mcp_server_has_last_error_field(self):
        """MCPServer should have last_error field"""
        assert hasattr(MCPServer, 'last_error')
        from sqlalchemy import Text
        column = MCPServer.__table__.columns.get('last_error')
        assert column is not None
        assert isinstance(column.type, Text)
    
    def test_mcp_server_has_prompts_field(self):
        """MCPServer should have prompts field for MCP Prompts"""
        assert hasattr(MCPServer, 'prompts')
        from sqlalchemy import JSON
        column = MCPServer.__table__.columns.get('prompts')
        assert column is not None
        assert isinstance(column.type, JSON)
    
    def test_mcp_server_field_defaults(self):
        """MCPServer fields should have correct defaults"""
        # prompts should default to empty list
        prompts_column = MCPServer.__table__.columns.get('prompts')
        assert prompts_column.default.arg == list
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_mcp_model_fields.py -v`
Expected: FAIL with "AttributeError: type object 'MCPServer' has no attribute 'last_connected_at'"

- [ ] **Step 3: Add missing fields to MCPServer model**

```python
# models/application.py (modify MCPServer class, add after line 311)

class MCPServer(Base):
    """
    MCP Server model with multi-tenant support
    """
    __tablename__ = "mcp_servers"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    type = Column(String(100), nullable=True)  # stdio, sse, etc.
    status = Column(SQLEnum(ResourceStatus), default=ResourceStatus.ACTIVE, nullable=False)
    
    # MCP Server configuration
    endpoint = Column(String(500), nullable=True)  # URL or command
    config = Column(JSON, default=dict, nullable=False)  # args, env, etc.
    
    # Capabilities
    tools = Column(JSON, default=list, nullable=False)  # Available tools
    resources = Column(JSON, default=list, nullable=False)  # Available resources
    prompts = Column(JSON, default=list, nullable=False)  # MCP Prompts (NEW)
    
    # Connection tracking (NEW)
    last_connected_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('ix_mcp_servers_tenant_name', 'tenant_id', 'name', unique=True),
    )
    
    def __repr__(self):
        return f"<MCPServer(id={self.id}, name={self.name})>"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_mcp_model_fields.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add models/application.py tests/unit/test_mcp_model_fields.py
git commit -m "feat: add last_connected_at, last_error, prompts fields to MCPServer model"
```

---

## Task 2: Schema Consistency Fix

**Files:**
- Modify: `schemas/mcp.py:31-47`
- Create: `tests/unit/test_mcp_schema_consistency.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_mcp_schema_consistency.py
"""Tests for MCP schema consistency"""
import pytest
from schemas.mcp import MCPServerResponse
from datetime import datetime


class TestMCPServerResponseSchema:
    """Tests for MCPServerResponse schema fields"""
    
    def test_response_has_prompts_field(self):
        """MCPServerResponse should have prompts field"""
        # Create response with prompts
        response = MCPServerResponse(
            id="test-123",
            tenant_id="tenant-1",
            name="test-server",
            description="Test",
            type="sse",
            endpoint="http://test",
            config={},
            status="active",
            tools=[],
            resources=[],
            prompts=[{"name": "test_prompt"}],  # NEW field
            created_at=datetime.now()
        )
        assert response.prompts == [{"name": "test_prompt"}]
    
    def test_response_prompts_default_empty_list(self):
        """MCPServerResponse prompts should default to empty list"""
        response = MCPServerResponse(
            id="test-123",
            name="test-server",
            type="sse",
            endpoint="http://test",
            status="active",
            created_at=datetime.now()
        )
        assert response.prompts == []
    
    def test_response_matches_model_fields(self):
        """MCPServerResponse should match MCPServer model fields"""
        from models.application import MCPServer
        model_fields = [
            'id', 'tenant_id', 'name', 'description', 'type', 
            'endpoint', 'config', 'status', 'tools', 'resources',
            'prompts', 'last_connected_at', 'last_error',
            'created_at', 'updated_at'
        ]
        schema_fields = list(MCPServerResponse.model_fields.keys())
        for field in model_fields:
            assert field in schema_fields, f"Schema missing field: {field}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_mcp_schema_consistency.py -v`
Expected: FAIL with "ValidationError" or "prompts field missing"

- [ ] **Step 3: Add prompts field to MCPServerResponse**

```python
# schemas/mcp.py (modify MCPServerResponse)

class MCPServerResponse(BaseModel):
    """MCP server response."""
    id: str
    tenant_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    type: str
    endpoint: str
    config: Dict[str, Any] = {}
    status: str
    tools: List[Dict[str, Any]] = []
    resources: List[Dict[str, Any]] = []
    prompts: List[Dict[str, Any]] = []  # NEW
    last_connected_at: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_mcp_schema_consistency.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add schemas/mcp.py tests/unit/test_mcp_schema_consistency.py
git commit -m "feat: add prompts field to MCPServerResponse schema"
```

---

## Task 3: MCP Tools Endpoint

**Files:**
- Modify: `gateway/api/v1/mcp_servers.py`
- Create: `tests/unit/test_mcp_tools_endpoint.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_mcp_tools_endpoint.py
"""Tests for MCP Server tools endpoint"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from gateway.main import app


class TestMCPToolsEndpoint:
    """Tests for GET /api/v1/mcp-servers/{id}/tools endpoint"""
    
    def test_tools_endpoint_exists(self):
        """Tools endpoint should be registered"""
        from gateway.api.v1.mcp_servers import router
        # Check route exists
        routes = [r.path for r in router.routes]
        assert "/{server_id}/tools" in routes
    
    @pytest.mark.asyncio
    async def test_get_tools_returns_tool_list(self):
        """GET /tools should return tool list"""
        # Mock database and MCPServer
        mock_server = MagicMock()
        mock_server.id = "server-123"
        mock_server.status = MagicMock(value="active")
        mock_server.tools = [
            {"name": "read_file", "description": "Read a file", "inputSchema": {}},
            {"name": "write_file", "description": "Write a file", "inputSchema": {}}
        ]
        
        with patch('gateway.api.v1.mcp_servers.get_mcp_server_or_404', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_server
            
            # Test endpoint function directly
            from gateway.api.v1.mcp_servers import get_mcp_server_tools
            result = await get_mcp_server_tools("server-123", db=MagicMock())
            
            assert result["data"]["tools"] == mock_server.tools
            assert result["data"]["total"] == 2
    
    @pytest.mark.asyncio
    async def test_get_tools_inactive_server_raises_error(self):
        """GET /tools on inactive server should raise 400"""
        from models.application import ResourceStatus
        mock_server = MagicMock()
        mock_server.status = ResourceStatus.INACTIVE
        
        with patch('gateway.api.v1.mcp_servers.get_mcp_server_or_404', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_server
            
            from gateway.api.v1.mcp_servers import get_mcp_server_tools
            from fastapi import HTTPException
            
            with pytest.raises(HTTPException) as exc:
                await get_mcp_server_tools("server-123", db=MagicMock())
            
            assert exc.value.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_mcp_tools_endpoint.py -v`
Expected: FAIL with "route not found" or "function not defined"

- [ ] **Step 3: Add tools endpoint to MCP API**

```python
# gateway/api/v1/mcp_servers.py (add after existing endpoints)

@router.get("/{server_id}/tools")
async def get_mcp_server_tools(
    server_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List tools available from MCP Server
    
    Args:
        server_id: MCP Server ID
        db: Database session
        
    Returns:
        Tools list with total count
        
    Raises:
        HTTPException 400 if server is not active
        HTTPException 404 if server not found
    """
    server = await get_mcp_server_or_404(db, server_id)
    
    if server.status != ResourceStatus.ACTIVE:
        raise HTTPException(
            status_code=400,
            detail=f"MCP Server {server_id} is not active"
        )
    
    tools = server.tools or []
    
    return {
        "data": {
            "tools": tools,
            "total": len(tools)
        }
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_mcp_tools_endpoint.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add gateway/api/v1/mcp_servers.py tests/unit/test_mcp_tools_endpoint.py
git commit -m "feat: add GET /mcp-servers/{id}/tools endpoint"
```

---

## Task 4: MCP Retry Logic

**Files:**
- Modify: `agent/mcp/client.py`
- Create: `tests/unit/test_mcp_retry_logic.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_mcp_retry_logic.py
"""Tests for MCP retry logic"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock


class TestMCPRetryMixin:
    """Tests for MCPRetryMixin retry behavior"""
    
    def test_mcp_retry_mixin_exists(self):
        """MCPRetryMixin class should exist"""
        from agent.mcp.client import MCPRetryMixin
        assert MCPRetryMixin is not None
    
    def test_retry_mixin_default_config(self):
        """MCPRetryMixin should have default retry config"""
        from agent.mcp.client import MCPRetryMixin
        
        class TestClient(MCPRetryMixin):
            pass
        
        client = TestClient()
        assert client.max_retries == 3
        assert client.base_delay == 1.0
        assert client.max_delay == 30.0
    
    def test_is_retryable_connection_error(self):
        """ConnectionError should be retryable"""
        from agent.mcp.client import MCPRetryMixin
        
        class TestClient(MCPRetryMixin):
            pass
        
        client = TestClient()
        error = ConnectionError("Network error")
        assert client._is_retryable(error) is True
    
    def test_is_retryable_timeout_error(self):
        """TimeoutError should be retryable"""
        from agent.mcp.client import MCPRetryMixin
        
        class TestClient(MCPRetryMixin):
            pass
        
        client = TestClient()
        error = TimeoutError("Request timeout")
        assert client._is_retryable(error) is True
    
    def test_is_not_retryable_auth_error(self):
        """Authentication error should not be retryable"""
        from agent.mcp.client import MCPRetryMixin
        
        class TestClient(MCPRetryMixin):
            pass
        
        client = TestClient()
        error = Exception("Invalid credentials")
        assert client._is_retryable(error) is False
    
    @pytest.mark.asyncio
    async def test_retry_call_succeeds_after_retry(self):
        """_retry_call should succeed after retries"""
        from agent.mcp.client import MCPRetryMixin
        
        class TestClient(MCPRetryMixin):
            def __init__(self):
                self.call_count = 0
        
        client = TestClient()
        
        async def flaky_fn():
            client.call_count += 1
            if client.call_count < 2:
                raise ConnectionError("Failed")
            return "success"
        
        result = await client._retry_call(flaky_fn)
        assert result == "success"
        assert client.call_count == 2
    
    @pytest.mark.asyncio
    async def test_retry_call_raises_after_max_retries(self):
        """_retry_call should raise after max retries"""
        from agent.mcp.client import MCPRetryMixin
        
        class TestClient(MCPRetryMixin):
            max_retries = 2
        
        client = TestClient()
        
        async def always_fail():
            raise ConnectionError("Always fails")
        
        with pytest.raises(ConnectionError):
            await client._retry_call(always_fail)
    
    @pytest.mark.asyncio
    async def test_retry_call_no_retry_for_non_retryable(self):
        """_retry_call should not retry non-retryable errors"""
        from agent.mcp.client import MCPRetryMixin
        
        class TestClient(MCPRetryMixin):
            call_count = 0
        
        client = TestClient()
        
        async def fail_auth():
            client.call_count += 1
            raise Exception("Auth failed")
        
        with pytest.raises(Exception):
            await client._retry_call(fail_auth)
        
        # Should only call once, no retry
        assert client.call_count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_mcp_retry_logic.py -v`
Expected: FAIL with "cannot import name 'MCPRetryMixin'"

- [ ] **Step 3: Add MCPRetryMixin to client.py**

```python
# agent/mcp/client.py (add after imports, before MCPClient class)

class MCPRetryMixin:
    """MCP retry mechanism with exponential backoff
    
    Provides automatic retry for transient errors with configurable
    retry count and delays.
    """
    
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    
    def _is_retryable(self, error: Exception) -> bool:
        """Determine if error is retryable
        
        Args:
            error: Exception to check
            
        Returns:
            True if error can be retried
        """
        # Network/connection errors are retryable
        retryable_types = [
            "ConnectionError",
            "TimeoutError",
            "ConnectTimeout",
            "ReadTimeout"
        ]
        
        error_type = type(error).__name__
        if error_type in retryable_types:
            return True
        
        # HTTP 5xx errors are retryable
        if hasattr(error, 'response'):
            status = getattr(error.response, 'status_code', 0)
            if 500 <= status < 600:
                return True
        
        # Check for httpx errors
        try:
            import httpx
            if isinstance(error, (httpx.ConnectError, httpx.TimeoutException)):
                return True
        except ImportError:
            pass
        
        return False
    
    async def _retry_call(
        self,
        fn: callable,
        *args,
        **kwargs
    ) -> Any:
        """Execute function with retry on failure
        
        Args:
            fn: Async function to call
            args: Function arguments
            kwargs: Function keyword arguments
            
        Returns:
            Function result
            
        Raises:
            Last exception after max retries exhausted
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                return await fn(*args, **kwargs)
            except Exception as e:
                last_error = e
                
                # Don't retry non-retryable errors
                if not self._is_retryable(e):
                    raise
                
                # Don't sleep on last attempt
                if attempt < self.max_retries - 1:
                    delay = min(
                        self.base_delay * (2 ** attempt),
                        self.max_delay
                    )
                    await asyncio.sleep(delay)
        
        # All retries exhausted
        raise last_error
```

- [ ] **Step 4: Integrate Mixin into SSEMCPClient**

```python
# agent/mcp/client.py (modify SSEMCPClient class)

class SSEMCPClient(MCPRetryMixin, MCPClient):
    """
    MCP client using Server-Sent Events transport
    For remote MCP servers
    """
    
    # ... existing implementation ...
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Call tool with retry support"""
        return await self._retry_call(
            self._call_tool_impl,
            name,
            arguments
        )
    
    async def _call_tool_impl(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Actual tool call implementation"""
        response = await self.client.post(
            f"{self.endpoint}/tools/call",
            json={"name": name, "arguments": arguments}
        )
        return response.json().get("content", [])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/unit/test_mcp_retry_logic.py -v`
Expected: PASS (8 tests)

- [ ] **Step 6: Commit**

```bash
git add agent/mcp/client.py tests/unit/test_mcp_retry_logic.py
git commit -m "feat: add MCPRetryMixin with exponential backoff retry logic"
```

---

## Task 5: MCP Error Suggestions

**Files:**
- Modify: `core/exceptions.py`
- Create: `tests/unit/test_mcp_error_suggestions.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_mcp_error_suggestions.py
"""Tests for MCPError suggestions"""
import pytest
from core.exceptions import MCPError


class TestMCPErrorSuggestions:
    """Tests for MCPError suggestion field"""
    
    def test_mcp_error_has_suggestions_field(self):
        """MCPError should have suggestions field"""
        error = MCPError(
            "Connection failed",
            suggestions=["Check network", "Verify endpoint"]
        )
        assert error.suggestions == ["Check network", "Verify endpoint"]
    
    def test_mcp_error_default_empty_suggestions(self):
        """MCPError suggestions should default to empty list"""
        error = MCPError("Some error")
        assert error.suggestions == []
    
    def test_mcp_error_to_dict_includes_suggestions(self):
        """MCPError.to_dict should include suggestions"""
        error = MCPError(
            "Connection failed",
            suggestions=["Retry connection", "Check firewall"]
        )
        result = error.to_dict()
        assert "suggestions" in result
        assert result["suggestions"] == ["Retry connection", "Check firewall"]
    
    def test_mcp_error_to_dict_includes_server_name(self):
        """MCPError.to_dict should include server_name"""
        error = MCPError(
            "Tool failed",
            server_name="github-mcp"
        )
        result = error.to_dict()
        assert result["server_name"] == "github-mcp"
    
    def test_mcp_error_to_dict_includes_tool_name(self):
        """MCPError.to_dict should include tool_name"""
        error = MCPError(
            "Tool execution failed",
            tool_name="read_file"
        )
        result = error.to_dict()
        assert result["tool_name"] == "read_file"
    
    def test_mcp_error_to_dict_has_type_field(self):
        """MCPError.to_dict should have type='mcp_error'"""
        error = MCPError("Error")
        result = error.to_dict()
        assert result["type"] == "mcp_error"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_mcp_error_suggestions.py -v`
Expected: FAIL with "TypeError: MCPError.__init__() got unexpected keyword argument 'suggestions'"

- [ ] **Step 3: Enhance MCPError class**

```python
# core/exceptions.py (modify MCPError class)

class MCPError(Exception):
    """MCP error with recovery suggestions
    
    Attributes:
        message: Error message
        suggestions: List of recovery suggestions
        server_name: MCP Server name (optional)
        tool_name: MCP Tool name (optional)
    """
    
    def __init__(
        self,
        message: str,
        suggestions: List[str] = None,
        server_name: str = None,
        tool_name: str = None
    ):
        self.message = message
        self.suggestions = suggestions or []
        self.server_name = server_name
        self.tool_name = tool_name
        super().__init__(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response
        
        Returns:
            Dict with error details and suggestions
        """
        return {
            "error": self.message,
            "type": "mcp_error",
            "suggestions": self.suggestions,
            "server_name": self.server_name,
            "tool_name": self.tool_name
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_mcp_error_suggestions.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add core/exceptions.py tests/unit/test_mcp_error_suggestions.py
git commit -m "feat: extend MCPError with suggestions and metadata fields"
```

---

## Task 6: Config Example Update

**Files:**
- Modify: `config/mcp_servers.yml`
- Create: `tests/unit/test_mcp_config_loading.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_mcp_config_loading.py
"""Tests for MCP config file loading"""
import pytest
from pathlib import Path
import yaml


class TestMCPConfigFile:
    """Tests for mcp_servers.yml config file"""
    
    def test_config_file_exists(self):
        """Config file should exist"""
        config_path = Path("config/mcp_servers.yml")
        assert config_path.exists()
    
    def test_config_file_is_valid_yaml(self):
        """Config file should be valid YAML"""
        config_path = Path("config/mcp_servers.yml")
        with open(config_path) as f:
            data = yaml.safe_load(f)
        assert data is not None
    
    def test_config_has_mcp_servers_key(self):
        """Config should have mcp_servers key"""
        config_path = Path("config/mcp_servers.yml")
        with open(config_path) as f:
            data = yaml.safe_load(f)
        assert "mcp_servers" in data
    
    def test_config_servers_not_all_commented(self):
        """Config should have at least one uncommented example"""
        config_path = Path("config/mcp_servers.yml")
        with open(config_path) as f:
            data = yaml.safe_load(f)
        
        servers = data.get("mcp_servers", [])
        # At least one server should be defined (not empty)
        assert len(servers) >= 1
    
    def test_config_server_has_required_fields(self):
        """Each server should have required fields"""
        config_path = Path("config/mcp_servers.yml")
        with open(config_path) as f:
            data = yaml.safe_load(f)
        
        servers = data.get("mcp_servers", [])
        required = ["name", "type"]
        
        for server in servers:
            for field in required:
                assert field in server, f"Server missing field: {field}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_mcp_config_loading.py -v`
Expected: FAIL with "servers empty" or "no uncommented example"

- [ ] **Step 3: Update config file with examples**

```yaml
# config/mcp_servers.yml

# MCP Server Configuration
# 
# SmartLink supports 3 MCP transport types:
# - stdio: Local process communication
# - sse: Server-Sent Events (HTTP)
# - streamable_http: HTTP POST/GET
#
# Servers can be configured via:
# 1. This config file
# 2. Database (MCPServer table)
# 3. Environment variable MCP_SERVERS_URL

mcp_servers:
  # Example 1: Local stdio MCP server (filesystem)
  # Requires: pip install mcp-server-filesystem
  - name: "filesystem"
    type: "stdio"
    description: "Local filesystem access"
    command: "python"
    args: ["-m", "mcp_server_filesystem"]
    config:
      env:
        ALLOWED_DIRS: "/tmp"
    status: "active"
  
  # Example 2: SSE remote MCP server
  # Template for remote MCP servers using SSE transport
  - name: "remote-mcp-template"
    type: "sse"
    description: "Template for SSE MCP servers"
    endpoint: "http://localhost:8080/sse"
    config:
      headers: {}
      timeout: 30
    status: "inactive"
  
  # Example 3: StreamableHttp MCP server
  # Template for newer HTTP-based MCP servers
  - name: "http-mcp-template"
    type: "streamable_http"
    description: "Template for HTTP MCP servers"
    endpoint: "http://localhost:8080/mcp"
    config:
      headers: {}
    status: "inactive"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_mcp_config_loading.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add config/mcp_servers.yml tests/unit/test_mcp_config_loading.py
git commit -m "docs: update mcp_servers.yml with usable configuration examples"
```

---

## Verification Task: Full Test Suite

**Files:**
- Run all MCP-related tests

- [ ] **Step 1: Run all MCP unit tests**

Run: `pytest tests/unit/test_mcp_*.py -v`
Expected: All PASS

- [ ] **Step 2: Run all existing MCP tests**

Run: `pytest tests/unit/test_mcp_client.py tests/unit/test_toolkit_mcp.py -v`
Expected: All PASS

- [ ] **Step 3: Run full test suite**

Run: `pytest tests/unit/ -v`
Expected: 240+ tests PASS

- [ ] **Step 4: Type check**

Run: `mypy agent/mcp/client.py core/exceptions.py --ignore-missing-imports`
Expected: No errors

- [ ] **Step 5: Final commit (if needed)**

```bash
git status
# If clean, no action needed
# If uncommitted changes, review and commit
```

---

## Plan Status

- **Total Tasks:** 6 (plus verification)
- **Total Steps:** 30+
- **Estimated Time:** 2-3 hours with TDD

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-17-mcp-integration-gap-fix-plan.md`**

**Two execution options:**

1. **Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**