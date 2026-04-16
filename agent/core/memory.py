"""
Memory system for agents
Short-term (Redis) and long-term (PostgreSQL) memory

Enhanced for Agent Intelligence Core:
- Importance marking (0-5)
- SubAgent context isolation
- Summary support
- MemoryContext for PlanAgent and SubAgents
"""
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import redis.asyncio as redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings


class MemoryContext(BaseModel):
    """Memory context for PlanAgent and SubAgents"""
    conversation_id: str
    messages: List[Dict[str, str]] = Field(default_factory=list)
    summary: Optional[str] = None
    key_entities: Dict[str, Any] = Field(default_factory=dict)
    user_preferences: Dict[str, Any] = Field(default_factory=dict)  # L3预留
    token_count: int = 0


class ShortTermMemory:
    """
    Short-term memory using Redis
    For recent conversation context and temporary state
    
    Enhanced features:
    - Importance marking (0-5, 5=key, 0=normal)
    - SubAgent context isolation
    - Summary support for long conversations
    """
    
    KEY_PREFIX = "memory:short"
    SUMMARY_PREFIX = "memory:summary"
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
        metadata: Dict = None,
        importance: int = 0
    ):
        """Add message to short-term memory
        
        Args:
            conversation_id: Conversation ID
            role: Message role (user/assistant/system)
            content: Message content
            metadata: Optional metadata
            importance: Importance level (0-5, 5=key, 0=normal)
        """
        key = f"{self.KEY_PREFIX}:conv:{conversation_id}"
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
            "importance": importance
        }
        await self.redis.lpush(key, json.dumps(message))
        await self.redis.ltrim(key, 0, 99)
        await self.redis.expire(key, self.TTL)
    
    async def get_messages(
        self,
        conversation_id: str,
        limit: int = 20,
        filter_importance: Optional[int] = None
    ) -> List[Dict]:
        """Get recent messages
        
        Args:
            conversation_id: Conversation ID
            limit: Maximum messages to return
            filter_importance: Minimum importance level (None = all)
            
        Returns:
            List of messages
        """
        key = f"{self.KEY_PREFIX}:conv:{conversation_id}"
        messages = await self.redis.lrange(key, 0, limit - 1)
        result = [json.loads(m) for m in messages]
        
        # Filter by importance if specified
        if filter_importance is not None:
            result = [m for m in result if m.get("importance", 0) >= filter_importance]
        
        result.reverse()
        return result
    
    async def get_context_for_subagent(
        self,
        conversation_id: str,
        subagent_role: str,
        max_tokens: int = 2000
    ) -> List[Dict[str, str]]:
        """Get context for SubAgent with priority ordering
        
        Priority: High importance > Recent messages
        
        Args:
            conversation_id: Conversation ID
            subagent_role: SubAgent role (research/code/data/doc)
            max_tokens: Maximum tokens
            
        Returns:
            List of messages formatted for LLM
        """
        messages = await self.get_messages(conversation_id, limit=100)
        
        # Sort by importance (descending), then by timestamp (newest first)
        sorted_messages = sorted(
            messages,
            key=lambda m: (-m.get("importance", 0), m.get("timestamp", ""))
        )
        
        result, total_tokens = [], 0
        for msg in sorted_messages:
            estimated_tokens = len(msg.get("content", "")) // 4
            if total_tokens + estimated_tokens > max_tokens:
                break
            result.append({"role": msg.get("role"), "content": msg.get("content")})
            total_tokens += estimated_tokens
        
        # Re-order chronologically for LLM context
        result.reverse()
        return result
    
    async def set_summary(self, conversation_id: str, summary: str):
        """Store conversation summary
        
        Args:
            conversation_id: Conversation ID
            summary: Summary text
        """
        key = f"{self.SUMMARY_PREFIX}:{conversation_id}"
        await self.redis.setex(key, self.TTL * 24, summary)  # 24 hours
    
    async def get_summary(self, conversation_id: str) -> Optional[str]:
        """Get conversation summary
        
        Args:
            conversation_id: Conversation ID
            
        Returns:
            Summary text or None
        """
        key = f"{self.SUMMARY_PREFIX}:{conversation_id}"
        return await self.redis.get(key)
    
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
        await self.redis.delete(f"{self.SUMMARY_PREFIX}:{conversation_id}")


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
    
    Enhanced for Agent Intelligence Core:
    - get_context_for_plan_agent(): Context for intent recognition
    - get_context_for_subagent(): Role-specific context
    - generate_summary_if_needed(): Auto-summary generation
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
    
    async def get_context_for_plan_agent(
        self,
        conversation_id: str,
        max_tokens: int = 4096
    ) -> MemoryContext:
        """Get context for PlanAgent intent recognition
        
        Args:
            conversation_id: Conversation ID
            max_tokens: Maximum tokens
            
        Returns:
            MemoryContext with summary, messages, key entities
        """
        # Get summary
        summary = await self.short_term.get_summary(conversation_id)
        
        # Get messages
        messages = await self.short_term.get_context_window(conversation_id, max_tokens)
        
        # Calculate token count
        token_count = sum(len(m.get("content", "")) // 4 for m in messages)
        
        return MemoryContext(
            conversation_id=conversation_id,
            messages=messages,
            summary=summary,
            key_entities={},  # TODO: Extract entities from messages
            token_count=token_count
        )
    
    async def get_context_for_subagent(
        self,
        conversation_id: str,
        subagent_role: str,
        max_tokens: int = 2000
    ) -> MemoryContext:
        """Get role-specific context for SubAgent
        
        Args:
            conversation_id: Conversation ID
            subagent_role: SubAgent role (research/code/data/doc)
            max_tokens: Maximum tokens
            
        Returns:
            MemoryContext with prioritized messages
        """
        # Get role-specific context
        messages = await self.short_term.get_context_for_subagent(
            conversation_id,
            subagent_role,
            max_tokens
        )
        
        # Get summary for context
        summary = await self.short_term.get_summary(conversation_id)
        
        # Calculate token count
        token_count = sum(len(m.get("content", "")) // 4 for m in messages)
        
        return MemoryContext(
            conversation_id=conversation_id,
            messages=messages,
            summary=summary,
            key_entities={},
            token_count=token_count
        )
    
    async def generate_summary_if_needed(
        self,
        conversation_id: str,
        llm_client: Any = None
    ) -> Optional[str]:
        """Generate summary if conversation exceeds threshold
        
        Args:
            conversation_id: Conversation ID
            llm_client: Optional LLM client for summary generation
            
        Returns:
            Generated summary or None
        """
        # Check message count
        messages = await self.short_term.get_messages(conversation_id, limit=100)
        
        # Auto-summary threshold: 50 messages
        if len(messages) < 50:
            return None
        
        # Check if summary already exists
        existing_summary = await self.short_term.get_summary(conversation_id)
        if existing_summary:
            return existing_summary
        
        # Generate summary using LLM if provided
        if llm_client:
            # Get last 30 messages for summary
            recent_messages = messages[-30:]
            summary_prompt = "请总结以下对话的关键内容:\n" + "\n".join([
                f"{m['role']}: {m['content']}"
                for m in recent_messages
            ])
            
            summary = await llm_client.chat(summary_prompt)
            await self.short_term.set_summary(conversation_id, summary)
            return summary
        
        return None
    
    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        importance: int = 0
    ):
        """Add message to short-term memory
        
        Args:
            conversation_id: Conversation ID
            role: Message role
            content: Message content
            importance: Importance level (0-5)
        """
        await self.short_term.add_message(conversation_id, role, content, importance=importance)
    
    async def clear_session(self, conversation_id: str):
        """Clear session memory"""
        await self.short_term.clear(conversation_id)