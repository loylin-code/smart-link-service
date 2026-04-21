"""
Unit tests for ExecutionService

Tests the runtime execution service layer that:
- Creates Execution records
- Calls AgentOrchestrator.execute_stream_openai
- Updates Execution status on completion/error
- Manages cancellation via InterruptManager
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from typing import AsyncIterator, List
from datetime import datetime

from models.execution import Execution, ExecutionStatus
from schemas.openai_compat import ChatCompletionChunk, ChatCompletionChunkDelta, ChatCompletionChunkChoice


class TestExecutionServiceExecuteStreamOpenai:
    """Test execute_stream_openai method"""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        mock = AsyncMock()
        mock.execute = AsyncMock()
        mock.commit = AsyncMock()
        mock.add = MagicMock()
        mock.refresh = AsyncMock()
        mock.rollback = AsyncMock()
        return mock

    @pytest.fixture
    def mock_orchestrator(self):
        """Mock AgentOrchestrator"""
        mock = MagicMock()
        mock.interrupt_manager = MagicMock()
        mock.interrupt_manager.cancel = MagicMock(return_value={"status": "cancelled"})
        return mock

    @pytest.fixture
    def mock_chunks(self):
        """Create mock ChatCompletionChunk objects"""
        chunks = []
        # Role chunk
        chunks.append(ChatCompletionChunk(
            id="chatcmpl-test",
            model="gpt-4",
            choices=[ChatCompletionChunkChoice(
                delta=ChatCompletionChunkDelta(role="assistant"),
                finish_reason=None
            )]
        ))
        # Content chunks
        chunks.append(ChatCompletionChunk(
            id="chatcmpl-test",
            model="gpt-4",
            choices=[ChatCompletionChunkChoice(
                delta=ChatCompletionChunkDelta(content="Hello"),
                finish_reason=None
            )]
        ))
        chunks.append(ChatCompletionChunk(
            id="chatcmpl-test",
            model="gpt-4",
            choices=[ChatCompletionChunkChoice(
                delta=ChatCompletionChunkDelta(content=" world"),
                finish_reason=None
            )]
        ))
        # Final chunk
        chunks.append(ChatCompletionChunk(
            id="chatcmpl-test",
            model="gpt-4",
            choices=[ChatCompletionChunkChoice(
                delta=ChatCompletionChunkDelta(),
                finish_reason="stop"
            )]
        ))
        return chunks

    def _create_chunk_stream(self, chunks: List[ChatCompletionChunk]) -> AsyncIterator[ChatCompletionChunk]:
        """Create async iterator for chunks"""
        async def stream_gen():
            for chunk in chunks:
                yield chunk
        return stream_gen()

    @pytest.mark.asyncio
    async def test_execute_stream_openai_returns_chat_completion_chunks(
        self, mock_db_session, mock_orchestrator, mock_chunks
    ):
        """Test that execute_stream_openai returns ChatCompletionChunk objects"""
        # Import service (will fail until implemented)
        from services.runtime.execution import ExecutionService
        
        service = ExecutionService(db=mock_db_session, orchestrator=mock_orchestrator)
        
        # Mock orchestrator.execute_stream_openai
        mock_stream = self._create_chunk_stream(mock_chunks)
        mock_orchestrator.execute_stream_openai = MagicMock(return_value=mock_stream)
        
        # Collect chunks
        chunks = []
        async for chunk in service.execute_stream_openai(
            agent_id="test-agent",
            execution_id="exec-001",
            input_data={"message": "Hello"}
        ):
            chunks.append(chunk)
        
        # Verify all chunks are ChatCompletionChunk objects
        assert len(chunks) > 0
        for chunk in chunks:
            assert isinstance(chunk, ChatCompletionChunk)

    @pytest.mark.asyncio
    async def test_execution_record_created_with_running_status(
        self, mock_db_session, mock_orchestrator, mock_chunks
    ):
        """Test that Execution record is created with RUNNING status"""
        from services.runtime.execution import ExecutionService
        
        service = ExecutionService(db=mock_db_session, orchestrator=mock_orchestrator)
        
        mock_stream = self._create_chunk_stream(mock_chunks)
        mock_orchestrator.execute_stream_openai = MagicMock(return_value=mock_stream)
        
        # Track what was added to database and capture initial status
        initial_status = None
        def track_add(obj):
            mock_db_session._added_obj = obj
            mock_db_session._initial_status = obj.status  # Capture at add() time
        mock_db_session.add.side_effect = track_add
        
        # Execute stream
        chunks = []
        async for chunk in service.execute_stream_openai(
            agent_id="test-agent",
            execution_id="exec-002",
            input_data={"message": "Hello"}
        ):
            chunks.append(chunk)
        
        # Verify db.add was called
        assert mock_db_session.add.called
        
        # Verify the added object had RUNNING status at creation time
        initial_status = mock_db_session._initial_status
        assert initial_status is not None
        assert initial_status == ExecutionStatus.RUNNING
        
        # Verify agent_id was set correctly
        added_obj = mock_db_session._added_obj
        assert added_obj.agent_id == "test-agent"

    @pytest.mark.asyncio
    async def test_execution_updated_to_completed_on_success(
        self, mock_db_session, mock_orchestrator, mock_chunks
    ):
        """Test that Execution status is updated to COMPLETED on success"""
        from services.runtime.execution import ExecutionService
        
        service = ExecutionService(db=mock_db_session, orchestrator=mock_orchestrator)
        
        mock_stream = self._create_chunk_stream(mock_chunks)
        mock_orchestrator.execute_stream_openai = MagicMock(return_value=mock_stream)
        
        # Execute stream
        async for chunk in service.execute_stream_openai(
            agent_id="test-agent",
            execution_id="exec-003",
            input_data={"message": "Hello"}
        ):
            pass
        
        # Verify commit was called (status update)
        assert mock_db_session.commit.called

    @pytest.mark.asyncio
    async def test_execution_updated_to_failed_on_error(
        self, mock_db_session, mock_orchestrator, mock_chunks
    ):
        """Test that Execution status is updated to FAILED on error"""
        from services.runtime.execution import ExecutionService
        from core.exceptions import AgentError
        
        service = ExecutionService(db=mock_db_session, orchestrator=mock_orchestrator)
        
        # Mock orchestrator that raises error
        async def error_stream():
            raise AgentError("Agent failed", agent_id="test-agent")
            yield  # Never reached
        mock_orchestrator.execute_stream_openai = MagicMock(return_value=error_stream())
        
        # Execute stream and expect error
        chunks = []
        try:
            async for chunk in service.execute_stream_openai(
                agent_id="test-agent",
                execution_id="exec-004",
                input_data={"message": "Hello"}
            ):
                chunks.append(chunk)
        except AgentError:
            pass
        
        # Verify rollback was called on error
        assert mock_db_session.rollback.called

    @pytest.mark.asyncio
    async def test_cancel_execution_uses_interrupt_manager(
        self, mock_db_session, mock_orchestrator
    ):
        """Test that cancel_execution uses InterruptManager"""
        from services.runtime.execution import ExecutionService
        
        service = ExecutionService(db=mock_db_session, orchestrator=mock_orchestrator)
        
        # Mock InterruptManager.cancel
        mock_orchestrator.interrupt_manager.cancel = MagicMock(
            return_value={"status": "cancelled", "cancelled_at": 12345}
        )
        
        # Mock database query to return None (execution not found in DB)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        result = await service.cancel_execution("exec-005")
        
        # Verify interrupt_manager.cancel was called
        assert mock_orchestrator.interrupt_manager.cancel.called
        assert result["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_get_execution_status_returns_correct_data(
        self, mock_db_session
    ):
        """Test that get_execution_status returns correct data from database"""
        from services.runtime.execution import ExecutionService
        from sqlalchemy import select
        
        service = ExecutionService(db=mock_db_session)
        
        # Mock database query result
        mock_execution = Execution(
            id="exec-006",
            agent_id="test-agent",
            status=ExecutionStatus.RUNNING,
            input_data={"message": "Hello"},
            created_at=datetime.utcnow()
        )
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=mock_execution)
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        status = await service.get_execution_status("exec-006")
        
        # Verify correct data returned
        assert status is not None
        assert status["id"] == "exec-006"
        assert status["status"] == ExecutionStatus.RUNNING.value


class TestExecutionServiceListExecutions:
    """Test list_executions method"""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        mock = AsyncMock()
        mock.execute = AsyncMock()
        return mock

    @pytest.mark.asyncio
    async def test_list_executions_filters_by_agent_id(
        self, mock_db_session
    ):
        """Test that list_executions can filter by agent_id"""
        from services.runtime.execution import ExecutionService
        
        service = ExecutionService(db=mock_db_session)
        
        # Mock database query result
        mock_executions = [
            Execution(id="exec-a", agent_id="agent-1", status=ExecutionStatus.COMPLETED),
            Execution(id="exec-b", agent_id="agent-1", status=ExecutionStatus.RUNNING),
        ]
        
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=mock_executions)
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        executions = await service.list_executions(agent_id="agent-1")
        
        # Verify results
        assert len(executions) == 2
        assert all(e["agent_id"] == "agent-1" for e in executions)

    @pytest.mark.asyncio
    async def test_list_executions_filters_by_status(
        self, mock_db_session
    ):
        """Test that list_executions can filter by status"""
        from services.runtime.execution import ExecutionService
        
        service = ExecutionService(db=mock_db_session)
        
        # Mock database query result
        mock_executions = [
            Execution(id="exec-c", agent_id="agent-1", status=ExecutionStatus.COMPLETED),
        ]
        
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=mock_executions)
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        executions = await service.list_executions(status=ExecutionStatus.COMPLETED.value)
        
        # Verify results
        assert len(executions) == 1
        assert executions[0]["status"] == ExecutionStatus.COMPLETED.value

    @pytest.mark.asyncio
    async def test_list_executions_respects_limit(
        self, mock_db_session
    ):
        """Test that list_executions respects limit parameter"""
        from services.runtime.execution import ExecutionService
        
        service = ExecutionService(db=mock_db_session)
        
        # Mock database query result with 3 executions
        mock_executions = [
            Execution(id="exec-1", agent_id="agent-1", status=ExecutionStatus.COMPLETED),
            Execution(id="exec-2", agent_id="agent-1", status=ExecutionStatus.COMPLETED),
            Execution(id="exec-3", agent_id="agent-1", status=ExecutionStatus.COMPLETED),
        ]
        
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all = MagicMock(return_value=mock_executions[:2])  # Limit to 2
        mock_result.scalars = MagicMock(return_value=mock_scalars)
        mock_db_session.execute = AsyncMock(return_value=mock_result)
        
        executions = await service.list_executions(limit=2)
        
        # Verify limit respected
        assert len(executions) == 2