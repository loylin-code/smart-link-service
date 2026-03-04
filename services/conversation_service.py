"""
Conversation service layer
"""
from typing import List, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from models.application import Conversation, Message
from core.exceptions import NotFoundError


class ConversationService:
    """Service for conversation and message management"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create_conversation(
        self,
        title: str,
        app_id: str,
        user_id: Optional[str] = None
    ) -> Conversation:
        """Create a new conversation"""
        import uuid
        conv_id = f"conv_{uuid.uuid4().hex[:12]}"
        
        conversation = Conversation(
            id=conv_id,
            title=title,
            app_id=app_id,
            user_id=user_id
        )
        
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)
        
        return conversation
    
    async def get_conversation(
        self,
        conversation_id: str,
        include_messages: bool = True
    ) -> Optional[Conversation]:
        """Get conversation by ID"""
        query = select(Conversation).where(Conversation.id == conversation_id)
        
        if include_messages:
            query = query.options(selectinload(Conversation.messages))
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def list_conversations(
        self,
        app_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 20
    ) -> List[Conversation]:
        """List conversations"""
        query = select(Conversation)
        
        if app_id:
            query = query.where(Conversation.app_id == app_id)
        
        if user_id:
            query = query.where(Conversation.user_id == user_id)
        
        query = query.order_by(Conversation.updated_at.desc()).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: dict,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None
    ) -> Message:
        """Add a message to conversation"""
        import uuid
        msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        
        message = Message(
            id=msg_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=(prompt_tokens or 0) + (completion_tokens or 0)
        )
        
        self.db.add(message)
        
        # Update conversation updated_at
        conversation = await self.get_conversation(conversation_id, include_messages=False)
        if conversation:
            conversation.updated_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(message)
        
        return message
    
    async def get_messages(
        self,
        conversation_id: str,
        limit: int = 100
    ) -> List[Message]:
        """Get messages from conversation"""
        query = select(Message).where(
            Message.conversation_id == conversation_id
        ).order_by(Message.created_at.asc()).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete conversation and all its messages"""
        conversation = await self.get_conversation(conversation_id)
        
        if not conversation:
            return False
        
        await self.db.delete(conversation)
        await self.db.commit()
        
        return True