"""
Agent configuration cache service with SQLite storage and lazy expiration
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import uuid4

from sqlalchemy import select, delete

from db.session import cache_session_maker, init_cache_db
from models.agent_cache import AgentCacheEntry
from core.config import settings

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    """Get current UTC time as timezone-naive datetime (for SQLite compatibility)"""
    return datetime.utcnow()


class AgentConfigCache:
    """
    Agent configuration cache with SQLite storage and lazy expiration.
    
    Features:
    - agent_id as unique key for fast lookups
    - Lazy expiration on read (delete expired entries)
    - Graceful degradation on cache errors
    - TTL configurable via settings
    - Shared database with LLM cache (cache.db)
    """
    
    def __init__(self):
        self.enabled = settings.AGENT_CACHE_ENABLED
        self.ttl = settings.AGENT_CACHE_TTL
        self._initialized = False
    
    async def initialize(self):
        """Initialize cache database (create table if needed)"""
        if self._initialized:
            return
        
        try:
            await init_cache_db()
            self._initialized = True
            logger.info("Agent config cache initialized")
        except Exception as e:
            logger.warning(f"Agent cache initialization failed: {e}")
            self.enabled = False
    
    async def get_config(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached agent config with lazy expiration.
        
        Args:
            agent_id: Agent UUID
        
        Returns:
            Cached config dict if valid, None if expired or not found
        """
        if not self.enabled:
            return None
        
        try:
            async with cache_session_maker() as session:
                result = await session.execute(
                    select(AgentCacheEntry).where(AgentCacheEntry.agent_id == agent_id)
                )
                entry = result.scalar_one_or_none()
                
                if entry is None:
                    return None  # Cache miss
                
                # Lazy expiration check
                if entry.expires_at <= utcnow():
                    # Delete expired entry
                    await session.execute(
                        delete(AgentCacheEntry).where(AgentCacheEntry.agent_id == agent_id)
                    )
                    await session.commit()
                    logger.debug(f"Agent cache entry expired and deleted: {agent_id}")
                    return None  # Expired
                
                # Cache hit
                logger.debug(f"Agent cache hit: {agent_id}")
                return json.loads(entry.config_json)
                
        except Exception as e:
            logger.warning(f"Agent cache get error: {e}")
            return None  # Graceful degradation
    
    async def set_config(self, agent_id: str, config: Dict[str, Any]) -> bool:
        """
        Store agent config in cache.
        
        Args:
            agent_id: Agent UUID
            config: Full agent configuration dict
        
        Returns:
            True if stored successfully, False otherwise
        """
        if not self.enabled:
            return False
        
        expires_at = utcnow() + timedelta(seconds=self.ttl)
        
        # Extract model name from config for metadata
        model = config.get("capabilities", {}).get("llm", {}).get("model", "")
        
        try:
            async with cache_session_maker() as session:
                # Check if entry exists (update or insert)
                result = await session.execute(
                    select(AgentCacheEntry).where(AgentCacheEntry.agent_id == agent_id)
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    # Update existing entry
                    existing.config_json = json.dumps(config)
                    existing.model = model
                    existing.expires_at = expires_at
                else:
                    # Create new entry
                    entry = AgentCacheEntry(
                        id=str(uuid4()),
                        agent_id=agent_id,
                        config_json=json.dumps(config),
                        model=model,
                        expires_at=expires_at
                    )
                    session.add(entry)
                
                await session.commit()
                logger.debug(f"Agent cache set: {agent_id}")
                return True
                
        except Exception as e:
            logger.warning(f"Agent cache set error: {e}")
            return False  # Graceful degradation
    
    async def clear_all(self) -> int:
        """
        Clear all agent cache entries.
        
        Returns:
            Number of entries deleted
        """
        try:
            async with cache_session_maker() as session:
                result = await session.execute(delete(AgentCacheEntry))
                await session.commit()
                count = result.rowcount or 0
                logger.info(f"Agent cache cleared: {count} entries deleted")
                return count
        except Exception as e:
            logger.warning(f"Agent cache clear error: {e}")
            return 0
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Get agent cache statistics.
        
        Returns:
            Dict with total_entries, enabled status
        """
        try:
            async with cache_session_maker() as session:
                result = await session.execute(select(AgentCacheEntry.id))
                entries = result.scalars().all()
                total_entries = len(entries)
                
                return {
                    "enabled": self.enabled,
                    "ttl": self.ttl,
                    "total_entries": total_entries,
                }
        except Exception as e:
            logger.warning(f"Agent cache stats error: {e}")
            return {"enabled": self.enabled, "ttl": self.ttl, "error": str(e)}


# Global cache instance
agent_config_cache = AgentConfigCache()