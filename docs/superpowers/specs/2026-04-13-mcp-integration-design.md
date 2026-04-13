# MCP Integration Design

**Date:** 2026-04-13
**Status:** Approved for Implementation
**Scope:** Full MCP (Model Context Protocol) integration with SSE + StreamableHttp transports

---

## 1. Overview

Integrate MCP servers with SmartLink AgentScope runtime:
- Remote MCP servers via SSE and StreamableHttp transports
- Hybrid discovery: Database-managed + Config file + Environment
- AgentToolkit integration for ReActAgent tool calling
- MCP Server CRUD API for management

### Design Decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Transport types | SSE + StreamableHttp | Remote MCP servers (cloud services) |
| Discovery method | Hybrid (DB + Config + Env) | Flexibility for different deployment scenarios |
| Integration mode | AgentScope Toolkit | Seamless ReActAgent tool calling |
| Success criteria | Functional + tested | 6 tests passing, API working |

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         MCP Integration Architecture                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌───────────────┐     ┌───────────────┐     ┌──────────────────────┐ │
│  │ Database      │     │ Config YAML   │     │ Environment          │ │
│  │ MCPServer     │     │ mcp_servers.yml│     │ MCP_SERVERS_URL     │ │
│  └───────────────┘     └───────────────┘     └──────────────────────┘ │
│          │                     │                        │              │
│          └─────────────────────┼────────────────────────┘              │
│                                │                                        │
│                                ▼                                        │
│                   ┌────────────────────────┐                           │
│                   │    MCPManager           │                           │
│                   │  (Startup Loading)      │                           │
│                   └────────────────────────┘                           │
│                                │                                        │
│                   ┌────────────┴────────────┐                           │
│                   │                         │                           │
│                   ▼                         ▼                           │
│          ┌───────────────┐        ┌──────────────────┐                 │
│          │ SSEMCPClient  │        │ StreamableHttp   │                 │
│          │ (SSE events)  │        │ MCPClient        │                 │
│          └───────────────┘        └──────────────────┘                 │
│                   │                         │                           │
│                   └────────────┬────────────┘                           │
│                                │                                        │
│                                ▼                                        │
│                   ┌────────────────────────┐                           │
│                   │    AgentToolkit         │                           │
│                   │ register_mcp_server()   │                           │
│                   │ get_tool_schemas()      │                           │
│                   └────────────────────────┘                           │
│                                │                                        │
│                                ▼                                        │
│                   ┌────────────────────────┐                           │
│                   │    ReActAgent           │                           │
│                   │ (tool calling)          │                           │
│                   └────────────────────────┘                           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Components

### 3.1 MCP Client Types

| Client | Transport | Use Case | Methods |
|--------|-----------|----------|---------|
| `SSEMCPClient` | HTTP SSE | Remote MCP servers with event stream | `connect()`, `call_tool()`, `list_tools()` |
| `StreamableHttpMCPClient` | HTTP POST/GET | Modern MCP servers without SSE | `connect()`, `call_tool()`, `list_tools()` |

### 3.2 SSEMCPClient Implementation

```python
# agent/mcp/client.py (enhance existing)
class SSEMCPClient(MCPClient):
    """MCP client using Server-Sent Events transport"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.endpoint = config.get("endpoint", "")
        self.headers = config.get("headers", {})
        self.timeout = config.get("timeout", 30)
    
    async def connect(self):
        """Connect to remote MCP server via SSE"""
        import httpx
        
        self.client = httpx.AsyncClient(
            headers=self.headers,
            timeout=self.timeout
        )
        
        # Initialize MCP session
        response = await self.client.post(
            f"{self.endpoint}/initialize",
            json={
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": True, "resources": True},
                "clientInfo": {"name": "smartlink", "version": "1.0.0"}
            }
        )
        response.raise_for_status()
        self.connected = True
        
        # Load tools and resources
        self.tools = await self.list_tools()
        self.resources = await self.list_resources()
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool via HTTP POST"""
        response = await self.client.post(
            f"{self.endpoint}/tools/call",
            json={"name": name, "arguments": arguments}
        )
        return response.json().get("content", [])
```

### 3.3 StreamableHttpMCPClient Implementation

```python
# agent/mcp/client.py (add new class)
class StreamableHttpMCPClient(MCPClient):
    """MCP client using HTTP POST/GET (newer MCP transport)"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.endpoint = config.get("endpoint", "")
        self.headers = config.get("headers", {})
        self.session_id = None
    
    async def connect(self):
        """Connect and establish session"""
        import httpx
        
        self.client = httpx.AsyncClient(headers=self.headers)
        
        # POST to initialize endpoint
        response = await self.client.post(
            f"{self.endpoint}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {}
                }
            }
        )
        data = response.json()
        self.session_id = data.get("result", {}).get("sessionId")
        self.connected = True
        
        self.tools = await self.list_tools()
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Call tool via POST with session"""
        response = await self.client.post(
            f"{self.endpoint}/mcp",
            headers={"mcp-session-id": self.session_id} if self.session_id else {},
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": name, "arguments": arguments}
            }
        )
        return response.json().get("result", {})
```

