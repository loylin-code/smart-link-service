"""
SessionMemory adapter for AgentScope AsyncSQLAlchemyMemory
Wraps AgentScope's memory for conversation session persistence
"""
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from agentscope.memory import AsyncSQLAlchemyMemory
from agentscope.message import Msg


class SessionMemory:
    """
    Session memory adapter using AgentScope's AsyncSQLAlchemyMemory
    
    Provides conversation session persistence for a specific user and session
    """
    
    def __init__(
        self,
        db_session: AsyncSession,
        user_id: str,
        session_id: str
    ):
        """
        Initialize SessionMemory
        
        Args:
            db_session: Async SQLAlchemy session
            user_id: User identifier
            session_id: Session identifier
        """
        self._user_id = user_id
        self._session_id = session_id
        self._memory = AsyncSQLAlchemyMemory(
            db_session=db_session,
            user_id=user_id,
            session_id=session_id
        )
    
    async def add_message(
        self,
        role: str,
        content: str,
        name: Optional[str] = None
    ) -> None:
        """
        Add a message to session memory
        
        Args:
            role: Message role (user, assistant, system)
            content: Message content
            name: Optional message name/identifier
        """
        msg = Msg(role=role, content=content, name=name)
        await self._memory.add(msg)
    
    async def get_context(self) -> List[Msg]:
        """
        Get conversation context (message history)
        
        Returns:
            List of Msg objects representing conversation history
        """
        return await self._memory.get_history()
    
    async def get_message_count(self) -> int:
        """
        Get number of messages in session
        
        Returns:
            Number of messages stored
        """
        return self._memory.size
    
    async def clear_session(self) -> None:
        """
        Clear all messages from session memory
        """
        await self._memory.clear()
