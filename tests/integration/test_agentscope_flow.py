"""AgentScope Orchestrator end-to-end integration tests"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os

# Add project root to path for direct imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


class TestAgentOrchestrator:
    """AgentOrchestrator AgentScope integration tests"""

    def test_init(self):
        """测试 Orchestrator 初始化"""
        from agent.core.orchestrator import AgentOrchestrator
        orchestrator = AgentOrchestrator()
        assert orchestrator.hub is not None
        assert orchestrator.factory is not None
        assert orchestrator.context is not None

    def test_init_with_config(self):
        """测试带配置初始化"""
        from agent.core.orchestrator import AgentOrchestrator
        config = {"custom_setting": "value"}
        orchestrator = AgentOrchestrator(config=config)
        assert orchestrator.config == config

    @pytest.mark.asyncio
    async def test_execute_returns_result(self):
        """测试 execute() 返回结果"""
        from agent.core.orchestrator import AgentOrchestrator
        
        orchestrator = AgentOrchestrator()
        
        # Mock the agent config loading
        mock_agent_config = {
            "id": "test-agent-001",
            "identity": {
                "name": "测试助手",
                "code": "test_assistant",
                "persona": "你是一个测试助手",
                "responsibilities": ["回答问题"]
            },
            "capabilities": {
                "skills": [],
                "llm": {"provider": "openai", "model": "gpt-4"}
            }
        }
        
        # Mock agent response
        mock_response = MagicMock()
        mock_response.content = "Hello, I am the test assistant."
        mock_response.tool_calls = []
        mock_response.metadata = {}
        
        # Mock agent that returns response when called (async callable)
        mock_agent = AsyncMock(return_value=mock_response)
        
        with patch.object(orchestrator, '_load_agent_config', new_callable=AsyncMock) as mock_load:
            with patch.object(orchestrator, '_create_toolkit', new_callable=AsyncMock) as mock_toolkit:
                with patch.object(orchestrator.factory, 'create_agent', new_callable=AsyncMock) as mock_create:
                    mock_load.return_value = mock_agent_config
                    mock_toolkit.return_value = MagicMock()
                    mock_create.return_value = mock_agent
                    
                    result = await orchestrator.execute(
                        agent_id="test-agent-001",
                        input_data={"message": "Hello"}
                    )
                    
                    assert result["type"] == "response"
                    assert "content" in result
                    assert result["content"] == "Hello, I am the test assistant."

    @pytest.mark.asyncio
    async def test_execute_stream_yields_chunks(self):
        """测试 execute_stream() 流式输出"""
        from agent.core.orchestrator import AgentOrchestrator
        
        orchestrator = AgentOrchestrator()
        
        mock_agent_config = {
            "id": "test-agent-001",
            "identity": {
                "name": "测试助手",
                "persona": "你是一个测试助手"
            },
            "capabilities": {"skills": []}
        }
        
        # Mock streaming agent
        async def mock_stream_reply(msg):
            chunks = [
                MagicMock(content="Hello"),
                MagicMock(content=" world"),
                MagicMock(content="!")
            ]
            for chunk in chunks:
                yield chunk
        
        mock_agent = MagicMock()
        mock_agent.stream_reply = mock_stream_reply
        
        with patch.object(orchestrator, '_load_agent_config', new_callable=AsyncMock) as mock_load:
            with patch.object(orchestrator, '_create_toolkit', new_callable=AsyncMock) as mock_toolkit:
                with patch.object(orchestrator.factory, 'create_agent', new_callable=AsyncMock) as mock_create:
                    mock_load.return_value = mock_agent_config
                    mock_toolkit.return_value = MagicMock()
                    mock_create.return_value = mock_agent
                    
                    chunks = []
                    async for chunk in orchestrator.execute_stream(
                        agent_id="test-agent-001",
                        input_data={"message": "Hello"}
                    ):
                        chunks.append(chunk)
                    
                    assert len(chunks) >= 3
                    assert chunks[0]["type"] == "chunk"
                    assert chunks[-1]["type"] == "complete"

    @pytest.mark.asyncio
    async def test_load_agent_config_from_database(self):
        """测试 _load_agent_config() 加载配置"""
        from agent.core.orchestrator import AgentOrchestrator
        from db.session import async_session_maker
        from models.agent import Agent
        
        orchestrator = AgentOrchestrator()
        
        # Mock database session and agent
        mock_agent = MagicMock(spec=Agent)
        mock_agent.id = "test-agent-001"
        mock_agent.name = "测试助手"
        mock_agent.code = "test_assistant"
        mock_agent.persona = "你是一个测试助手"
        mock_agent.skills = []
        mock_agent.tools = []
        mock_agent.mcp_servers = []
        mock_agent.llm_config = {"provider": "openai", "model": "gpt-4"}
        
        mock_agent.to_dict = MagicMock(return_value={
            "id": "test-agent-001",
            "identity": {
                "name": "测试助手",
                "persona": "你是一个测试助手"
            },
            "capabilities": {"skills": []}
        })
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_agent)
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        with patch('agent.core.orchestrator.async_session_maker') as mock_session_maker:
            mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)
            
            config = await orchestrator._load_agent_config("test-agent-001")
            
            assert config is not None
            assert config["id"] == "test-agent-001"

    @pytest.mark.asyncio
    async def test_load_agent_config_not_found_raises_error(self):
        """测试 Agent 不存在时抛出错误"""
        from agent.core.orchestrator import AgentOrchestrator
        from core.exceptions import AgentError
        
        orchestrator = AgentOrchestrator()
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=mock_result)
        
        with patch('agent.core.orchestrator.async_session_maker') as mock_session_maker:
            mock_session_maker.return_value.__aenter__ = AsyncMock(return_value=mock_db)
            mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with pytest.raises(AgentError) as exc_info:
                await orchestrator._load_agent_config("non-existent-agent")
            
            assert "not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_create_toolkit_registers_skills(self):
        """测试 _create_toolkit() 创建 toolkit"""
        from agent.core.orchestrator import AgentOrchestrator
        from agent.agentscope.toolkit import AgentToolkit
        
        orchestrator = AgentOrchestrator()
        
        role_config = {
            "capabilities": {
                "skills": [{"skillId": "search", "version": "1.0.0"}]
            }
        }
        
        # Mock skill registry - patch at the source location
        mock_skill = MagicMock()
        mock_skill.name = "search"
        mock_skill.description = "搜索功能"
        
        with patch('agent.skills.base.skill_registry') as mock_registry:
            mock_registry.get = MagicMock(return_value=mock_skill)
            
            toolkit = await orchestrator._create_toolkit(role_config)
            
            assert toolkit is not None
            assert isinstance(toolkit, AgentToolkit)

    @pytest.mark.asyncio
    async def test_execute_handles_error(self):
        """测试 execute() 错误处理"""
        from agent.core.orchestrator import AgentOrchestrator
        from core.exceptions import AgentError
        
        orchestrator = AgentOrchestrator()
        
        with patch.object(orchestrator, '_load_agent_config', new_callable=AsyncMock) as mock_load:
            mock_load.side_effect = Exception("Database error")
            
            with pytest.raises(AgentError):
                await orchestrator.execute(
                    agent_id="test-agent-001",
                    input_data={"message": "Hello"}
                )

    @pytest.mark.asyncio
    async def test_execute_stream_handles_error(self):
        """测试 execute_stream() 错误处理"""
        from agent.core.orchestrator import AgentOrchestrator
        
        orchestrator = AgentOrchestrator()
        
        with patch.object(orchestrator, '_load_agent_config', new_callable=AsyncMock) as mock_load:
            mock_load.side_effect = Exception("Connection failed")
            
            chunks = []
            async for chunk in orchestrator.execute_stream(
                agent_id="test-agent-001",
                input_data={"message": "Hello"}
            ):
                chunks.append(chunk)
            
            assert len(chunks) > 0
            assert chunks[-1]["type"] == "error"
            assert "Connection failed" in chunks[-1]["content"]

    def test_build_result(self):
        """测试 _build_result() 构建结果"""
        from agent.core.orchestrator import AgentOrchestrator
        
        orchestrator = AgentOrchestrator()
        
        mock_response = MagicMock()
        mock_response.content = "Test response"
        mock_response.tool_calls = [{"id": "call_1"}]
        mock_response.metadata = {"tokens": 100}
        
        result = orchestrator._build_result(mock_response)
        
        assert result["type"] == "response"
        assert result["content"] == "Test response"
        assert result["tool_calls"] == [{"id": "call_1"}]
        assert result["metadata"] == {"tokens": 100}


class TestAgentScopeIntegration:
    """完整 AgentScope 集成流程测试"""

    @pytest.mark.asyncio
    async def test_full_chat_flow(self):
        """测试完整聊天流程"""
        from agent.core.orchestrator import AgentOrchestrator
        
        orchestrator = AgentOrchestrator()
        
        mock_agent_config = {
            "id": "test-agent-001",
            "identity": {
                "name": "测试助手",
                "persona": "你是一个测试助手"
            },
            "capabilities": {
                "skills": [],
                "llm": {"provider": "openai", "model": "gpt-4"}
            }
        }
        
        mock_response = MagicMock()
        mock_response.content = "你好！我是测试助手，有什么可以帮助你的吗？"
        mock_response.tool_calls = []
        
        # Mock agent as async callable that returns response
        mock_agent = AsyncMock(return_value=mock_response)
        
        with patch.object(orchestrator, '_load_agent_config', new_callable=AsyncMock) as mock_load:
            with patch.object(orchestrator, '_create_toolkit', new_callable=AsyncMock) as mock_toolkit:
                with patch.object(orchestrator.factory, 'create_agent', new_callable=AsyncMock) as mock_create:
                    mock_load.return_value = mock_agent_config
                    mock_toolkit.return_value = MagicMock()
                    mock_create.return_value = mock_agent
                    
                    result = await orchestrator.execute(
                        agent_id="test-agent-001",
                        input_data={"message": "你好"},
                        conversation_id="conv-001"
                    )
                    
                    assert result is not None
                    mock_load.assert_called_once_with("test-agent-001")

    @pytest.mark.asyncio
    async def test_full_streaming_flow(self):
        """测试完整流式流程"""
        from agent.core.orchestrator import AgentOrchestrator
        
        orchestrator = AgentOrchestrator()
        
        mock_agent_config = {
            "id": "test-agent-001",
            "identity": {
                "name": "测试助手",
                "persona": "你是一个测试助手"
            },
            "capabilities": {"skills": []}
        }
        
        async def mock_stream(msg):
            yield MagicMock(content="你好")
            yield MagicMock(content="！")
        
        mock_agent = MagicMock()
        mock_agent.stream_reply = mock_stream
        
        with patch.object(orchestrator, '_load_agent_config', new_callable=AsyncMock) as mock_load:
            with patch.object(orchestrator, '_create_toolkit', new_callable=AsyncMock) as mock_toolkit:
                with patch.object(orchestrator.factory, 'create_agent', new_callable=AsyncMock) as mock_create:
                    mock_load.return_value = mock_agent_config
                    mock_toolkit.return_value = MagicMock()
                    mock_create.return_value = mock_agent
                    
                    collected_content = ""
                    async for chunk in orchestrator.execute_stream(
                        agent_id="test-agent-001",
                        input_data={"message": "你好"}
                    ):
                        if chunk["type"] == "chunk":
                            collected_content += chunk.get("content", "")
                    
                    assert collected_content == "你好！"