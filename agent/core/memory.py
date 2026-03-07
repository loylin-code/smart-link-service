"""
Memory system for agents
Short-term (Redis) and long-term (PostgreSQL) memory
"""
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings


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
    
    async def add_message(self, conversation_id: str, role: str, content: str, metadata: Dict = None):
        """Add message to short-term memory"""
        key = f"{self.KEY_PREFIX}:conv:{conversation_id}"
        message = {"role": role, "content": content, "timestamp": datetime.utcnow().isoformat(), "metadata": metadata or {}}
        await self.redis.lpush(key, json.dumps(message))
        await self.redis.ltrim(key, 0, 99)
        await self.redis.expire(key, self.TTL)
    
    async def get_messages(self, conversation_id: str, limit: int = 20) -> List[Dict]:
        """Get recent messages"""
        key = f"{self.KEY_PREFIX}:conv:{conversation_id}"
        messages = await self.redis.lrange(key, 0, limit - 1)
        result = [json.loads(m) for m in messages]
        result.reverse()
        return result
    
    async def get_context_window(self, conversation_id: str, max_tokens: int = 4096) -> List[Dict[str, str]]:
        """Get messages fitting within token limit"""
        messages = await self.get_messages(conversation_id, limit=100)
        result, total_tokens = [], 0
        for msg in messages:
            estimated_tokens = len(msg.get("content", "")) // 4
            if total_tokens + estimated_tokens > max_tokens:
                break
            result.append({"role": msg.get("role"), "content": msg.get("content")})
            total_tokens += estimated_tokens
        return result
    
    async def set_state(self, conversation_id: str, state: Dict):
        """Set conversation state"""
        key = f"{self.KEY_PREFIX}:state:{conversation_id}"
        await self.redis.setex(key, self.TTL, json.dumps(state))
    
    async def get_state(self, conversation_id: str) -> Optional[Dict]:
        """Get conversation state"""
        key = f"{self.KEY_PREFIX}:state:{conversation_id}"
        data = await self.redis.get(key)
        return json.loads(data) if data else None
    
    async def clear(self, conversation_id: str):
        """Clear short-term memory"""
        await self.redis.delete(f"{self.KEY_PREFIX}:conv:{conversation_id}")
        await self.redis.delete(f"{self.KEY_PREFIX}:state:{conversation_id}")


class LongTermMemory:
    """
    Long-term memory using PostgreSQL
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_conversation_history(self, conversation_id: str, limit: int = 100) -> List[Dict]:
        """Get conversation messages from database"""
        from models import Message
        result = await self.db.execute(
            select(Message).where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc()).limit(limit)
        )
        messages = result.scalars().all()
        return [{"role": m.role, "content": m.content.get("text", ""), "timestamp": m.created_at} for m in messages]
    
    async def search_messages(self, tenant_id: str, query: str, limit: int = 10) -> List[Dict]:
        """Search messages by content"""
        from models import Message
        result = await self.db.execute(
            select(Message).where(Message.tenant_id == tenant_id)
            .where(Message.content["text"].astext.ilike(f"%{query}%"))
            .limit(limit)
        )
        return [{"id": m.id, "content": m.content.get("text", ""), "conversation_id": m.conversation_id} for m in result.scalars().all()]


class MemoryManager:
    """
    Unified memory manager combining short-term and long-term memory
    """
    
    def __init__(self, db: AsyncSession, redis_client: redis.Redis = None):
        self.short_term = ShortTermMemory(redis_client)
        self.long_term = LongTermMemory(db)
    
    async def get_context_for_llm(self, conversation_id: str, max_tokens: int = 4096) -> List[Dict[str, str]]:
        """Get conversation context for LLM"""
        # Try short-term first
        messages = await self.short_term.get_context_window(conversation_id, max_tokens)
        if len(messages) >= 10:
            return messages
        # Fall back to long-term
        return await self.long_term.get_conversation_history(conversation_id)
    
    async def add_message(self, conversation_id: str, role: str, content: str):
        """Add message to short-term memory"""
        await self.short_term.add_message(conversation_id, role, content)
    
    async def clear_session(self, conversation_id: str):
        """Clear session memory"""
        await self.short_term.clear(conversation_id)