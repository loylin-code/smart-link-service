# LLM Response Caching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement SQLite-based LLM response caching with lazy expiration to reduce latency and API costs.

**Architecture:** Cache service (`LLMCache`) stores LLM responses in SQLite using SHA-256 cache keys. Lazy expiration deletes expired entries on read. LLMClient integration checks cache before calling LLM API.

**Tech Stack:** SQLite (aiosqlite), SQLAlchemy, SHA-256 hashing, Python asyncio

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `agent/cache/__init__.py` | Create | Module entry point, exports |
| `agent/cache/keygen.py` | Create | Cache key generation (SHA-256) |
| `agent/cache/llm_cache.py` | Create | LLMCache class (get/set operations) |
| `models/cache.py` | Create | LLMCacheEntry SQLAlchemy model |
| `core/config.py` | Modify | Add LLM cache config variables |
| `agent/llm/client.py` | Modify | Integrate cache into LLMClient |
| `db/session.py` | Modify | Add cache database engine |
| `tests/unit/test_llm_cache.py` | Create | Unit tests (~15 tests) |

---

### Task 1: Add Configuration Variables

**Files:**
- Modify: `core/config.py`

- [ ] **Step 1: Add LLM cache configuration to Settings class**

Locate the `# LLM` section in `core/config.py` and add cache configuration after existing LLM settings:

```python
# LLM Caching
LLM_CACHE_ENABLED: bool = Field(
    default=True,
    description="Enable LLM response caching"
)
LLM_CACHE_TTL: int = Field(
    default=3600,
    description="Cache TTL in seconds (default: 1 hour)"
)
LLM_CACHE_DB: str = Field(
    default="cache.db",
    description="SQLite cache database file path"
)
```

- [ ] **Step 2: Verify settings import**

Run: `python -c "from core.config import settings; print(settings.LLM_CACHE_ENABLED, settings.LLM_CACHE_TTL, settings.LLM_CACHE_DB)"`
Expected: `True 3600 cache.db`

- [ ] **Step 3: Commit**

```bash
git add core/config.py
git commit -m "feat(config): add LLM cache configuration variables"
```

---

### Task 2: Create Cache Entry Model

**Files:**
- Create: `models/cache.py`

- [ ] **Step 1: Create models/cache.py with LLMCacheEntry model**

```python
"""
LLM Cache entry model for storing cached LLM responses
"""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Text, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from db.session import Base


class LLMCacheEntry(Base):
    """
    SQLite model for LLM response cache entries.
    
    Cache key is SHA-256 hash of (system_prompt + user_message + model).
    Lazy expiration: entries deleted when expires_at <= now on read.
    """
    
    __tablename__ = "llm_cache_entries"
    
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    cache_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    system_prompt: Mapped[str] = mapped_column(Text)
    user_message: Mapped[str] = mapped_column(Text)
    response: Mapped[str] = mapped_column(Text)  # JSON response
    model: Mapped[str] = mapped_column(String(50))
    provider: Mapped[str] = mapped_column(String(50))
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "cache_key": self.cache_key,
            "system_prompt": self.system_prompt,
            "user_message": self.user_message,
            "response": self.response,
            "model": self.model,
            "provider": self.provider,
            "tokens_used": self.tokens_used,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
```

- [ ] **Step 2: Verify model import**

Run: `python -c "from models.cache import LLMCacheEntry; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add models/cache.py
git commit -m "feat(models): add LLMCacheEntry model for response caching"
```

---

### Task 3: Create Cache Database Engine

**Files:**
- Modify: `db/session.py`

- [ ] **Step 1: Add cache database engine to db/session.py**

Add after the main database engine definition (after line 41):

```python
# Cache database (separate SQLite file for LLM response caching)
from core.config import settings as cache_settings

CACHE_DATABASE_URL = f"sqlite+aiosqlite:///./{cache_settings.LLM_CACHE_DB}"

cache_engine = create_async_engine(
    CACHE_DATABASE_URL,
    echo=cache_settings.DEBUG,
    future=True,
)

cache_session_maker = async_sessionmaker(
    cache_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def init_cache_db():
    """Initialize cache database - create cache table"""
    async with cache_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_cache_db():
    """Close cache database connections"""
    await cache_engine.dispose()
```

- [ ] **Step 2: Verify cache engine import**

