"""
Agent config cache unit tests
"""
import pytest
import json
import asyncio
from datetime import datetime

from agent.cache import AgentConfigCache
from models.agent_cache import AgentCacheEntry
from db.session import cache_session_maker, init_cache_db
from sqlalchemy import delete


@pytest.fixture(autouse=True)
async def setup_cache_db():
    """Setup and teardown cache database for each test"""
    # Initialize cache database
    await init_cache_db()
    
    # Clear all entries before test
    async with cache_session_maker() as session:
        await session.execute(delete(AgentCacheEntry))
        await session.commit()
    
    yield
    
    # Clear after test
    async with cache_session_maker() as session:
        await session.execute(delete(AgentCacheEntry))
        await session.commit()


class TestAgentConfigCacheGetSet:
    """Test AgentConfigCache get/set operations"""

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """Set should store entry, get should retrieve it"""
        cache = AgentConfigCache()
        await cache.initialize()
        
        config = {
            "id": "agent-001",
            "identity": {"name": "Test Agent"},
            "capabilities": {"llm": {"model": "gpt-4"}}
        }
        
        # Set cache
        success = await cache.set_config("agent-001", config)
        assert success is True
        
        # Get cache
        cached = await cache.get_config("agent-001")
        assert cached is not None
        assert cached["identity"]["name"] == "Test Agent"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self):
        """Get for nonexistent agent_id should return None"""
        cache = AgentConfigCache()
        await cache.initialize()
        
        cached = await cache.get_config("nonexistent-agent")
        assert cached is None

    @pytest.mark.asyncio
    async def test_get_expired_entry(self):
        """Expired entry should return None and be deleted"""
        cache = AgentConfigCache()
        cache.ttl = 0  # Immediate expiration
        await cache.initialize()
        
        config = {"id": "agent-002", "identity": {"name": "Expired"}}
        
        # Set with immediate expiration
        await cache.set_config("agent-002", config)
        
        # Wait a moment
        await asyncio.sleep(0.1)
        
        # Get should return None (expired)
        cached = await cache.get_config("agent-002")
        assert cached is None

    @pytest.mark.asyncio
    async def test_clear_all(self):
        """Clear all should delete all entries"""
        cache = AgentConfigCache()
        await cache.initialize()
        
        # Add entries
        await cache.set_config("agent-a", {"id": "a"})
        await cache.set_config("agent-b", {"id": "b"})
        
        # Clear
        count = await cache.clear_all()
        assert count >= 2
        
        # Verify cleared
        assert await cache.get_config("agent-a") is None
        assert await cache.get_config("agent-b") is None

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Get stats should return cache statistics"""
        cache = AgentConfigCache()
        await cache.initialize()
        
        # Add entries
        await cache.set_config("agent-1", {"id": "1"})
        await cache.set_config("agent-2", {"id": "2"})
        
        stats = await cache.get_stats()
        assert stats["enabled"] is True
        assert stats["total_entries"] >= 2


class TestAgentConfigCacheDisabled:
    """Test cache behavior when disabled"""

    @pytest.mark.asyncio
    async def test_disabled_returns_none(self):
        """Disabled cache should return None on get"""
        cache = AgentConfigCache()
        cache.enabled = False
        
        cached = await cache.get_config("agent-x")
        assert cached is None

    @pytest.mark.asyncio
    async def test_disabled_skips_set(self):
        """Disabled cache should skip set and return False"""
        cache = AgentConfigCache()
        cache.enabled = False
        
        success = await cache.set_config("agent-x", {"id": "x"})
        assert success is False


class TestAgentCacheEntryModel:
    """Test AgentCacheEntry model"""

    def test_model_fields_exist(self):
        """Model should have all required fields"""
        from models.agent_cache import AgentCacheEntry
        
        assert hasattr(AgentCacheEntry, '__tablename__')
        assert AgentCacheEntry.__tablename__ == "agent_cache_entries"

    def test_to_dict_method(self):
        """Model should have to_dict method"""
        entry = AgentCacheEntry(
            id="test-id",
            agent_id="agent-test",
            config_json='{"id": "test"}',
            model="gpt-4",
            expires_at=datetime.utcnow()
        )
        
        d = entry.to_dict()
        assert d["id"] == "test-id"
        assert d["agent_id"] == "agent-test"


class TestConfigSettings:
    """Test agent cache configuration"""

    def test_settings_has_cache_enabled(self):
        """Settings should have AGENT_CACHE_ENABLED"""
        from core.config import settings
        assert hasattr(settings, 'AGENT_CACHE_ENABLED')
        assert isinstance(settings.AGENT_CACHE_ENABLED, bool)

    def test_settings_has_cache_ttl(self):
        """Settings should have AGENT_CACHE_TTL"""
        from core.config import settings
        assert hasattr(settings, 'AGENT_CACHE_TTL')
        assert settings.AGENT_CACHE_TTL == 3600