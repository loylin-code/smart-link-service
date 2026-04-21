"""
Execution Service - Runtime execution management

Provides execution management for agent streaming interface:
- Creates Execution records
- Calls AgentOrchestrator.execute_stream_openai
- Updates Execution status on completion/error
- Manages cancellation via InterruptManager
"""
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.core.orchestrator import AgentOrchestrator
from models.execution import Execution, ExecutionStatus
from schemas.openai_compat import ChatCompletionChunk


class ExecutionService:
    """
    Runtime execution service
    
    Manages agent execution lifecycle:
    - Creates Execution records with RUNNING status
    - Orchestrates streaming via AgentOrchestrator
    - Updates Execution status on completion/error
    - Handles cancellation via InterruptManager
    """
    
    def __init__(
        self,
        db: AsyncSession,
        orchestrator: Optional[AgentOrchestrator] = None
    ):
        """
        Initialize ExecutionService
        
        Args:
            db: Database session for Execution CRUD
            orchestrator: AgentOrchestrator instance (optional, creates default if None)
        """
        self.db = db
        self.orchestrator = orchestrator or AgentOrchestrator()
    
    async def execute_stream_openai(
        self,
        agent_id: str,
        execution_id: str,
        input_data: Dict[str, Any],
        include_usage: bool = False,
        conversation_id: Optional[str] = None
    ) -> AsyncIterator[ChatCompletionChunk]:
        """
        Execute Agent and return OpenAI format streaming chunks
        
        Creates Execution record with RUNNING status, streams from orchestrator,
        and updates Execution status on completion or error.
        
        Args:
            agent_id: Agent ID to execute
            execution_id: Execution ID for tracking
            input_data: Input data containing message and optional parameters
            include_usage: Whether to include usage statistics
            conversation_id: Optional conversation ID for context
            
        Yields:
            ChatCompletionChunk objects in OpenAI format
            
        Raises:
            AgentError: If agent not found or execution fails
            LLMError: If LLM streaming fails
        """
        # Create Execution record with RUNNING status
        execution = Execution(
            id=execution_id,
            agent_id=agent_id,
            conversation_id=conversation_id,
            status=ExecutionStatus.RUNNING,
            input_data=input_data,
            started_at=datetime.now(timezone.utc)
        )
        self.db.add(execution)
        self._added_obj = execution  # Track for test verification
        await self.db.commit()
        await self.db.refresh(execution)
        
        try:
            # Stream from orchestrator
            async for chunk in self.orchestrator.execute_stream_openai(
                agent_id=agent_id,
                execution_id=execution_id,
                input_data=input_data,
                include_usage=include_usage
            ):
                yield chunk
            
            # Update Execution to COMPLETED
            execution.status = ExecutionStatus.COMPLETED
            execution.completed_at = datetime.now(timezone.utc)
            await self.db.commit()
            
        except Exception as e:
            # Update Execution to FAILED
            execution.status = ExecutionStatus.FAILED
            execution.completed_at = datetime.now(timezone.utc)
            execution.error_message = str(e)
            await self.db.rollback()
            await self.db.commit()
            raise
    
    async def cancel_execution(self, execution_id: str) -> Dict[str, Any]:
        """
        Cancel execution via InterruptManager
        
        Args:
            execution_id: Execution ID to cancel
            
        Returns:
            Cancel result from InterruptManager
        """
        # Cancel via orchestrator's InterruptManager
        result = self.orchestrator.interrupt_manager.cancel(execution_id)
        
        # Update Execution status if exists in database
        execution = await self._get_execution_by_id(execution_id)
        if execution is not None and execution.status == ExecutionStatus.RUNNING:
            execution.status = ExecutionStatus.CANCELLED
            execution.completed_at = datetime.now(timezone.utc)
            await self.db.commit()
        
        return result
    
    async def get_execution_status(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """
        Get execution status from database
        
        Args:
            execution_id: Execution ID
            
        Returns:
            Execution status dict or None if not found
        """
        execution = await self._get_execution_by_id(execution_id)
        if not execution:
            return None
        
        return {
            "id": execution.id,
            "agent_id": execution.agent_id,
            "conversation_id": execution.conversation_id,
            "status": execution.status.value,
            "input_data": execution.input_data,
            "output_data": execution.output_data,
            "prompt_tokens": execution.prompt_tokens,
            "completion_tokens": execution.completion_tokens,
            "total_tokens": execution.total_tokens,
            "created_at": execution.created_at,
            "started_at": execution.started_at,
            "completed_at": execution.completed_at,
            "error_message": execution.error_message,
            "error_code": execution.error_code,
        }
    
    async def list_executions(
        self,
        agent_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        List execution history with filters
        
        Args:
            agent_id: Filter by agent ID
            status: Filter by status value
            limit: Maximum number of results
            
        Returns:
            List of execution dicts
        """
        query = select(Execution)
        
        if agent_id:
            query = query.where(Execution.agent_id == agent_id)
        
        if status:
            status_enum = ExecutionStatus(status)
            query = query.where(Execution.status == status_enum)
        
        query = query.order_by(Execution.created_at.desc()).limit(limit)
        
        result = await self.db.execute(query)
        executions = result.scalars().all()
        
        return [
            {
                "id": e.id,
                "agent_id": e.agent_id,
                "conversation_id": e.conversation_id,
                "status": e.status.value,
                "created_at": e.created_at,
                "completed_at": e.completed_at,
            }
            for e in executions
        ]
    
    async def _get_execution_by_id(self, execution_id: str) -> Optional[Execution]:
        """
        Get Execution by ID from database
        
        Args:
            execution_id: Execution ID
            
        Returns:
            Execution object or None
        """
        query = select(Execution).where(Execution.id == execution_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()


__all__ = ["ExecutionService"]