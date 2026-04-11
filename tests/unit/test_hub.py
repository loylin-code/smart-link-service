"""MessageHub 单元测试"""
import pytest
from unittest.mock import MagicMock, AsyncMock
import sys
import os

# Add project root to path for direct imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

class TestAgentHub:
    """AgentHub 测试类"""
    
    def test_singleton_pattern(self):
        """测试单例模式"""
        from agent.agentscope.hub import AgentHub
        AgentHub._instance = None
        hub1 = AgentHub.get_instance()
        hub2 = AgentHub.get_instance()
        assert hub1 is hub2
    
    def test_initial_state(self):
        """测试初始状态"""
        from agent.agentscope.hub import AgentHub
        AgentHub._instance = None
        hub = AgentHub.get_instance()
        assert hub.hub is None
        assert hub.participants == []
        assert hub.message_history == []
    
    @pytest.mark.asyncio
    async def test_initialize(self):
        """测试初始化"""
        from agent.agentscope.hub import AgentHub
        AgentHub._instance = None
        hub = AgentHub.get_instance()
        mock_agents = [MagicMock(name="agent1"), MagicMock(name="agent2")]
        await hub.initialize(mock_agents)
        assert hub.participants == mock_agents
        assert len(hub.message_history) == 0
    
    def test_get_history(self):
        """测试历史记录获取"""
        from agent.agentscope.hub import AgentHub
        AgentHub._instance = None
        hub = AgentHub.get_instance()
        hub.message_history = ["msg1", "msg2", "msg3", "msg4", "msg5"]
        history = hub.get_history(limit=3)
        assert len(history) == 3
        assert history == ["msg3", "msg4", "msg5"]
