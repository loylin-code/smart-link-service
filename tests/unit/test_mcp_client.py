"""MCP client unit tests."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agent.mcp.client import SSEMCPClient, MCPTool


class TestSSEMCPClient:
    """Test SSE MCP client."""
    
    @pytest.mark.asyncio
    async def test_connect_initializes_and_loads_tools(self):
        """Test SSEMCPClient connect loads tools from server."""
        client = SSEMCPClient({
            "name": "test-server",
            "endpoint": "http://test.example.com/mcp",
            "headers": {"Authorization": "Bearer test"},
            "timeout": 30
        })
        
        # Mock httpx.AsyncClient
        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=MagicMock(
            raise_for_status=lambda: None
        ))
        mock_client.get = AsyncMock(return_value=MagicMock(
            json=lambda: {
                "tools": [
                    {"name": "get_weather", "description": "Get weather", "inputSchema": {}}
                ]
            }
        ))
        mock_client.aclose = AsyncMock()
        
        with patch("httpx.AsyncClient", return_value=mock_client):
            await client.connect()
        
        assert client.connected
        assert len(client.tools) == 1
        assert client.tools[0].name == "get_weather"
    
    @pytest.mark.asyncio
    async def test_call_tool_returns_content(self):
        """Test SSEMCPClient call_tool returns result."""
        client = SSEMCPClient({"endpoint": "http://test.example.com"})
        client.connected = True
        
        mock_response = MagicMock()
        mock_response.json = MagicMock(return_value={
            "content": [{"type": "text", "text": "Sunny, 25C"}]
        })
        client.client = MagicMock()
        client.client.post = AsyncMock(return_value=mock_response)
        
        result = await client.call_tool("get_weather", {"location": "Beijing"})
        
        assert result == [{"type": "text", "text": "Sunny, 25C"}]
