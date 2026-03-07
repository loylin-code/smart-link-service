"""
MCP (Model Context Protocol) Client
"""
import asyncio
import json
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from abc import ABC, abstractmethod

from core.config import settings
from core.exceptions import MCPError


class MCPTool(BaseModel):
    """MCP Tool definition"""
    name: str
    description: str
    input_schema: Dict[str, Any]


class MCPResource(BaseModel):
    """MCP Resource definition"""
    uri: str
    name: str
    description: Optional[str] = None
    mime_type: Optional[str] = None


class MCPClient(ABC):
    """
    Base MCP client implementing Model Context Protocol
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tools: List[MCPTool] = []
        self.resources: List[MCPResource] = []
        self.connected = False
    
    @abstractmethod
    async def connect(self):
        """Connect to MCP server"""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Disconnect from MCP server"""
        pass
    
    @abstractmethod
    async def list_tools(self) -> List[MCPTool]:
        """List available tools"""
        pass
    
    @abstractmethod
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool"""
        pass
    
    @abstractmethod
    async def list_resources(self) -> List[MCPResource]:
        """List available resources"""
        pass
    
    @abstractmethod
    async def read_resource(self, uri: str) -> Any:
        """Read a resource"""
        pass


class StdioMCPClient(MCPClient):
    """
    MCP client using stdio transport
    For local MCP servers
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.process: Optional[asyncio.subprocess.Process] = None
        self.command = config.get("command", "")
        self.args = config.get("args", [])
        self.env = config.get("env", {})
    
    async def connect(self):
        """Start MCP server process"""
        import os
        env = {**os.environ, **self.env}
        
        self.process = await asyncio.create_subprocess_exec(
            self.command,
            *self.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env
        )
        
        self.connected = True
        
        # Initialize MCP connection
        await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "smartlink", "version": "1.0.0"}
        })
        
        # Load tools and resources
        self.tools = await self.list_tools()
        self.resources = await self.list_resources()
    
    async def disconnect(self):
        """Stop MCP server process"""
        if self.process:
            self.process.terminate()
            await self.process.wait()
            self.process = None
        self.connected = False
    
    async def _send_request(self, method: str, params: Dict = None) -> Dict:
        """Send JSON-RPC request"""
        if not self.process or not self.process.stdin:
            raise MCPError("Not connected to MCP server")
        
        request = {
            "jsonrpc": "2.0",
            "id": id(self),
            "method": method,
            "params": params or {}
        }
        
        # Send request
        self.process.stdin.write((json.dumps(request) + "\n").encode())
        await self.process.stdin.drain()
        
        # Read response
        response_line = await self.process.stdout.readline()
        if not response_line:
            raise MCPError("No response from MCP server")
        
        response = json.loads(response_line.decode())
        
        if "error" in response:
            raise MCPError(f"MCP error: {response['error']}")
        
        return response.get("result", {})
    
    async def list_tools(self) -> List[MCPTool]:
        """List available tools"""
        result = await self._send_request("tools/list")
        tools = []
        for tool_data in result.get("tools", []):
            tools.append(MCPTool(
                name=tool_data.get("name"),
                description=tool_data.get("description", ""),
                input_schema=tool_data.get("inputSchema", {})
            ))
        return tools
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool"""
        result = await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments
        })
        return result
    
    async def list_resources(self) -> List[MCPResource]:
        """List available resources"""
        result = await self._send_request("resources/list")
        resources = []
        for res_data in result.get("resources", []):
            resources.append(MCPResource(
                uri=res_data.get("uri"),
                name=res_data.get("name"),
                description=res_data.get("description"),
                mime_type=res_data.get("mimeType")
            ))
        return resources
    
    async def read_resource(self, uri: str) -> Any:
        """Read a resource"""
        result = await self._send_request("resources/read", {"uri": uri})
        return result


class SSEMCPClient(MCPClient):
    """
    MCP client using Server-Sent Events transport
    For remote MCP servers
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.endpoint = config.get("endpoint", "")
        self.headers = config.get("headers", {})
    
    async def connect(self):
        """Connect to remote MCP server"""
        import httpx
        self.client = httpx.AsyncClient(headers=self.headers)
        self.connected = True
        
        # Initialize
        response = await self.client.post(f"{self.endpoint}/initialize", json={
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "smartlink", "version": "1.0.0"}
        })
        response.raise_for_status()
        
        # Load tools
        self.tools = await self.list_tools()
        self.resources = await self.list_resources()
    
    async def disconnect(self):
        """Disconnect from server"""
        if hasattr(self, 'client'):
            await self.client.aclose()
        self.connected = False
    
    async def list_tools(self) -> List[MCPTool]:
        """List available tools"""
        response = await self.client.get(f"{self.endpoint}/tools")
        data = response.json()
        return [MCPTool(**t) for t in data.get("tools", [])]
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool"""
        response = await self.client.post(
            f"{self.endpoint}/tools/call",
            json={"name": name, "arguments": arguments}
        )
        return response.json()
    
    async def list_resources(self) -> List[MCPResource]:
        """List available resources"""
        response = await self.client.get(f"{self.endpoint}/resources")
        data = response.json()
        return [MCPResource(**r) for r in data.get("resources", [])]
    
    async def read_resource(self, uri: str) -> Any:
        """Read a resource"""
        response = await self.client.get(f"{self.endpoint}/resources", params={"uri": uri})
        return response.json()


class MCPManager:
    """
    Manager for multiple MCP clients
    """
    
    def __init__(self):
        self.clients: Dict[str, MCPClient] = {}
    
    async def register_client(self, name: str, config: Dict[str, Any]) -> MCPClient:
        """Register and connect an MCP client"""
        transport = config.get("type", "stdio")
        
        if transport == "stdio":
            client = StdioMCPClient(config)
        elif transport == "sse":
            client = SSEMCPClient(config)
        else:
            raise MCPError(f"Unknown transport: {transport}")
        
        await client.connect()
        self.clients[name] = client
        return client
    
    async def unregister_client(self, name: str):
        """Disconnect and remove an MCP client"""
        if name in self.clients:
            await self.clients[name].disconnect()
            del self.clients[name]
    
    def get_client(self, name: str) -> Optional[MCPClient]:
        """Get an MCP client by name"""
        return self.clients.get(name)
    
    def get_all_tools(self) -> List[Dict[str, Any]]:
        """Get tools from all clients in OpenAI format"""
        tools = []
        for client in self.clients.values():
            for tool in client.tools:
                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.input_schema
                    }
                })
        return tools
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool by name (searches all clients)"""
        for client in self.clients.values():
            for tool in client.tools:
                if tool.name == tool_name:
                    return await client.call_tool(tool_name, arguments)
        raise MCPError(f"Tool not found: {tool_name}")
    
    async def disconnect_all(self):
        """Disconnect all clients"""
        for client in self.clients.values():
            await client.disconnect()
        self.clients.clear()


# Global MCP manager
mcp_manager = MCPManager()