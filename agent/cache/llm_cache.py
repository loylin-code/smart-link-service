"""
LLM response cache service with SQLite storage and lazy expiration
"""
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any
from uuid import uuid4

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import cache_session_maker, init_cache_db
from models.cache import LLMCacheEntry
from core.config import settings
from agent.cache.keygen import generate_cache_key

logger = logging.getLogger(__name__)


class LLMCache:
    """
    LLM response cache with SQLite storage and lazy expiration.
    
    Features:
    - SHA-256 cache keys (system_prompt + user_message + model)
    - Lazy expiration on read (delete expired entries)
    - Graceful degradation on cache errors
    - TTL configurable via settings
    """
    
    def __init__(self):
        self.enabled = settings.LLM_CACHE_ENABLED
        self.ttl = settings.LLM_CACHE_TTL
        self._initialized = False
    
    async def initialize(self):
        """Initialize cache database (create table if needed)"""
        if self._initialized:
            return
        
        try:
            await init_cache_db()
            self._initialized = True
            logger.info("LLM cache initialized")
        except Exception as e:
            logger.warning(f"Cache initialization failed: {e}")
            self.enabled = False
    
    async def get(
        self,
        system_prompt: str,
        user_message: str,
        model: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get cached response with lazy expiration.
        
        Args:
            system_prompt: Agent system prompt
            user_message: User input message
            model: LLM model name
        
        Returns:
            Cached response dict if valid, None if expired or not found
        """
        if not self.enabled:
            return None
        
        cache_key = generate_cache_key(system_prompt, user_message, model)
        
        try:
            async with cache_session_maker() as session:
                result = await session.execute(
                    select(LLMCacheEntry).where(LLMCacheEntry.cache_key == cache_key)
                )
                entry = result.scalar_one_or_none()
                
                if entry is None:
                    return None  # Cache miss
                
                # Lazy expiration check
                if entry.expires_at <= datetime.now(timezone.utc):
                    # Delete expired entry
                    await session.execute(
                        delete(LLMCacheEntry).where(LLMCacheEntry.cache_key == cache_key)
                    )
                    await session.commit()
                    logger.debug(f"Cache entry expired and deleted: {cache_key[:16]}")
                    return None  # Expired
                
                # Cache hit
                logger.debug(f"Cache hit: {cache_key[:16]}")
                return json.loads(entry.response)
                
        except Exception as e:
            logger.warning(f"Cache get error: {e}")
            return None  # Graceful degradation
    
    async def set(
        self,
        system_prompt: str,
        user_message: str,
        model: str,
        provider: str,
        response: Dict[str, Any],
        tokens_used: int = 0
    ) -> bool:
        """
        Store response in cache.
        
        Args:
            system_prompt: Agent system prompt
            user_message: User input message
            model: LLM model name
            provider: LLM provider (e.g., "openai")
            response: LLM response dict
            tokens_used: Token count from response
        
        Returns:
            True if stored successfully, False otherwise
        """
        if not self.enabled:
            return False
        
        cache_key = generate_cache_key(system_prompt, user_message, model)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.ttl)
        
        try:
            async with cache_session_maker() as session:
                # Check if entry exists (update or insert)
                result = await session.execute(
                    select(LLMCacheEntry).where(LLMCacheEntry.cache_key == cache_key)
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    # Update existing entry
                    existing.response = json.dumps(response)
                    existing.tokens_used = tokens_used
                    existing.expires_at = expires_at
                else:
                    # Create new entry
                    entry = LLMCacheEntry(
                        id=str(uuid4()),
                        cache_key=cache_key,
                        system_prompt=system_prompt,
                        user_message=user_message,
                        response=json.dumps(response),
                        model=model,
                        provider=provider,
                        tokens_used=tokens_used,
                        expires_at=expires_at
                    )
                    session.add(entry)
                
                await session.commit()
                logger.debug(f"Cache set: {cache_key[:16]}")
                return True
                
        except Exception as e:
            logger.warning(f"Cache set error: {e}")
            return False  # Graceful degradation
    
    async def clear_all(self) -> int:
        """
        Clear all cache entries.
        
        Returns:
            Number of entries deleted
        """
        try:
            async with cache_session_maker() as session:
                result = await session.execute(delete(LLMCacheEntry))
                await session.commit()
                count = result.rowcount or 0
                logger.info(f"Cache cleared: {count} entries deleted")
                return count
        except Exception as e:
            logger.warning(f"Cache clear error: {e}")
            return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dict with total_entries, total_tokens, enabled status
        """
        try:
            async with cache_session_maker() as session:
                # Count entries
                result = await session.execute(select(LLMCacheEntry.id))
                entries = result.scalars().all()
                total_entries = len(entries)
                
                # Sum tokens
                result = await session.execute(select(LLMCacheEntry.tokens_used))
                tokens = result.scalars().all()
                total_tokens = sum(tokens)
                
                return {
                    "enabled": self.enabled,
                    "ttl": self.ttl,
                    "total_entries": total_entries,
                    "total_tokens_cached": total_tokens,
                }
        except Exception as e:
            logger.warning(f"Cache stats error: {e}")
            return {"enabled": self.enabled, "ttl": self.ttl, "error": str(e)}


# Global cache instance
llm_cache = LLMCache()