### 3.4 AgentToolkit MCP Integration

```python
# agent/agentscope/toolkit.py (enhance)
class AgentToolkit:
    """Agent toolkit for Skills and MCP tools"""
    
    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}
        self._mcp_clients: Dict[str, MCPClient] = {}
    
    async def register_mcp_server(self, mcp_client: MCPClient) -> None:
        """Register MCP tools as toolkit functions
        
        Args:
            mcp_client: Connected MCPClient instance
        """
        self._mcp_clients[mcp_client.config.get("name", "unknown")] = mcp_client
        
        for tool in mcp_client.tools:
            self._tools[tool.name] = {
                "type": "mcp",
                "client": mcp_client,
                "name": tool.name,
                "description": tool.description,
                "schema": tool.input_schema
            }
    
    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """Return AgentScope-compatible tool schemas
        
        Format matches AgentScope ReActAgent tool format:
        {
            "type": "function",
            "function": {
                "name": str,
                "description": str,
                "parameters": dict
            }
        }
        """
        schemas = []
        for name, tool in self._tools.items():
            schemas.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool.get("description", ""),
                    "parameters": tool.get("schema", {})
                }
            })
        return schemas
    
    async def execute_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Execute tool by name
        
        Args:
            name: Tool name
            arguments: Tool arguments
            
        Returns:
            Tool execution result
            
        Raises:
            MCPError: If tool not found or execution fails
        """
        tool = self._tools.get(name)
        if not tool:
            raise MCPError(f"Tool not found: {name}")
        
        if tool["type"] == "mcp":
            return await tool["client"].call_tool(name, arguments)
        
        # Skill execution (existing logic)
        skill = tool.get("skill")
        if skill:
            return await skill.execute(arguments)
        
        raise MCPError(f"Unknown tool type: {tool.get('type')}")
```

---

## 4. Startup Loading

### 4.1 Hybrid Discovery Flow

```
Startup Sequence:
1. Load from Database → MCPServer table (tenant-scoped)
2. Load from Config → mcp_servers.yml (global defaults)
3. Environment Override → MCP_SERVERS_URL (comma-separated URLs)
4. Connect all → MCPManager.register_client()
5. Register to Toolkit → AgentToolkit.register_mcp_server()
```

### 4.2 Startup Implementation

```python
# gateway/main.py lifespan
from agent.mcp.client import mcp_manager
from agent.agentscope.toolkit import AgentToolkit
from models.application import MCPServer
import yaml
import os

async def load_mcp_servers(toolkit: AgentToolkit):
    """Load MCP servers from database, config, and environment"""
    
    # 1. Database MCP servers
    async with async_session_maker() as db:
        result = await db.execute(
            select(MCPServer).where(MCPServer.status == ResourceStatus.ACTIVE)
        )
        servers = result.scalars().all()
        
        for server in servers:
            try:
                config = {
                    "name": server.name,
                    "type": server.type,
                    "endpoint": server.endpoint,
                    "headers": server.config.get("headers", {}),
                    "timeout": server.config.get("timeout", 30)
                }
                client = await mcp_manager.register_client(server.name, config)
                await toolkit.register_mcp_server(client)
                print(f"[OK] MCP server '{server.name}' connected ({len(client.tools)} tools)")
            except Exception as e:
                print(f"[WARN] MCP server '{server.name}' failed: {e}")
                server.status = ResourceStatus.INACTIVE
                server.last_error = str(e)
                await db.commit()
    
    # 2. Config file MCP servers
    config_path = "config/mcp_servers.yml"
    if os.path.exists(config_path):
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        for server_config in config.get("mcp_servers", []):
            try:
                client = await mcp_manager.register_client(
                    server_config["name"],
                    server_config
                )
                await toolkit.register_mcp_server(client)
                print(f"[OK] MCP server '{server_config['name']}' loaded from config")
            except Exception as e:
                print(f"[WARN] Config MCP '{server_config['name']}' failed: {e}")
    
    # 3. Environment URLs
    if settings.MCP_SERVERS_URL:
        urls = settings.MCP_SERVERS_URL.split(",")
        for i, url in enumerate(urls):
            try:
                name = f"env-mcp-{i}"
                client = await mcp_manager.register_client(name, {
                    "type": "sse",
                    "endpoint": url.strip()
                })
                await toolkit.register_mcp_server(client)
                print(f"[OK] MCP server '{name}' loaded from env")
            except Exception as e:
                print(f"[WARN] Env MCP '{url}' failed: {e}")
```

