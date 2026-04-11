"""Toolkit 单元测试"""
import pytest
from unittest.mock import MagicMock, AsyncMock


class TestAgentToolkit:
    """AgentToolkit 测试类"""

    def test_init(self):
        """测试初始化"""
        from agent.agentscope.toolkit import AgentToolkit
        toolkit = AgentToolkit()
        assert toolkit._registered_skills == {}
        assert toolkit._registered_mcp == {}

    @pytest.mark.asyncio
    async def test_register_skill(self):
        """测试注册 Skill"""
        from agent.agentscope.toolkit import AgentToolkit
        toolkit = AgentToolkit()
        mock_skill = MagicMock()
        mock_skill.name = "search"
        mock_skill.description = "搜索功能"
        mock_skill.execute = AsyncMock(return_value={"result": "test"})
        await toolkit.register_skill(mock_skill)
        assert "search" in toolkit._registered_skills

    def test_get_tool_schemas(self):
        """测试获取工具 Schema"""
        from agent.agentscope.toolkit import AgentToolkit
        toolkit = AgentToolkit()
        schemas = toolkit.get_tool_schemas()
        assert isinstance(schemas, list)
