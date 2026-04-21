"""
Unit tests for StreamingService

Tests the streaming execution helper service that:
- Creates stream context (execution_id, agent_id, chatcmpl_id, cancel_event)
- Handles stream errors and returns error chunks
- Finalizes execution records in database
- Builds initial messages with conversation history
- Checks interrupt signals and returns stop chunks
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from schemas.openai_compat import ChatCompletionChunk, ChatCompletionChunkDelta, ChatCompletionChunkChoice
from models.execution import Execution, ExecutionStatus


class TestStreamingServiceCreateStreamContext:
    """Test create_stream_context method"""

    @pytest.mark.asyncio
    async def test_create_stream_context_returns_proper_dict(self):
        """Test that create_stream_context returns dict with required fields"""
        # This will fail because StreamingService doesn't exist yet
        from services.runtime.streaming import StreamingService
        
        service = StreamingService()
        
        context = service.create_stream_context(
            execution_id="exec-001",
            agent_id="agent-001",
            conversation_id="conv-001"
        )
        
        # Verify required fields exist
        assert "execution_id" in context
        assert "agent_id" in context
        assert "conversation_id" in context
        assert "chatcmpl_id" in context
        assert "cancel_event" in context
        assert "created_at" in context
        
        # Verify values
        assert context["execution_id"] == "exec-001"
        assert context["agent_id"] == "agent-001"
        assert context["conversation_id"] == "conv-001"
        assert context["chatcmpl_id"].startswith("chatcmpl-")
        assert isinstance(context["cancel_event"], asyncio.Event)
        assert isinstance(context["created_at"], datetime)

    @pytest.mark.asyncio
    async def test_create_stream_context_without_conversation_id(self):
        """Test that create_stream_context works without conversation_id"""
        from services.runtime.streaming import StreamingService
        
        service = StreamingService()
        
        context = service.create_stream_context(
            execution_id="exec-002",
            agent_id="agent-002",
            conversation_id=None
        )
        
        # Verify conversation_id is None
        assert context["conversation_id"] is None


class TestStreamingServiceHandleStreamError:
    """Test handle_stream_error method"""

    @pytest.fixture
    def mock_chunk_builder(self):
        """Mock ChunkBuilder"""
        mock = MagicMock()
        mock.build_error_chunk = MagicMock(return_value=ChatCompletionChunk(
            id="chatcmpl-test",
            model="gpt-4",
            choices=[ChatCompletionChunkChoice(
                delta=ChatCompletionChunkDelta(),
                finish_reason="content_filter"
            )]
        ))
        return mock

    @pytest.mark.asyncio
    async def test_handle_stream_error_returns_error_chunk(self, mock_chunk_builder):
        """Test that handle_stream_error returns error chunk"""
        from services.runtime.streaming import StreamingService
        
        service = StreamingService()
        service.chunk_builder = mock_chunk_builder
        
        error = Exception("Test error")
        
        chunk = await service.handle_stream_error(
            execution_id="exec-001",
            error=error,
            chatcmpl_id="chatcmpl-test"
        )
        
        # Verify returns ChatCompletionChunk
        assert isinstance(chunk, ChatCompletionChunk)
        
        # Verify ChunkBuilder.build_error_chunk was called
        assert mock_chunk_builder.build_error_chunk.called

    @pytest.mark.asyncio
    async def test_handle_stream_error_chunk_has_content_filter_reason(self, mock_chunk_builder):
        """Test that error chunk has content_filter finish reason"""
        from services.runtime.streaming import StreamingService
        
        service = StreamingService()
        service.chunk_builder = mock_chunk_builder
        
        error = ValueError("Invalid input")
        
        chunk = await service.handle_stream_error(
            execution_id="exec-002",
            error=error,
            chatcmpl_id="chatcmpl-abc123"
        )
        
        # Verify chunk has content_filter finish_reason
        assert chunk.choices[0].finish_reason == "content_filter"


class TestStreamingServiceFinalizeExecution:
    """Test finalize_execution method"""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        mock = AsyncMock()
        mock.execute = AsyncMock()
        mock.commit = AsyncMock()
        return mock

    @pytest.fixture
    def mock_execution(self):
        """Mock Execution object"""
        execution = MagicMock()
        execution.status = ExecutionStatus.RUNNING
        execution.prompt_tokens = 0
        execution.completion_tokens = 0
        return execution

    @pytest.mark.asyncio
    async def test_finalize_execution_updates_status_to_completed(self, mock_db_session, mock_execution):
        """Test that finalize_execution updates status to completed"""
        from services.runtime.streaming import StreamingService
        
        service = StreamingService()
        
        # Mock database query to return execution
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_execution)
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        await service.finalize_execution(
            execution_id="exec-001",
            status="completed",
            tokens={"prompt": 10, "completion": 20},
            db=mock_db_session
        )
        
        # Verify status updated
        assert mock_execution.status == ExecutionStatus.COMPLETED
        
        # Verify tokens updated
        assert mock_execution.prompt_tokens == 10
        assert mock_execution.completion_tokens == 20
        
        # Verify commit called
        assert mock_db_session.commit.called

    @pytest.mark.asyncio
    async def test_finalize_execution_updates_status_to_failed(self, mock_db_session, mock_execution):
        """Test that finalize_execution updates status to failed"""
        from services.runtime.streaming import StreamingService
        
        service = StreamingService()
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_execution)
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        await service.finalize_execution(
            execution_id="exec-002",
            status="failed",
            tokens={"prompt": 5, "completion": 0},
            db=mock_db_session
        )
        
        # Verify status updated to FAILED
        assert mock_execution.status == ExecutionStatus.FAILED

    @pytest.mark.asyncio
    async def test_finalize_execution_updates_status_to_cancelled(self, mock_db_session, mock_execution):
        """Test that finalize_execution updates status to cancelled"""
        from services.runtime.streaming import StreamingService
        
        service = StreamingService()
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_execution)
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        await service.finalize_execution(
            execution_id="exec-003",
            status="cancelled",
            tokens={"prompt": 3, "completion": 0},
            db=mock_db_session
        )
        
        # Verify status updated to CANCELLED
        assert mock_execution.status == ExecutionStatus.CANCELLED

    @pytest.mark.asyncio
    async def test_finalize_execution_sets_completed_at_timestamp(self, mock_db_session, mock_execution):
        """Test that finalize_execution sets completed_at timestamp"""
        from services.runtime.streaming import StreamingService
        
        service = StreamingService()
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_execution)
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        await service.finalize_execution(
            execution_id="exec-004",
            status="completed",
            tokens={"prompt": 10, "completion": 20},
            db=mock_db_session
        )
        
        # Verify completed_at was set
        assert mock_execution.completed_at is not None


class TestStreamingServiceBuildInitialMessages:
    """Test build_initial_messages method"""

    @pytest.fixture
    def mock_conversation_service(self):
        """Mock ConversationService"""
        mock = MagicMock()
        mock.get_messages_for_llm = AsyncMock(return_value=[
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"}
        ])
        return mock

    @pytest.mark.asyncio
    async def test_build_initial_messages_prepends_history(self, mock_conversation_service):
        """Test that build_initial_messages prepends conversation history"""
        from services.runtime.streaming import StreamingService
        
        service = StreamingService()
        
        request_messages = [{"role": "user", "content": "New question"}]
        
        messages = await service.build_initial_messages(
            request_messages=request_messages,
            conversation_id="conv-001",
            conversation_service=mock_conversation_service
        )
        
        # Verify history was fetched
        assert mock_conversation_service.get_messages_for_llm.called
        
        # Verify history prepended before new message
        assert len(messages) == 3  # 2 history + 1 new
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "New question"

    @pytest.mark.asyncio
    async def test_build_initial_messages_without_conversation_id(self):
        """Test that build_initial_messages returns request_messages when no conversation_id"""
        from services.runtime.streaming import StreamingService
        
        service = StreamingService()
        
        request_messages = [{"role": "user", "content": "Hello"}]
        
        messages = await service.build_initial_messages(
            request_messages=request_messages,
            conversation_id=None,
            conversation_service=None
        )
        
        # Verify returns original messages
        assert messages == request_messages

    @pytest.mark.asyncio
    async def test_build_initial_messages_preserves_order(self, mock_conversation_service):
        """Test that build_initial_messages preserves message order"""
        from services.runtime.streaming import StreamingService
        
        service = StreamingService()
        
        request_messages = [{"role": "user", "content": "Third question"}]
        
        messages = await service.build_initial_messages(
            request_messages=request_messages,
            conversation_id="conv-001",
            conversation_service=mock_conversation_service
        )
        
        # Verify order: history first, then new message
        assert messages[0]["content"] == "Hello"  # First history
        assert messages[1]["content"] == "Hi there"  # Second history
        assert messages[2]["content"] == "Third question"  # New message


class TestStreamingServiceCheckInterrupt:
    """Test check_interrupt method"""

    @pytest.fixture
    def mock_chunk_builder(self):
        """Mock ChunkBuilder"""
        mock = MagicMock()
        mock.build_stop_chunk = MagicMock(return_value=ChatCompletionChunk(
            id="chatcmpl-test",
            model="gpt-4",
            choices=[ChatCompletionChunkChoice(
                delta=ChatCompletionChunkDelta(),
                finish_reason="stop"
            )]
        ))
        return mock

    @pytest.mark.asyncio
    async def test_check_interrupt_returns_none_when_not_cancelled(self, mock_chunk_builder):
        """Test that check_interrupt returns None when cancel_event is not set"""
        from services.runtime.streaming import StreamingService
        
        service = StreamingService()
        service.chunk_builder = mock_chunk_builder
        
        cancel_event = asyncio.Event()
        
        result = await service.check_interrupt(
            cancel_event=cancel_event,
            chatcmpl_id="chatcmpl-test",
            execution_id="exec-001"
        )
        
        # Verify returns None (not cancelled)
        assert result is None

    @pytest.mark.asyncio
    async def test_check_interrupt_returns_stop_chunk_when_cancelled(self, mock_chunk_builder):
        """Test that check_interrupt returns stop chunk when cancel_event is set"""
        from services.runtime.streaming import StreamingService
        
        service = StreamingService()
        service.chunk_builder = mock_chunk_builder
        
        cancel_event = asyncio.Event()
        cancel_event.set()  # Simulate cancellation
        
        result = await service.check_interrupt(
            cancel_event=cancel_event,
            chatcmpl_id="chatcmpl-abc123",
            execution_id="exec-002"
        )
        
        # Verify returns stop chunk
        assert result is not None
        assert isinstance(result, ChatCompletionChunk)
        assert result.choices[0].finish_reason == "stop"

    @pytest.mark.asyncio
    async def test_check_interrupt_calls_build_stop_chunk(self, mock_chunk_builder):
        """Test that check_interrupt calls ChunkBuilder.build_stop_chunk"""
        from services.runtime.streaming import StreamingService
        
        service = StreamingService()
        service.chunk_builder = mock_chunk_builder
        
        cancel_event = asyncio.Event()
        cancel_event.set()
        
        await service.check_interrupt(
            cancel_event=cancel_event,
            chatcmpl_id="chatcmpl-test",
            execution_id="exec-003"
        )
        
        # Verify build_stop_chunk was called
        assert mock_chunk_builder.build_stop_chunk.called


class TestStreamingServiceIntegration:
    """Integration tests for StreamingService"""

    @pytest.mark.asyncio
    async def test_streaming_service_has_chunk_builder(self):
        """Test that StreamingService has ChunkBuilder instance"""
        from services.runtime.streaming import StreamingService
        from agent.core.chunk_builder import ChunkBuilder
        
        service = StreamingService()
        
        # Verify chunk_builder exists and is correct type
        assert hasattr(service, "chunk_builder")
        assert isinstance(service.chunk_builder, ChunkBuilder)

    @pytest.mark.asyncio
    async def test_chatcmpl_id_format(self):
        """Test that chatcmpl_id follows OpenAI format"""
        from services.runtime.streaming import StreamingService
        
        service = StreamingService()
        
        # Create multiple contexts to verify ID uniqueness
        context1 = service.create_stream_context("exec-1", "agent-1", None)
        context2 = service.create_stream_context("exec-2", "agent-2", None)
        
        # Verify format: chatcmpl-{hex}
        assert context1["chatcmpl_id"].startswith("chatcmpl-")
        assert context2["chatcmpl_id"].startswith("chatcmpl-")
        
        # Verify uniqueness
        assert context1["chatcmpl_id"] != context2["chatcmpl_id"]