### 4.3 Config File Format

```yaml
# config/mcp_servers.yml
mcp_servers:
  # SSE transport MCP server
  - name: "weather-api"
    type: "sse"
    endpoint: "https://api.weather.com/mcp"
    headers:
      Authorization: "Bearer ${WEATHER_API_KEY}"
      Content-Type: "application/json"
    timeout: 30
  
  # HTTP transport MCP server
  - name: "calendar-service"
    type: "http"
    endpoint: "https://calendar.example.com/mcp"
    headers:
      X-API-Key: "${CALENDAR_API_KEY}"
```

---

## 5. MCP Server API

### 5.1 Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/mcp-servers` | GET | List all MCP servers |
| `/api/v1/mcp-servers` | POST | Create new MCP server |
| `/api/v1/mcp-servers/{id}` | GET | Get MCP server details |
| `/api/v1/mcp-servers/{id}` | PUT | Update MCP server config |
| `/api/v1/mcp-servers/{id}` | DELETE | Delete MCP server |
| `/api/v1/mcp-servers/{id}/tools` | GET | List available tools |
| `/api/v1/mcp-servers/{id}/connect` | POST | Test connection |
| `/api/v1/mcp-servers/{id}/disconnect` | POST | Disconnect server |

### 5.2 API Implementation

```python
# gateway/api/v1/mcp_servers.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.session import get_db
from models.application import MCPServer, ResourceStatus
from agent.mcp.client import mcp_manager
from schemas.mcp import MCPServerCreate, MCPServerUpdate, MCPServerResponse

router = APIRouter()

@router.get("/", response_model=List[MCPServerResponse])
async def list_mcp_servers(
    db: AsyncSession = Depends(get_db)
):
    """List all MCP servers"""
    result = await db.execute(select(MCPServer))
    return result.scalars().all()

@router.post("/", response_model=MCPServerResponse)
async def create_mcp_server(
    data: MCPServerCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create and connect new MCP server"""
    server = MCPServer(
        name=data.name,
        type=data.type,
        endpoint=data.endpoint,
        config=data.config,
        status=ResourceStatus.ACTIVE
    )
    db.add(server)
    await db.commit()
    
    # Try to connect
    try:
        client = await mcp_manager.register_client(server.name, {
            "type": server.type,
            "endpoint": server.endpoint,
            **server.config
        })
        server.tools = [t.dict() for t in client.tools]
        server.resources = [r.dict() for r in client.resources]
        await db.commit()
    except Exception as e:
        server.status = ResourceStatus.INACTIVE
        server.last_error = str(e)
        await db.commit()
    
    return server

@router.post("/{id}/connect")
async def connect_mcp_server(
    id: str,
    db: AsyncSession = Depends(get_db)
):
    """Test connection to MCP server"""
    result = await db.execute(select(MCPServer).where(MCPServer.id == id))
    server = result.scalar_one_or_none()
    
    if not server:
        raise HTTPException(404, "MCP server not found")
    
    try:
        client = await mcp_manager.register_client(server.name, {
            "type": server.type,
            "endpoint": server.endpoint,
            **server.config
        })
        return {"connected": True, "tools": len(client.tools)}
    except Exception as e:
        return {"connected": False, "error": str(e)}
```

---

## 6. Data Model

### 6.1 MCPServer Model (Existing - minor updates)

```python
# models/application.py
class MCPServer(Base):
    __tablename__ = "mcp_servers"
    
    id = Column(String, primary_key=True, default=generate_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id", ondelete="CASCADE"))
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    
    # Transport configuration
    type = Column(String(100), nullable=False)  # "sse" or "http"
    endpoint = Column(String(500), nullable=False)  # URL
    config = Column(JSON, default=dict)  # headers, timeout, etc.
    
    # Status
    status = Column(SQLEnum(ResourceStatus), default=ResourceStatus.ACTIVE)
    last_connected_at = Column(DateTime(timezone=True))
    last_error = Column(Text)
    
    # Cached capabilities (updated on connect)
    tools = Column(JSON, default=list)  # [{"name": "...", "description": "..."}]
    resources = Column(JSON, default=list)  # [{"uri": "...", "name": "..."}]
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

---

## 7. Error Handling

### 7.1 Error Types

| Error Type | Handler | Recovery |
|------------|---------|----------|
| Connection failed | Retry with exponential backoff (3 attempts) | Mark status=inactive, log error |
| Tool call failed | Return error response to agent | Allow agent to retry or use fallback |
| Timeout (30s) | Cancel request, raise MCPError | Notify agent, continue other tools |
| Authentication failed | Skip server, log warning | Mark status=inactive |

### 7.2 Error Response Format

```python
# MCP tool call error response
{
    "type": "mcp_error",
    "server_name": "weather-api",
    "error": {
        "code": "connection_timeout",
        "message": "Connection timed out after 30s",
        "recoverable": true
    },
    "tool_name": "get_weather",
    "suggestions": ["retry", "use_cached_data", "fallback_skill"]
}
```

---

## 8. Testing Strategy

### 8.1 Unit Tests

| Test File | Tests | Purpose |
|-----------|-------|---------|
| `tests/unit/test_mcp_client.py` | 4 tests | SSEMCPClient, StreamableHttpMCPClient with mocked HTTP |
| `tests/unit/test_toolkit_mcp.py` | 3 tests | register_mcp_server, get_tool_schemas, execute_tool |
| `tests/unit/test_mcp_manager.py` | 3 tests | register_client, call_tool across multiple clients |

### 8.2 Integration Tests

| Test File | Tests | Purpose |
|-----------|-------|---------|
| `tests/integration/test_mcp_startup.py` | 2 tests | Load from database, config file |
| `tests/integration/test_mcp_agent.py` | 2 tests | ReActAgent calls MCP tool end-to-end |

### 8.3 Test Implementation

```python
# tests/unit/test_mcp_client.py
import pytest
from unittest.mock import AsyncMock, patch
from agent.mcp.client import SSEMCPClient, StreamableHttpMCPClient