Run: `python -c "from db.session import cache_engine, cache_session_maker; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add db/session.py
git commit -m "feat(db): add cache database engine and session maker"
```

---

### Task 4: Create Cache Key Generator

**Files:**
- Create: `agent/cache/__init__.py`
- Create: `agent/cache/keygen.py`

- [ ] **Step 1: Create agent/cache directory**

```bash
mkdir -p agent/cache
```

- [ ] **Step 2: Create agent/cache/__init__.py placeholder**

```python
"""
Agent cache module - LLM response caching
"""
from agent.cache.keygen import generate_cache_key
from agent.cache.llm_cache import LLMCache

__all__ = ["generate_cache_key", "LLMCache"]
```

- [ ] **Step 3: Create agent/cache/keygen.py with key generation**

```python
"""
Cache key generation for LLM responses
"""
import hashlib


def generate_cache_key(system_prompt: str, user_message: str, model: str) -> str:
    """
    Generate unique cache key for LLM request.
    
    Key composition: SHA-256 hash of (system_prompt | user_message | model)
    
    Args:
        system_prompt: Agent system prompt/identity
        user_message: User's input message
        model: LLM model name (e.g., "gpt-4o-mini")
    
    Returns:
        64-character SHA-256 hex digest
    """
    content = f"{system_prompt}|{user_message}|{model}"
    return hashlib.sha256(content.encode('utf-8')).hexdigest()
```

- [ ] **Step 4: Verify keygen import**

Run: `python -c "from agent.cache import generate_cache_key; key = generate_cache_key('sys', 'user', 'gpt-4'); print(len(key), key[:16])"`
Expected: `64 a1b2c3d4e5f6...` (64 chars, hex string)

- [ ] **Step 5: Commit**

```bash
git add agent/cache/__init__.py agent/cache/keygen.py
git commit -m "feat(cache): add cache key generation with SHA-256"
```

---

### Task 5: Create LLMCache Service

**Files:**
- Create: `agent/cache/llm_cache.py`

- [ ] **Step 1: Create agent/cache/llm_cache.py with LLMCache class**

```python
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
```

- [ ] **Step 2: Update agent/cache/__init__.py exports**

```python
"""
Agent cache module - LLM response caching
"""
from agent.cache.keygen import generate_cache_key
from agent.cache.llm_cache import LLMCache, llm_cache

__all__ = ["generate_cache_key", "LLMCache", "llm_cache"]
```

- [ ] **Step 3: Verify LLMCache import**

Run: `python -c "from agent.cache import LLMCache, llm_cache; print('OK')"`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add agent/cache/__init__.py agent/cache/llm_cache.py
git commit -m "feat(cache): add LLMCache service with get/set operations"
```

---

### Task 6: Write Unit Tests

**Files:**
- Create: `tests/unit/test_llm_cache.py`

- [ ] **Step 1: Create tests/unit/test_llm_cache.py with test classes**

```python
"""
LLM cache unit tests
"""
import pytest
import json
import os
import asyncio
from datetime import datetime, timezone, timedelta

