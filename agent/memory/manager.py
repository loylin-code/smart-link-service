"""
Memory system for agents
Short-term (Redis) and long-term (PostgreSQL) memory
"""
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import redis.asyncio as redis
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from models import Conversation, Message


class MemoryItem(BaseModel):
    """Single memory item"""
    id: str
    role: str
    content: str
    timestamp: datetime
    importance: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ShortTermMemory:
    """
    Short-term memory using Redis
    For recent conversation context and temporary state
    """
    
    KEY_PREFIX = "memory:short"
    TTL = 3600  # 1 hour
    
    def __init__(self, redis_client: redis.Redis = None):
        self.redis = redis_client
    
    async def connect(self):
        """Initialize Redis connection"""
        if not self.redis:
            self.redis = await redis.Redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True
            )
    
    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Dict[str, Any] = None
    ):
        """Add message to short-term memory"""
        key = self._conversation_key(conversation_id)
        
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        
        # Add to list (LPUSH for newest first)
        await self.redis.lpush(key, json.dumps(message))
        # Trim to keep only last N messages
        await self.redis.ltrim(key, 0, 99)  # Keep 100 messages
        # Set TTL
        await self.redis.expire(key, self.TTL)
    
    async def get_messages(
        self,
        conversation_id: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get recent messages"""
        key = self._conversation_key(conversation_id)
        
        messages = await self.redis.lrange(key, 0, limit - 1)
        
        result = []
        for msg_json in messages:
            try:
                msg = json.loads(msg_json)
                result.append(msg)
            except:
                continue
        
        # Reverse to get chronological order
        result.reverse()
        return result
    
    async def get_context_window(
        self,
        conversation_id: str,
        max_tokens: int = 4096
    ) -> List[Dict[str, str]]:
        """
        Get messages fitting within token limit
        Simple estimation: ~4 chars per token
        """
        messages = await self.get_messages(conversation_id, limit=100)
        
        result = []
        total_tokens = 0
        
        for msg in messages:
            content = msg.get("content", "")
            estimated_tokens = len(content) // 4
            
            if total_tokens + estimated_tokens > max_tokens:
                break
            
            result.append({
                "role": msg.get("role"),
                "content": content
            })
            total_tokens += estimated_tokens
        
        return result
    
    async def clear(self, conversation_id: str):
        """Clear short-term memory"""
        key = self._conversation_key(conversation_id)
        await self.redis.delete(key)
    
    async def set_state(
        self,
        conversation_id: str,
        state: Dict[str, Any]
    ):
        """Set conversation state"""
        key = self._state_key(conversation_id)
        await self.redis.setex(key, self.TTL, json.dumps(state))
    
    async def get_state(
        self,
        conversation_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get conversation state"""
        key = self._state_key(conversation_id)
        data = await self.redis.get(key)
        
        if data:
            return json.loads(data)
        return None
    
    def _conversation_key(self, conversation_id: str) -> str:
        return f"{self.KEY_PREFIX}:conv:{conversation_id}"
    
    def _state_key(self, conversation_id: str) -> str:
        return f"{self.KEY_PREFIX}:state:{conversation_id}"


class LongTermMemory:
    """
    Long-term memory using PostgreSQL
    For persistent conversation history and searchable memory
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_conversation_history(
        self,
        conversation_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Message]:
        """Get conversation messages from database"""
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        return result.scalars().all()
    
    async def get_user_conversations(
        self,
        user_id: str,
        tenant_id: str,
        limit: int = 20
    ) -> List[Conversation]:
        """Get user's conversations"""
        result = await self.db.execute(
            select(Conversation)
            .where(
                Conversation.user_id == user_id,
                Conversation.tenant_id == tenant_id,
                Conversation.is_archived == False
            )
            .order_by(Conversation.last_activity.desc())
            .limit(limit)
        )
        return result.scalars().all()
    
    async def search_messages(
        self,
        tenant_id: str,
        query: str,
        conversation_id: str = None,
        limit: int = 10
    ) -> List[Message]:
        """
        Search messages by content
        Uses PostgreSQL full-text search
        """
        # Build query
        sql_query = select(Message).where(
            Message.tenant_id == tenant_id
        )
        
        if conversation_id:
            sql_query = sql_query.where(
                Message.conversation_id == conversation_id
            )
        
        # Simple LIKE search (could use pg_trgm or full-text)
        # For production, use proper full-text search
        sql_query = sql_query.where(
            Message.content["text"].astext.ilike(f"%{query}%")
        ).limit(limit)
        
        result = await self.db.execute(sql_query)
        return result.scalars().all()
    
    async def summarize_conversation(
        self,
        conversation_id: str
    ) -> str:
        """
        Generate conversation summary
        Used for context compression
        """
        messages = await self.get_conversation_history(conversation_id)
        
        if not messages:
            return ""
        
        # Simple summary: first and last messages
        # In production, use LLM for summarization
        first_msg = messages[0]
        last_msg = messages[-1]
        
        return f"Conversation started with: {first_msg.content.get('text', '')[:100]}... Last message: {last_msg.content.get('text', '')[:100]}"


class MemoryManager:
    """
    Unified memory manager combining short-term and long-term memory
    """
    
    def __init__(self, db: AsyncSession, redis_client: redis.Redis = None):
        self.short_term = ShortTermMemory(redis_client)
        self.long_term = LongTermMemory(db)
    
    async def get_context_for_llm(
        self,
        conversation_id: str,
        max_tokens: int = 4096,
        include_summary: bool = True
    ) -> List[Dict[str, str]]:
        """
        Get conversation context for LLM
        
        Combines:
        1. Short-term memory (recent messages from Redis)
        2. Long-term memory (historical messages from DB)
        3. Conversation summary (if context is too long)
        """
        # First try short-term memory
        short_term_messages = await self.short_term.get_context_window(
            conversation_id,
            max_tokens=max_tokens
        )
        
        if len(short_term_messages) >= 10:
            # We have enough from short-term
            return short_term_messages
        
        # Need to fetch from long-term
        long_term_messages = await self.long_term.get_conversation_history(
            conversation_id
        )
        
        # Convert to LLM format
        messages = []
        for msg in long_term_messages:
            content = msg.content.get("text", "")
            if content:
                messages.append({
                    "role": msg.role,
                    "content": content
                })
        
        # If too many messages, include summary
        if include_summary and len(messages) > 20:
            summary = await self.long_term.summarize_conversation(conversation_id)
            # Add summary as system message
            messages = [
                {"role": "system", "content": f"Conversation summary: {summary}"}
            ] + messages[-20:]  # Keep last 20 messages
        
        return messages
    
    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Dict[str, Any] = None
    ):
        """Add message to both memories"""
        await self.short_term.add_message(
            conversation_id,
            role,
            content,
            metadata
        )
        # Long-term storage is handled by conversation service
    
    async def clear_session(self, conversation_id: str):
        """Clear session memory"""
        await self.short_term.clear(conversation_id)