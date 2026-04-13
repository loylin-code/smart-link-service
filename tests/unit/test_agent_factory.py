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
    
    @pytest.mark.asyncio
    async def test_create_agent_with_memory(self):
        """测试创建带记忆的 Agent"""
        from agent.agentscope.agent_factory import AgentFactory
        factory = AgentFactory()
        memory = {"history": [{"role": "user", "content": "Hello"}]}
        tools = ["tool1", "tool2"]
        with patch('agentscope.agent.ReActAgent') as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent_class.return_value = mock_agent
            agent = await factory.create_agent_with_memory(
                model_name="gpt-4",
                sys_prompt="You are helpful",
                memory=memory,
                tools=tools
            )
            assert agent is not None
            mock_agent_class.assert_called_once()
            call_args = mock_agent_class.call_args
            assert call_args[1]["sys_prompt"] == "You are helpful"
            assert call_args[1]["tools"] == tools
    
    @pytest.mark.asyncio
    async def test_create_sub_agent(self):
        """测试创建子 Agent"""
        from agent.agentscope.agent_factory import AgentFactory
        factory = AgentFactory()
        role_config = {
            "name": "ResearchAgent",
            "code": "research_agent",
            "persona": "You are a research assistant",
            "responsibilities": ["Search information", "Analyze data"]
        }
        toolkit = MagicMock()
        with patch('agentscope.agent.ReActAgent') as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent_class.return_value = mock_agent
            agent = await factory.create_sub_agent(role_config, toolkit)
            assert agent is not None
            mock_agent_class.assert_called_once()
            call_args = mock_agent_class.call_args
            assert "ResearchAgent" in call_args[1]["sys_prompt"]
            assert "Search information" in call_args[1]["sys_prompt"]
            assert "Analyze data" in call_args[1]["sys_prompt"]
    
    @pytest.mark.asyncio
    async def test_create_plan_agent(self):
        """测试创建计划 Agent"""
        from agent.agentscope.agent_factory import AgentFactory
        factory = AgentFactory()
        sub_agents_config = [
            {"name": "Researcher", "role": "research"},
            {"name": "Writer", "role": "write"}
        ]
        toolkit = MagicMock()
        with patch('agentscope.agent.ReActAgent') as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent_class.return_value = mock_agent
            agent = await factory.create_plan_agent(sub_agents_config, toolkit)
            assert agent is not None
            mock_agent_class.assert_called_once()
            call_args = mock_agent_class.call_args
            assert "PlanAgent" in call_args[1]["name"]
            assert "PlanAgent" in call_args[1]["sys_prompt"]
