"""AgentFactory 单元测试"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import sys
import os

# Add project root to path for direct imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


class TestAgentFactory:
    """AgentFactory 测试类"""
    
    def test_init(self):
        """测试初始化"""
        from agent.agentscope.agent_factory import AgentFactory
        factory = AgentFactory()
        assert factory._model_configs is not None
        assert "default" in factory._model_configs
    
    def test_build_sys_prompt(self):
        """测试系统提示词构建"""
        from agent.agentscope.agent_factory import AgentFactory
        factory = AgentFactory()
        identity = {
            "name": "测试助手",
            "code": "test_assistant",
            "persona": "你是一个测试助手",
            "responsibilities": ["回答问题", "执行任务"]
        }
        prompt = factory._build_sys_prompt(identity, {})
        assert "测试助手" in prompt
        assert "回答问题" in prompt
        assert "你是一个测试助手" in prompt
    
    @pytest.mark.asyncio
    async def test_create_agent(self):
        """测试创建 Agent"""
        from agent.agentscope.agent_factory import AgentFactory
        factory = AgentFactory()
        with patch('agentscope.agent.ReActAgent') as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent_class.return_value = mock_agent
            agent = await factory.create_agent("test", "prompt", None)
            assert agent is not None
            mock_agent_class.assert_called_once()
