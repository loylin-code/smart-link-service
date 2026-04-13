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


class TestAgentHubMsgHub:
    """AgentHub with MsgHub wrapper tests"""
    
    @pytest.fixture(autouse=True)
    def reset_hub(self):
        """Reset AgentHub singleton before each test"""
        from agent.agentscope.hub import AgentHub
        AgentHub._instance = None
        yield
        AgentHub._instance = None
    
    @pytest.mark.asyncio
    async def test_create_msghub_with_participants(self):
        """Test that initialize_with_msghub creates MsgHub instance"""
        from agent.agentscope.hub import AgentHub
        from unittest.mock import MagicMock, patch
        
        hub = AgentHub.get_instance()
        mock_agents = [MagicMock(name="agent1"), MagicMock(name="agent2")]
        announcement = {"content": "Welcome to the hub"}
        
        with patch('agent.agentscope.hub.MsgHub') as MockMsgHub:
            mock_msghub_instance = MagicMock()
            MockMsgHub.return_value = mock_msghub_instance
            
            await hub.initialize_with_msghub(mock_agents, announcement)
            
            assert hub._msghub is not None
            MockMsgHub.assert_called_once_with(
                participants=mock_agents,
                announcement=announcement
            )
    
    @pytest.mark.asyncio
    async def test_broadcast_message(self):
        """Test that broadcast sends message to MsgHub"""
        from agent.agentscope.hub import AgentHub
        from unittest.mock import MagicMock, patch
        
        hub = AgentHub.get_instance()
        
        with patch('agent.agentscope.hub.MsgHub') as MockMsgHub:
            mock_msghub_instance = MagicMock()
            mock_msghub_instance.broadcast = AsyncMock()
            MockMsgHub.return_value = mock_msghub_instance
            
            await hub.initialize_with_msghub([], {"content": "init"})
            
            test_msg = MagicMock(name="test_message")
            await hub.broadcast(test_msg)
            
            mock_msghub_instance.broadcast.assert_called_once_with(test_msg)
