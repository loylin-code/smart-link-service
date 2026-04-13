"""Toolkit MCP integration tests."""
import pytest
from unittest.mock import MagicMock, AsyncMock
from agent.agentscope.toolkit import AgentToolkit
from agent.mcp.client import MCPTool


class TestToolkitMCP:
    """Test AgentToolkit MCP integration."""
    
    @pytest.mark.asyncio
    async def test_register_mcp_server_adds_tools(self):
        """Test register_mcp_server adds MCP tools to toolkit."""
        toolkit = AgentToolkit()
        
        # Create mock MCP client with tools
        mock_client = MagicMock()
        mock_client.config = {"name": "weather-server"}
        mock_client.tools = [
            MCPTool(name="get_weather", description="Get weather info", input_schema={"type": "object"})
        ]
        
        await toolkit.register_mcp_server(mock_client)
        
        schemas = toolkit.get_tool_schemas()
        assert len(schemas) == 1
        assert schemas[0]["function"]["name"] == "get_weather"
    
    @pytest.mark.asyncio
    async def test_execute_tool_calls_mcp_client(self):
        """Test execute_tool calls MCP client."""
        toolkit = AgentToolkit()
        
        mock_client = MagicMock()
        mock_client.config = {"name": "test-server"}
        mock_client.call_tool = AsyncMock(return_value={"result": "success"})
        mock_client.tools = [
            MCPTool(name="test_tool", description="Test", input_schema={})
        ]
        
        await toolkit.register_mcp_server(mock_client)
        
        result = await toolkit.execute_tool("test_tool", {"arg": "value"})
        
        mock_client.call_tool.assert_called_once_with("test_tool", {"arg": "value"})
        assert result == {"result": "success"}
    
    @pytest.mark.asyncio
    async def test_get_tool_schemas_agent_scope_format(self):
        """Test get_tool_schemas returns AgentScope format."""
        toolkit = AgentToolkit()
        
        mock_client = MagicMock()
        mock_client.config = {"name": "api-server"}
        mock_client.tools = [
            MCPTool(
                name="api_call",
                description="Make API call",
                input_schema={
                    "type": "object",
                    "properties": {"url": {"type": "string"}}
                }
            )
        ]
        
        await toolkit.register_mcp_server(mock_client)
        
        schemas = toolkit.get_tool_schemas()
        
        assert schemas[0]["type"] == "function"
        assert schemas[0]["function"]["name"] == "api_call"
        assert "url" in schemas[0]["function"]["parameters"]["properties"]
