"""Pipeline execution integration tests for AgentOrchestrator"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import sys
import os

# Add project root to path for direct imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


class TestPipelineFlow:
    """Test multi-agent pipeline execution flows"""

    @pytest.mark.asyncio
    async def test_execute_pipeline_sequential(self):
        """Test sequential pipeline execution with multiple agents"""
        from agent.core.orchestrator import AgentOrchestrator
        from agent.agentscope.pipeline import PipelineType
        
        orchestrator = AgentOrchestrator()
        
        # Create mock agents
        mock_agent1 = AsyncMock(return_value=MagicMock(content="Step 1 result"))
        mock_agent2 = AsyncMock(return_value=MagicMock(content="Step 2 result"))
        mock_agent3 = AsyncMock(return_value=MagicMock(content="Final result"))
        
        # Mock config loading for all agents
        mock_agent_config = {
            "id": "test-agent",
            "identity": {"name": "Test Agent", "code": "test", "persona": "Test"},
            "capabilities": {"skills": [], "llm": {"model": "gpt-4"}}
        }
        
        with patch.object(orchestrator, '_load_agent_config', new_callable=AsyncMock) as mock_load:
            with patch.object(orchestrator, '_create_toolkit', new_callable=AsyncMock) as mock_toolkit:
                with patch.object(orchestrator.factory, 'create_agent', new_callable=AsyncMock) as mock_create:
                    mock_load.return_value = mock_agent_config
                    mock_toolkit.return_value = MagicMock()
                    mock_create.side_effect = [mock_agent1, mock_agent2, mock_agent3]
                    
                    # Execute sequential pipeline
                    result = await orchestrator.execute_pipeline(
                        agents=["agent-1", "agent-2", "agent-3"],
                        input_data={"message": "Start pipeline"},
                        pipeline_type=PipelineType.SEQUENTIAL,
                        memory={},
                        conversation_id="conv-123"
                    )
                    
                    # Verify all agents were called in sequence
                    assert mock_create.call_count == 3
                    assert result["type"] == "pipeline_response"
                    assert result["pipeline_type"] == "sequential"
                    assert "results" in result
                    assert len(result["results"]) == 3

    @pytest.mark.asyncio
    async def test_execute_pipeline_parallel(self):
        """Test parallel pipeline execution with fan-out/fan-in"""
        from agent.core.orchestrator import AgentOrchestrator
        from agent.agentscope.pipeline import PipelineType
        
        orchestrator = AgentOrchestrator()
        
        # Create mock agents with different responses
        mock_agent1 = AsyncMock(return_value=MagicMock(content="Parallel result 1"))
        mock_agent2 = AsyncMock(return_value=MagicMock(content="Parallel result 2"))
        mock_agent3 = AsyncMock(return_value=MagicMock(content="Parallel result 3"))
        
        mock_agent_config = {
            "id": "test-agent",
            "identity": {"name": "Test Agent", "code": "test", "persona": "Test"},
            "capabilities": {"skills": [], "llm": {"model": "gpt-4"}}
        }
        
        with patch.object(orchestrator, '_load_agent_config', new_callable=AsyncMock) as mock_load:
            with patch.object(orchestrator, '_create_toolkit', new_callable=AsyncMock) as mock_toolkit:
                with patch.object(orchestrator.factory, 'create_agent', new_callable=AsyncMock) as mock_create:
                    mock_load.return_value = mock_agent_config
                    mock_toolkit.return_value = MagicMock()
                    mock_create.side_effect = [mock_agent1, mock_agent2, mock_agent3]
                    
                    # Execute parallel pipeline
                    result = await orchestrator.execute_pipeline(
                        agents=["agent-1", "agent-2", "agent-3"],
                        input_data={"message": "Parallel execution"},
                        pipeline_type=PipelineType.PARALLEL,
                        memory={},
                        conversation_id="conv-456"
                    )
                    
                    # Verify all agents were called
                    assert mock_create.call_count == 3
                    assert result["type"] == "pipeline_response"
                    assert result["pipeline_type"] == "parallel"
                    assert "results" in result
                    assert len(result["results"]) == 3

    @pytest.mark.asyncio
    async def test_execute_pipeline_with_memory(self):
        """Test pipeline execution with shared memory between agents"""
        from agent.core.orchestrator import AgentOrchestrator
        from agent.agentscope.pipeline import PipelineType
        
        orchestrator = AgentOrchestrator()
        
        # Track calls to verify memory passing
        call_history = []
        
        async def mock_agent_call(msg):
            call_history.append(msg)
            # Each agent adds to the memory
            content = f"Processed: {getattr(msg, 'content', str(msg))}"
            return MagicMock(content=content)
        
        mock_agent1 = AsyncMock(side_effect=mock_agent_call)
        mock_agent2 = AsyncMock(side_effect=mock_agent_call)
        mock_agent3 = AsyncMock(side_effect=mock_agent_call)
        
        mock_agent_config = {
            "id": "test-agent",
            "identity": {"name": "Test Agent", "code": "test", "persona": "Test"},
            "capabilities": {"skills": [], "llm": {"model": "gpt-4"}}
        }
        
        initial_memory = {"step": 0, "data": "initial"}
        
        with patch.object(orchestrator, '_load_agent_config', new_callable=AsyncMock) as mock_load:
            with patch.object(orchestrator, '_create_toolkit', new_callable=AsyncMock) as mock_toolkit:
                with patch.object(orchestrator.factory, 'create_agent', new_callable=AsyncMock) as mock_create:
                    mock_load.return_value = mock_agent_config
                    mock_toolkit.return_value = MagicMock()
                    mock_create.side_effect = [mock_agent1, mock_agent2, mock_agent3]
                    
                    # Execute pipeline with memory
                    result = await orchestrator.execute_pipeline(
                        agents=["agent-1", "agent-2", "agent-3"],
                        input_data={"message": "With memory"},
                        pipeline_type=PipelineType.SEQUENTIAL,
                        memory=initial_memory,
                        conversation_id="conv-789"
                    )
                    
                    # Verify memory was maintained
                    assert result["type"] == "pipeline_response"
                    assert result["memory"] is not None
                    assert len(call_history) == 3  # All 3 agents were called

    @pytest.mark.asyncio
    async def test_execute_pipeline_stream_sequential(self):
        """Test streaming sequential pipeline execution"""
        from agent.core.orchestrator import AgentOrchestrator
        from agent.agentscope.pipeline import PipelineType
        
        orchestrator = AgentOrchestrator()
        
        # Mock agents
        mock_agent1 = AsyncMock(return_value=MagicMock(content="Step 1"))
        mock_agent2 = AsyncMock(return_value=MagicMock(content="Step 2"))
        
        mock_agent_config = {
            "id": "test-agent",
            "identity": {"name": "Test Agent", "code": "test", "persona": "Test"},
            "capabilities": {"skills": [], "llm": {"model": "gpt-4"}}
        }
        
        with patch.object(orchestrator, '_load_agent_config', new_callable=AsyncMock) as mock_load:
            with patch.object(orchestrator, '_create_toolkit', new_callable=AsyncMock) as mock_toolkit:
                with patch.object(orchestrator.factory, 'create_agent', new_callable=AsyncMock) as mock_create:
                    mock_load.return_value = mock_agent_config
                    mock_toolkit.return_value = MagicMock()
                    mock_create.side_effect = [mock_agent1, mock_agent2]
                    
                    # Collect streamed chunks
                    chunks = []
                    async for chunk in orchestrator.execute_pipeline_stream(
                        agents=["agent-1", "agent-2"],
                        input_data={"message": "Stream test"},
                        pipeline_type=PipelineType.SEQUENTIAL,
                        memory={}
                    ):
                        chunks.append(chunk)
                    
                    # Verify streaming output
                    assert len(chunks) > 0
                    # Last chunk should be completion marker
                    assert chunks[-1].get("done") is True
                    assert chunks[-1].get("type") == "complete"

    @pytest.mark.asyncio
    async def test_execute_pipeline_single_agent(self):
        """Test pipeline with single agent (degenerates to simple execution)"""
        from agent.core.orchestrator import AgentOrchestrator
        from agent.agentscope.pipeline import PipelineType
        
        orchestrator = AgentOrchestrator()
        
        mock_agent = AsyncMock(return_value=MagicMock(content="Single agent result"))
        
        mock_agent_config = {
            "id": "test-agent",
            "identity": {"name": "Test Agent", "code": "test", "persona": "Test"},
            "capabilities": {"skills": [], "llm": {"model": "gpt-4"}}
        }
        
        with patch.object(orchestrator, '_load_agent_config', new_callable=AsyncMock) as mock_load:
            with patch.object(orchestrator, '_create_toolkit', new_callable=AsyncMock) as mock_toolkit:
                with patch.object(orchestrator.factory, 'create_agent', new_callable=AsyncMock) as mock_create:
                    mock_load.return_value = mock_agent_config
                    mock_toolkit.return_value = MagicMock()
                    mock_create.return_value = mock_agent
                    
                    result = await orchestrator.execute_pipeline(
                        agents=["agent-1"],
                        input_data={"message": "Single agent"},
                        pipeline_type=PipelineType.SINGLE,
                        memory={},
                        conversation_id="conv-single"
                    )
                    
                    assert result["type"] == "pipeline_response"
                    assert result["pipeline_type"] == "single"
                    # Only one agent should be created
                    assert mock_create.call_count == 1
