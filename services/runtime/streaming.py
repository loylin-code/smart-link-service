"""
StreamingService - Streaming execution helper service

Provides stream context management and error handling for OpenAI-compatible
streaming interface:
- Creates stream context (execution_id, agent_id, chatcmpl_id, cancel_event)
- Handles stream errors and returns error chunks
- Finalizes execution records in database
- Builds initial messages with conversation history
- Checks interrupt signals and returns stop chunks
"""
import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.core.chunk_builder import ChunkBuilder
from models.execution import Execution, ExecutionStatus
from schemas.openai_compat import ChatCompletionChunk
from services.conversation_service import ConversationService


class StreamingService:
    """
    Streaming execution helper service
    
    Manages stream context and provides helper methods for:
    - Creating stream context dict for tracking execution state
    - Handling stream errors by returning error chunks
    - Finalizing execution records in database with status/tokens
    - Building initial messages with conversation history
    - Checking interrupt signals for cancellation
    """
    
    chunk_builder: ChunkBuilder
    
    def __init__(self):
        """Initialize StreamingService with ChunkBuilder"""
        self.chunk_builder = ChunkBuilder()
    
    def create_stream_context(
        self,
        execution_id: str,
        agent_id: str,
        conversation_id: str | None = None
    ) -> dict[str, asyncio.Event | str | datetime | None]:
        """
        Create stream execution context
        
        Args:
            execution_id: Execution ID for tracking
            agent_id: Agent ID being executed
            conversation_id: Optional conversation ID for multi-turn
            
        Returns:
            Dict with:
                - execution_id: str
                - agent_id: str
                - conversation_id: str | None
                - chatcmpl_id: str (OpenAI format: chatcmpl-{hex})
                - cancel_event: asyncio.Event
                - created_at: datetime
        """
        return {
            "execution_id": execution_id,
            "agent_id": agent_id,
            "conversation_id": conversation_id,
            "chatcmpl_id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
            "cancel_event": asyncio.Event(),
            "created_at": datetime.now(timezone.utc),
        }
    
    async def handle_stream_error(
        self,
        execution_id: str,  # noqa: ARG001 - for logging context
        error: Exception,
        chatcmpl_id: str
    ) -> ChatCompletionChunk:
        """
        Handle stream error and return error chunk
        
        Args:
            execution_id: Execution ID (for logging)
            error: Exception that occurred
            chatcmpl_id: Chat completion ID for chunk
            
        Returns:
            ChatCompletionChunk with error indication (finish_reason="content_filter")
        """
        # Use ChunkBuilder to build error chunk
        return self.chunk_builder.build_error_chunk(
            chatcmpl_id=chatcmpl_id,
            model="gpt-4",  # Default model for error chunks
            error_message=str(error)
        )
    
    async def finalize_execution(
        self,
        execution_id: str,
        status: str,
        tokens: dict[str, int],
        db: AsyncSession
    ) -> None:
        """
        Finalize execution record in database
        
        Args:
            execution_id: Execution ID to update
            status: Final status ("completed" | "failed" | "cancelled")
            tokens: Token usage dict {"prompt": int, "completion": int}
            db: Database session
        """
        # Query execution from database
        query = select(Execution).where(Execution.id == execution_id)
        result = await db.execute(query)
        execution = result.scalar_one_or_none()
        
        if execution is None:
            return  # Execution not found, nothing to update
        
        # Update status
        status_mapping: dict[str, ExecutionStatus] = {
            "completed": ExecutionStatus.COMPLETED,
            "failed": ExecutionStatus.FAILED,
            "cancelled": ExecutionStatus.CANCELLED,
        }
        execution.status = status_mapping.get(status, ExecutionStatus.COMPLETED)
        
        # Update tokens
        execution.prompt_tokens = tokens.get("prompt", 0)
        execution.completion_tokens = tokens.get("completion", 0)
        
        # Update timestamp
        execution.completed_at = datetime.now(timezone.utc)
        
        # Commit changes
        await db.commit()
    
    async def build_initial_messages(
        self,
        request_messages: list[dict[str, str]],
        conversation_id: str | None,
        conversation_service: ConversationService | None
    ) -> list[dict[str, str]]:
        """
        Build initial message list with conversation history
        
        Args:
            request_messages: New request messages from user
            conversation_id: Optional conversation ID for history
            conversation_service: ConversationService instance
            
        Returns:
            List of messages with history prepended before new messages
        """
        messages: list[dict[str, str]] = []
        
        # If conversation_id provided, prepend history
        if conversation_id and conversation_service:
            history = await conversation_service.get_messages_for_llm(conversation_id)
            messages.extend(history)
        
        # Append new request messages
        messages.extend(request_messages)
        
        return messages
    
    async def check_interrupt(
        self,
        cancel_event: asyncio.Event,
        chatcmpl_id: str,
        execution_id: str  # noqa: ARG001 - for logging context
    ) -> ChatCompletionChunk | None:
        """
        Check interrupt signal and return stop chunk if cancelled
        
        Args:
            cancel_event: asyncio.Event for cancellation signal
            chatcmpl_id: Chat completion ID for chunk
            execution_id: Execution ID (for logging context)
            
        Returns:
            ChatCompletionChunk with stop finish_reason if cancelled, None otherwise
        """
        # Check if cancel event is set
        if cancel_event.is_set():
            return self.chunk_builder.build_stop_chunk(
                chatcmpl_id=chatcmpl_id,
                model="gpt-4"  # Default model for stop chunks
            )
        
        return None


__all__ = ["StreamingService"]