class TestSSEMCPClient:
    @pytest.mark.asyncio
    async def test_connect_loads_tools(self):
        """Test SSEMCPClient connection and tool discovery"""
        client = SSEMCPClient({
            "name": "test",
            "endpoint": "http://test-server",
            "type": "sse"
        })
        
        with patch("httpx.AsyncClient") as mock_http:
            mock_http.return_value.post = AsyncMock(return_value=Mock(
                json=lambda: {"protocolVersion": "2024-11-05"},
                raise_for_status=lambda: None
            ))
            mock_http.return_value.get = AsyncMock(return_value=Mock(
                json=lambda: {"tools": [{"name": "test_tool", "description": "Test"}]}
            ))
            
            await client.connect()
            
            assert client.connected
            assert len(client.tools) == 1
    
    @pytest.mark.asyncio
    async def test_call_tool_returns_result(self):
        """Test tool execution"""
        client = SSEMCPClient({"endpoint": "http://test"})
        client.connected = True
        
        with patch("httpx.AsyncClient") as mock_http:
            mock_http.return_value.post = AsyncMock(return_value=Mock(
                json=lambda: {"content": [{"type": "text", "text": "result"}]}
            ))
            
            result = await client.call_tool("test_tool", {"arg": "value"})
            
            assert result == [{"type": "text", "text": "result"}]
```

---

## 9. Implementation Tasks

### 9.1 Files to Create/Modify

| File | Action | Purpose |
|------|--------|---------|
| `agent/mcp/client.py` | Modify | Add StreamableHttpMCPClient, enhance SSEMCPClient |
| `agent/agentscope/toolkit.py` | Modify | Add register_mcp_server, execute_tool |
| `gateway/api/v1/mcp_servers.py` | Create | MCP Server CRUD API |
| `gateway/api/v1/__init__.py` | Modify | Add MCP router |
| `gateway/main.py` | Modify | Add load_mcp_servers to lifespan |
| `schemas/mcp.py` | Create | MCP request/response schemas |
| `config/mcp_servers.yml` | Create | Example MCP server config |
| `tests/unit/test_mcp_client.py` | Create | MCP client tests |
| `tests/unit/test_toolkit_mcp.py` | Create | Toolkit MCP tests |

### 9.2 Task Order

1. Enhance MCPClient classes (SSE + StreamableHttp)
2. Enhance AgentToolkit with MCP integration
3. Create MCP Server API
4. Add startup loading
5. Write tests
6. Verify integration

---

## 10. Success Criteria

| Criteria | Verification |
|----------|--------------|
| MCP servers connect on startup | Log shows "[OK] MCP server connected" |
| MCP tools available in Toolkit | toolkit.get_tool_schemas() returns MCP tools |
| ReActAgent can call MCP tools | Integration test passes |
| MCP API CRUD works | API endpoints return correct responses |
| Tests pass | 6 unit tests + 2 integration tests passing |

---

## 11. Dependencies

- `httpx>=0.25.0` - HTTP client for SSE/HTTP transports
- `mcp>=0.9.0` - MCP protocol (already in dependencies)
- `pyyaml>=6.0` - Config file parsing

---

## 12. References

- MCP Protocol Spec: https://spec.modelcontextprotocol.io/
- MCP SSE Transport: https://spec.modelcontextprotocol.io/specification/basic/transports/sse/
- AgentScope Toolkit: https://doc.agentscope.io/tutorial/tool.html