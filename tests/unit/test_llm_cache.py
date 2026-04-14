"""
LLM cache unit tests
"""
import pytest
import json
import asyncio
from datetime import datetime, timezone

from agent.cache import generate_cache_key, LLMCache
from models.cache import LLMCacheEntry
from db.session import cache_session_maker, init_cache_db
from sqlalchemy import delete


@pytest.fixture(autouse=True)
async def setup_cache_db():
    """Setup and teardown cache database for each test"""
    # Initialize cache database
    await init_cache_db()
    
    # Clear all entries before test
    async with cache_session_maker() as session:
        await session.execute(delete(LLMCacheEntry))
        await session.commit()
    
    yield
    
    # Clear after test
    async with cache_session_maker() as session:
        await session.execute(delete(LLMCacheEntry))
        await session.commit()


class TestCacheKeyGeneration:
    """Test cache key generation"""

    def test_key_is_64_chars(self):
        """Cache key should be 64 character hex string"""
        key = generate_cache_key("system", "user", "gpt-4")
        assert len(key) == 64
        assert all(c in '0123456789abcdef' for c in key)

    def test_key_deterministic(self):
        """Same inputs should produce same key"""
        key1 = generate_cache_key("system", "user", "gpt-4")
        key2 = generate_cache_key("system", "user", "gpt-4")
        assert key1 == key2

    def test_key_unique_different_messages(self):
        """Different messages should produce different keys"""
        key1 = generate_cache_key("system", "hello", "gpt-4")
        key2 = generate_cache_key("system", "goodbye", "gpt-4")
        assert key1 != key2

    def test_key_unique_different_models(self):
        """Different models should produce different keys"""
        key1 = generate_cache_key("system", "user", "gpt-4")
        key2 = generate_cache_key("system", "user", "gpt-3.5")
        assert key1 != key2

    def test_key_unique_different_system_prompts(self):
        """Different system prompts should produce different keys"""
        key1 = generate_cache_key("You are helpful", "user", "gpt-4")
        key2 = generate_cache_key("You are creative", "user", "gpt-4")
        assert key1 != key2


class TestLLMCacheGetSet:
    """Test LLMCache get/set operations"""

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """Set should store entry, get should retrieve it"""
        cache = LLMCache()
        await cache.initialize()
        
        response = {"content": "Hello world", "role": "assistant"}
        
        # Set cache
        success = await cache.set(
            system_prompt="You are helpful",
            user_message="Hello",
            model="gpt-4",
            provider="openai",
            response=response,
            tokens_used=100
        )
        assert success is True
        
        # Get cache
        cached = await cache.get(
            system_prompt="You are helpful",
            user_message="Hello",
            model="gpt-4"
        )
        assert cached is not None
        assert cached["content"] == "Hello world"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self):
        """Get for nonexistent key should return None"""
        cache = LLMCache()
        await cache.initialize()
        
        cached = await cache.get(
            system_prompt="unknown",
            user_message="unknown",
            model="unknown"
        )
        assert cached is None

    @pytest.mark.asyncio
    async def test_get_expired_entry(self):
        """Expired entry should return None and be deleted"""
        cache = LLMCache()
        cache.ttl = 0  # Immediate expiration
        await cache.initialize()
        
        response = {"content": "Expired response"}
        
        # Set with immediate expiration
        await cache.set(
            system_prompt="system",
            user_message="user",
            model="gpt-4",
            provider="openai",
            response=response,
            tokens_used=50
        )
        
        # Wait a moment
        await asyncio.sleep(0.1)
        
        # Get should return None (expired)
        cached = await cache.get(
            system_prompt="system",
            user_message="user",
            model="gpt-4"
        )
        assert cached is None

    @pytest.mark.asyncio
    async def test_clear_all(self):
        """Clear all should delete all entries"""
        cache = LLMCache()
        await cache.initialize()
        
        # Add entries
        await cache.set("sys1", "msg1", "gpt-4", "openai", {"content": "1"}, 10)
        await cache.set("sys2", "msg2", "gpt-4", "openai", {"content": "2"}, 20)
        
        # Clear
        count = await cache.clear_all()
        assert count >= 2
        
        # Verify cleared
        assert await cache.get("sys1", "msg1", "gpt-4") is None
        assert await cache.get("sys2", "msg2", "gpt-4") is None

    @pytest.mark.asyncio
    async def test_get_stats(self):
        """Get stats should return cache statistics"""
        cache = LLMCache()
        await cache.initialize()
        
        # Add entries
        await cache.set("sys", "msg1", "gpt-4", "openai", {"content": "1"}, 100)
        await cache.set("sys", "msg2", "gpt-4", "openai", {"content": "2"}, 200)
        
        stats = await cache.get_stats()
        assert stats["enabled"] is True
        assert stats["total_entries"] >= 2
        assert stats["total_tokens_cached"] >= 300


class TestLLMCacheDisabled:
    """Test cache behavior when disabled"""

    @pytest.mark.asyncio
    async def test_disabled_returns_none(self):
        """Disabled cache should return None on get"""
        cache = LLMCache()
        cache.enabled = False
        
        cached = await cache.get("sys", "msg", "gpt-4")
        assert cached is None

    @pytest.mark.asyncio
    async def test_disabled_skips_set(self):
        """Disabled cache should skip set and return False"""
        cache = LLMCache()
        cache.enabled = False
        
        success = await cache.set("sys", "msg", "gpt-4", "openai", {"content": "x"}, 10)
        assert success is False


class TestLLMCacheEntryModel:
    """Test LLMCacheEntry model"""

    def test_model_fields_exist(self):
        """Model should have all required fields"""
        from models.cache import LLMCacheEntry
        
        # Check field annotations exist
        assert hasattr(LLMCacheEntry, '__tablename__')
        assert LLMCacheEntry.__tablename__ == "llm_cache_entries"

    def test_to_dict_method(self):
        """Model should have to_dict method"""
        from datetime import datetime
        entry = LLMCacheEntry(
            id="test-id",
            cache_key="test-key",
            system_prompt="sys",
            user_message="user",
            response='{"content": "test"}',
            model="gpt-4",
            provider="openai",
            tokens_used=100,
            expires_at=datetime.utcnow()
        )
        
        d = entry.to_dict()
        assert d["id"] == "test-id"
        assert d["cache_key"] == "test-key"
        assert d["tokens_used"] == 100


class TestConfigSettings:
    """Test LLM cache configuration"""

    def test_settings_has_cache_enabled(self):
        """Settings should have LLM_CACHE_ENABLED"""
        from core.config import settings
        assert hasattr(settings, 'LLM_CACHE_ENABLED')
        assert isinstance(settings.LLM_CACHE_ENABLED, bool)

    def test_settings_has_cache_ttl(self):
        """Settings should have LLM_CACHE_TTL"""
        from core.config import settings
        assert hasattr(settings, 'LLM_CACHE_TTL')
        assert settings.LLM_CACHE_TTL == 3600

    def test_settings_has_cache_db(self):
        """Settings should have LLM_CACHE_DB"""
        from core.config import settings
        assert hasattr(settings, 'LLM_CACHE_DB')
        assert settings.LLM_CACHE_DB == "cache.db"