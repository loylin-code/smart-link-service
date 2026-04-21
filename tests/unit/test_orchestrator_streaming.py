"""
Unit tests for AgentOrchestrator.execute_stream_openai

Tests the OpenAI-compatible streaming interface implementation.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import AsyncIterator, List

from agent.core.orchestrator import AgentOrchestrator
from agent.core.interrupt_manager import InterruptManager
from agent.core.chunk_builder import ChunkBuilder
from schemas.openai_compat import ChatCompletionChunk


class TestExecuteStreamOpenai:
    """Test execute_stream_openai method"""

    @pytest.fixture
    def orchestrator(self):
        """Create AgentOrchestrator instance"""
        return AgentOrchestrator()

    @pytest.fixture
    def mock_role_config(self):
        """Mock agent role configuration"""
        return {
            "identity": {
                "name": "Test Agent",
                "description": "A test agent"
            },
            "capabilities": {
                "llm": {
                    "model": "gpt-4",
                    "provider": "openai"
                },
                "skills": []
            }
        }

    @pytest.fixture
    def mock_llm_chunks(self):
        """Mock LiteLLM streaming chunks"""
        return [
            {"content": "Hello", "finish_reason": None, "tool_calls": [], "usage": None},
            {"content": " world", "finish_reason": None, "tool_calls": [], "usage": None},
            {"content": "", "finish_reason": "stop", "tool_calls": [], "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}},
        ]

    def _create_mock_llm_stream(self, chunks: List[dict]) -> AsyncIterator[dict]:
        """Create async iterator for mock LLM chunks"""
        async def stream_gen():
            for chunk in chunks:
                yield chunk
        return stream_gen()

    @pytest.mark.asyncio
    async def test_returns_chat_completion_chunk_objects(
        self, orchestrator, mock_role_config, mock_llm_chunks
    ):
        """Test that method returns ChatCompletionChunk objects, not dicts"""
        # Mock dependencies
        orchestrator._load_agent_config = AsyncMock(return_value=mock_role_config)
        orchestrator._create_toolkit = AsyncMock(return_value=MagicMock(get_tool_schemas=MagicMock(return_value=[])))
        
        # Mock LLMClient.chat_stream_openai
        mock_stream = self._create_mock_llm_stream(mock_llm_chunks)
        
        with patch("agent.core.orchestrator.LLMClient") as MockLLMClient:
            mock_client_instance = MagicMock()
            mock_client_instance.chat_stream_openai = MagicMock(return_value=mock_stream)
            MockLLMClient.return_value = mock_client_instance
            
            chunks = []
            async for chunk in orchestrator.execute_stream_openai(
                agent_id="test-agent",
                execution_id="exec-001",
                input_data={"message": "Hello"}
            ):
                chunks.append(chunk)
            
            # Verify all chunks are ChatCompletionChunk objects
            for chunk in chunks:
                assert isinstance(chunk, ChatCompletionChunk), \
                    f"Expected ChatCompletionChunk, got {type(chunk)}"

    @pytest.mark.asyncio
    async def test_first_chunk_has_assistant_role(
        self, orchestrator, mock_role_config, mock_llm_chunks
    ):
        """Test that first chunk has role='assistant'"""
        orchestrator._load_agent_config = AsyncMock(return_value=mock_role_config)
        orchestrator._create_toolkit = AsyncMock(return_value=MagicMock(get_tool_schemas=MagicMock(return_value=[])))
        
        mock_stream = self._create_mock_llm_stream(mock_llm_chunks)
        
        with patch("agent.core.orchestrator.LLMClient") as MockLLMClient:
            mock_client_instance = MagicMock()
            mock_client_instance.chat_stream_openai = MagicMock(return_value=mock_stream)
            MockLLMClient.return_value = mock_client_instance
            
            chunks = []
            async for chunk in orchestrator.execute_stream_openai(
                agent_id="test-agent",
                execution_id="exec-002",
                input_data={"message": "Hello"}
            ):
                chunks.append(chunk)
            
            # First chunk should have role="assistant"
            assert len(chunks) > 0
            first_chunk = chunks[0]
            assert first_chunk.choices[0].delta.role == "assistant"

    @pytest.mark.asyncio
    async def test_content_chunks_yielded_correctly(
        self, orchestrator, mock_role_config, mock_llm_chunks
    ):
        """Test that content chunks are yielded correctly"""
        orchestrator._load_agent_config = AsyncMock(return_value=mock_role_config)
        orchestrator._create_toolkit = AsyncMock(return_value=MagicMock(get_tool_schemas=MagicMock(return_value=[])))
        
        mock_stream = self._create_mock_llm_stream(mock_llm_chunks)
        
        with patch("agent.core.orchestrator.LLMClient") as MockLLMClient:
            mock_client_instance = MagicMock()
            mock_client_instance.chat_stream_openai = MagicMock(return_value=mock_stream)
            MockLLMClient.return_value = mock_client_instance
            
            chunks = []
            async for chunk in orchestrator.execute_stream_openai(
                agent_id="test-agent",
                execution_id="exec-003",
                input_data={"message": "Hello"}
            ):
                chunks.append(chunk)
            
            # Find content chunks (skip role chunk)
            content_chunks = [
                c for c in chunks
                if c.choices[0].delta.content is not None
            ]
            
            # Should have content from mock chunks
            assert len(content_chunks) >= 2
            assert content_chunks[0].choices[0].delta.content == "Hello"
            assert content_chunks[1].choices[0].delta.content == " world"

    @pytest.mark.asyncio
    async def test_final_chunk_has_stop_finish_reason(
        self, orchestrator, mock_role_config, mock_llm_chunks
    ):
        """Test that final chunk has finish_reason='stop'"""
        orchestrator._load_agent_config = AsyncMock(return_value=mock_role_config)
        orchestrator._create_toolkit = AsyncMock(return_value=MagicMock(get_tool_schemas=MagicMock(return_value=[])))
        
        mock_stream = self._create_mock_llm_stream(mock_llm_chunks)
        
        with patch("agent.core.orchestrator.LLMClient") as MockLLMClient:
            mock_client_instance = MagicMock()
            mock_client_instance.chat_stream_openai = MagicMock(return_value=mock_stream)
            MockLLMClient.return_value = mock_client_instance
            
            chunks = []
            async for chunk in orchestrator.execute_stream_openai(
                agent_id="test-agent",
                execution_id="exec-004",
                input_data={"message": "Hello"}
            ):
                chunks.append(chunk)
            
            # Final chunk should have finish_reason="stop"
            final_chunk = chunks[-1]
            assert final_chunk.choices[0].finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_interrupt_manager_registered_and_unregistered(
        self, orchestrator, mock_role_config, mock_llm_chunks
    ):
        """Test that InterruptManager is properly registered and unregistered"""
        orchestrator._load_agent_config = AsyncMock(return_value=mock_role_config)
        orchestrator._create_toolkit = AsyncMock(return_value=MagicMock(get_tool_schemas=MagicMock(return_value=[])))
        
        mock_stream = self._create_mock_llm_stream(mock_llm_chunks)
        
        execution_id = "exec-005"
        
        with patch("agent.core.orchestrator.LLMClient") as MockLLMClient:
            mock_client_instance = MagicMock()
            mock_client_instance.chat_stream_openai = MagicMock(return_value=mock_stream)
            MockLLMClient.return_value = mock_client_instance
            
            # Execute stream
            chunks = []
            async for chunk in orchestrator.execute_stream_openai(
                agent_id="test-agent",
                execution_id=execution_id,
                input_data={"message": "Hello"}
            ):
                chunks.append(chunk)
            
            # After execution, execution should be unregistered
            assert execution_id not in orchestrator.interrupt_manager._local_executions

    @pytest.mark.asyncio
    async def test_cancel_event_stops_stream(
        self, orchestrator, mock_role_config
    ):
        """Test that cancel event stops the stream"""
        orchestrator._load_agent_config = AsyncMock(return_value=mock_role_config)
        orchestrator._create_toolkit = AsyncMock(return_value=MagicMock(get_tool_schemas=MagicMock(return_value=[])))
        
        # Mock LLM stream that yields indefinitely
        async def infinite_stream():
            while True:
                yield {"content": "data", "finish_reason": None, "tool_calls": [], "usage": None}
                await asyncio.sleep(0.01)
        
        execution_id = "exec-006"
        
        with patch("agent.core.orchestrator.LLMClient") as MockLLMClient:
            mock_client_instance = MagicMock()
            mock_client_instance.chat_stream_openai = MagicMock(return_value=infinite_stream())
            MockLLMClient.return_value = mock_client_instance
            
            # Start streaming in background
            chunks_received = []
            
            async def collect_chunks():
                async for chunk in orchestrator.execute_stream_openai(
                    agent_id="test-agent",
                    execution_id=execution_id,
                    input_data={"message": "Hello"}
                ):
                    chunks_received.append(chunk)
            
            # Start collection task
            task = asyncio.create_task(collect_chunks())
            
            # Wait a bit for chunks to start
            await asyncio.sleep(0.05)
            
            # Cancel the execution
            orchestrator.interrupt_manager.cancel(execution_id)
            
            # Wait for task to complete (should stop due to cancel)
            await asyncio.wait_for(task, timeout=1.0)
            
            # Should have received some chunks then stopped
            # Last chunk should be a stop chunk
            if len(chunks_received) > 0:
                final_chunk = chunks_received[-1]
                assert final_chunk.choices[0].finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_stream_with_usage_included(
        self, orchestrator, mock_role_config, mock_llm_chunks
    ):
        """Test that usage info is included when include_usage=True"""
        orchestrator._load_agent_config = AsyncMock(return_value=mock_role_config)
        orchestrator._create_toolkit = AsyncMock(return_value=MagicMock(get_tool_schemas=MagicMock(return_value=[])))
        
        mock_stream = self._create_mock_llm_stream(mock_llm_chunks)
        
        with patch("agent.core.orchestrator.LLMClient") as MockLLMClient:
            mock_client_instance = MagicMock()
            mock_client_instance.chat_stream_openai = MagicMock(return_value=mock_stream)
            MockLLMClient.return_value = mock_client_instance
            
            chunks = []
            async for chunk in orchestrator.execute_stream_openai(
                agent_id="test-agent",
                execution_id="exec-007",
                input_data={"message": "Hello"},
                include_usage=True
            ):
                chunks.append(chunk)
            
            # Final chunk should have usage info
            final_chunk = chunks[-1]
            assert final_chunk.usage is not None
            assert final_chunk.usage.prompt_tokens == 10
            assert final_chunk.usage.completion_tokens == 5
            assert final_chunk.usage.total_tokens == 15

    @pytest.mark.asyncio
    async def test_chunk_builder_and_interrupt_manager_initialized(
        self, orchestrator
    ):
        """Test that chunk_builder and interrupt_manager are initialized in __init__"""
        assert hasattr(orchestrator, 'chunk_builder')
        assert hasattr(orchestrator, 'interrupt_manager')
        
        # Should be proper instances
        assert isinstance(orchestrator.chunk_builder, ChunkBuilder)
        assert isinstance(orchestrator.interrupt_manager, InterruptManager)


class TestExecuteStreamOpenaiErrorHandling:
    """Test error handling in execute_stream_openai"""

    @pytest.fixture
    def orchestrator(self):
        """Create AgentOrchestrator instance"""
        return AgentOrchestrator()

    @pytest.fixture
    def mock_role_config(self):
        """Mock agent role configuration"""
        return {
            "identity": {"name": "Test Agent"},
            "capabilities": {"llm": {"model": "gpt-4"}, "skills": []}
        }

    @pytest.mark.asyncio
    async def test_cleanup_on_agent_not_found(
        self, orchestrator
    ):
        """Test that InterruptManager is cleaned up when agent not found"""
        from core.exceptions import AgentError
        
        orchestrator._load_agent_config = AsyncMock(
            side_effect=AgentError("Agent not found", agent_id="missing-agent")
        )
        
        execution_id = "exec-error-001"
        
        # Execute should raise AgentError but cleanup
        chunks = []
        try:
            async for chunk in orchestrator.execute_stream_openai(
                agent_id="missing-agent",
                execution_id=execution_id,
                input_data={"message": "Hello"}
            ):
                chunks.append(chunk)
        except AgentError:
            pass
        
        # InterruptManager should be cleaned up
        assert execution_id not in orchestrator.interrupt_manager._local_executions

    @pytest.mark.asyncio
    async def test_cleanup_on_llm_error(
        self, orchestrator, mock_role_config
    ):
        """Test that InterruptManager is cleaned up when LLM fails"""
        from core.exceptions import LLMError
        
        orchestrator._load_agent_config = AsyncMock(return_value=mock_role_config)
        orchestrator._create_toolkit = AsyncMock(return_value=MagicMock(get_tool_schemas=MagicMock(return_value=[])))
        
        async def error_stream():
            raise LLMError("LLM connection failed", provider="openai")
            yield  # Never reached
        
        execution_id = "exec-error-002"
        
        with patch("agent.core.orchestrator.LLMClient") as MockLLMClient:
            mock_client_instance = MagicMock()
            mock_client_instance.chat_stream_openai = MagicMock(return_value=error_stream())
            MockLLMClient.return_value = mock_client_instance
            
            chunks = []
            try:
                async for chunk in orchestrator.execute_stream_openai(
                    agent_id="test-agent",
                    execution_id=execution_id,
                    input_data={"message": "Hello"}
                ):
                    chunks.append(chunk)
            except LLMError:
                pass
            
            # InterruptManager should be cleaned up
            assert execution_id not in orchestrator.interrupt_manager._local_executions