from agent.cache import generate_cache_key, LLMCache, llm_cache
from models.cache import LLMCacheEntry
from db.session import cache_engine, cache_session_maker, init_cache_db
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
        entry = LLMCacheEntry(
            id="test-id",
            cache_key="test-key",
            system_prompt="sys",
            user_message="user",
            response='{"content": "test"}',
            model="gpt-4",
            provider="openai",
            tokens_used=100,
            expires_at=datetime.now(timezone.utc)
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
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/unit/test_llm_cache.py -v`
Expected: 18 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_llm_cache.py
git commit -m "test(cache): add unit tests for LLMCache and key generation"
```

---

### Task 7: Integrate Cache into LLMClient

**Files:**
- Modify: `agent/llm/client.py`

- [ ] **Step 1: Add cache integration to LLMClient.chat method**

In `agent/llm/client.py`, import cache at top and modify `chat` method:

Add import at top of file (after line 10):
```python
from agent.cache import llm_cache
```

Modify `chat` method (lines 67-146) to add cache integration. Replace the entire method:

```python
async def chat(
    self,
    messages: List[Dict[str, str]],
    tools: Optional[List[Dict[str, Any]]] = None,
    tool_choice: Optional[str] = "auto",
    temperature: Optional[float] = 0.7,
    max_tokens: Optional[int] = 4096,
    **kwargs
) -> Dict[str, Any]:
    """
    Send chat completion request with caching.
    
    Args:
        messages: List of message dicts with role and content
        tools: List of tool definitions (OpenAI format)
        tool_choice: Tool choice strategy ("auto", "none", or specific)
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
        **kwargs: Additional parameters
        
    Returns:
        Response dict with content, tool_calls, usage
    """
    # Initialize cache if needed
    if llm_cache.enabled and not llm_cache._initialized:
        await llm_cache.initialize()
    
    # Extract prompts for cache key
    system_prompt = next(
        (m.get('content', '') for m in messages if m.get('role') == 'system'),
        ""
    )
    user_message = next(
        (m.get('content', '') for m in messages if m.get('role') == 'user'),
        ""
    )
    
    # Check cache (only if no tools - tool calls vary)
    if llm_cache.enabled and not tools:
        cached = await llm_cache.get(
            system_prompt=system_prompt,
            user_message=user_message,
            model=self.model
        )
        if cached:
            return cached  # Cache hit
    
    try:
        # Build request
        request_params = {
            "model": self._get_model_string(),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        
        # Add tools if provided
        if tools:
            request_params["tools"] = tools
            request_params["tool_choice"] = tool_choice
        
        # Add extra params
        request_params.update(kwargs)
        
        # Call LLM
        response = await acompletion(**request_params)
        
        # Extract result
        message = response.choices[0].message
        
        result = {
            "content": message.content or "",
            "role": message.role,
        }
        
        # Extract tool calls if present
        if hasattr(message, 'tool_calls') and message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in message.tool_calls
            ]
        
        # Add usage info
        if hasattr(response, 'usage'):
            result["usage"] = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        
        # Store in cache (only if no tools)
        if llm_cache.enabled and not tools:
            await llm_cache.set(
                system_prompt=system_prompt,
                user_message=user_message,
                model=self.model,
                provider=self.provider,
                response=result,
                tokens_used=result.get("usage", {}).get("total_tokens", 0)
            )
        
        return result
        
    except Exception as e:
        raise LLMError(
            f"LLM request failed: {str(e)}",
            provider=self.provider
        )
```

- [ ] **Step 2: Verify LLMClient import still works**

Run: `python -c "from agent.llm.client import LLMClient; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add agent/llm/client.py
git commit -m "feat(llm): integrate response caching into LLMClient"
```

---

### Task 8: Run Full Test Suite

**Files:**
- All modified files

- [ ] **Step 1: Run all unit tests**

Run: `pytest tests/unit/ -v`
Expected: All tests PASS (92 + 18 = 110 tests)

- [ ] **Step 2: Verify app imports correctly**

Run: `python -c "from gateway.main import app; print('OK')"`
Expected: OK

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat(cache): complete LLM response caching implementation

- SQLite-based cache with lazy expiration
- SHA-256 cache keys (system_prompt + user_message + model)
- LLMClient integration with cache hit/miss handling
- 18 unit tests for cache module
- 1 hour TTL (configurable)

Phase 3 Performance Optimization - LLM Caching complete."
```

---

## Self-Review Checklist

| Spec Section | Covered by Task |
|--------------|-----------------|
| 2.1 System Flow | Task 7 (LLMClient integration) |
| 2.2 Components | Task 4, 5, 6 |
| 3.1 Cache Entry Schema | Task 2 (LLMCacheEntry model) |
| 4.1 Key Composition | Task 4 (keygen.py) |
| 5.1 Get with Lazy Expiration | Task 5 (llm_cache.py get method) |
| 5.2 Set | Task 5 (llm_cache.py set method) |
| 6.1 LLMClient Integration | Task 7 (client.py modification) |
| 7.1 Settings | Task 1 (config.py) |
| 8.1 Graceful Degradation | Task 5 (exception handling in get/set) |
| 9.1 Test Coverage | Task 6 (18 tests) |

**Placeholder Scan:** No TBD/TODO found

**Type Consistency:** 
- `generate_cache_key(system_prompt, user_message, model)` signature consistent across keygen.py, llm_cache.py, and client.py
- `LLMCacheEntry` fields match between model and usage in llm_cache.py
- Response dict structure consistent (content, role, usage)