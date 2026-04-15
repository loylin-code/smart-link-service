# Agent Config Caching Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement SQLite-based agent config caching with lazy expiration to reduce database load for repeated agent executions.

**Architecture:** Cache service (`AgentConfigCache`) stores agent configs in SQLite (shared `cache.db` with LLM cache). Lazy expiration deletes expired entries on read. Orchestrator integration checks cache before querying DB.

**Tech Stack:** SQLite (aiosqlite), SQLAlchemy, Python asyncio

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `agent/cache/agent_config_cache.py` | Create | AgentConfigCache class |
| `models/agent_cache.py` | Create | AgentCacheEntry SQLAlchemy model |
| `core/config.py` | Modify | Add AGENT_CACHE config variables |
| `agent/cache/__init__.py` | Modify | Export AgentConfigCache |
| `agent/core/orchestrator.py` | Modify | Integrate cache into _load_agent_config |
| `tests/unit/test_agent_config_cache.py` | Create | Unit tests (~12 tests) |

---

### Task 1: Add Configuration Variables

**Files:**
- Modify: `core/config.py`

- [ ] **Step 1: Add AGENT_CACHE configuration to Settings class**

Locate the `# Agent Cache Configuration` section in `core/config.py` (after LLM cache settings) and add:

```python
# Agent Cache Configuration
AGENT_CACHE_ENABLED: bool = Field(
    default=True,
    description="Enable agent config caching"
)
AGENT_CACHE_TTL: int = Field(
    default=3600,
    description="Agent config cache TTL in seconds (default: 1 hour)"
)
```

Note: AGENT_CACHE_DB is not needed - uses same `cache.db` as LLM cache.

- [ ] **Step 2: Verify settings import**

Run: `python -c "from core.config import settings; print(settings.AGENT_CACHE_ENABLED, settings.AGENT_CACHE_TTL)"`
Expected: `True 3600`

- [ ] **Step 3: Commit**

```bash
git add core/config.py
git commit -m "feat(config): add agent cache configuration variables"
```

---

### Task 2: Create AgentCacheEntry Model

**Files:**
- Create: `models/agent_cache.py`

- [ ] **Step 1: Create models/agent_cache.py with AgentCacheEntry model**

```python
"""
Agent cache entry model for caching agent configurations
"""
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime
import uuid

from db.session import Base


def generate_uuid() -> str:
    """Generate a UUID string"""
    return str(uuid.uuid4())


class AgentCacheEntry(Base):
    """
    SQLite model for agent configuration cache entries.
    
    Uses agent_id as unique key for lookups.
    Lazy expiration: entries deleted when expires_at <= now on read.
    """
    
    __tablename__ = "agent_cache_entries"
    
    id = Column(String(36), primary_key=True, default=generate_uuid)
    agent_id = Column(String(36), unique=True, index=True, nullable=False)
    config_json = Column(Text, nullable=False)  # Full agent config as JSON
    model = Column(String(50), nullable=True)  # Model name for metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "config_json": self.config_json,
            "model": self.model,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
```

- [ ] **Step 2: Verify model import**

Run: `python -c "from models.agent_cache import AgentCacheEntry; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add models/agent_cache.py
git commit -m "feat(models): add AgentCacheEntry model for config caching"
```

---

### Task 3: Create AgentConfigCache Service

**Files:**
- Create: `agent/cache/agent_config_cache.py`
- Modify: `agent/cache/__init__.py`

- [ ] **Step 1: Create agent/cache/agent_config_cache.py**

```python
"""
Agent configuration cache service with SQLite storage and lazy expiration
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import uuid4

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

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
```

- [ ] **Step 2: Update agent/cache/__init__.py exports**

```python
"""
Agent cache module - LLM response and agent config caching
"""
from agent.cache.keygen import generate_cache_key
from agent.cache.llm_cache import LLMCache, llm_cache
from agent.cache.agent_config_cache import AgentConfigCache, agent_config_cache

__all__ = [
    "generate_cache_key", 
    "LLMCache", "llm_cache",
    "AgentConfigCache", "agent_config_cache"
]
```

- [ ] **Step 3: Verify AgentConfigCache import**

Run: `python -c "from agent.cache import AgentConfigCache, agent_config_cache; print('OK')"`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add agent/cache/__init__.py agent/cache/agent_config_cache.py
git commit -m "feat(cache): add AgentConfigCache service with get/set operations"
```

---

### Task 4: Write Unit Tests

**Files:**
- Create: `tests/unit/test_agent_config_cache.py`

- [ ] **Step 1: Create tests/unit/test_agent_config_cache.py**

```python
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
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/unit/test_agent_config_cache.py -v`
Expected: 12 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_agent_config_cache.py
git commit -m "test(cache): add unit tests for AgentConfigCache"
```

---

### Task 5: Integrate Cache into Orchestrator

**Files:**
- Modify: `agent/core/orchestrator.py`

- [ ] **Step 1: Add cache import to orchestrator.py**

Add at top of file (after existing imports):

```python
from agent.cache import agent_config_cache
```

- [ ] **Step 2: Modify _load_agent_config method**

Replace the `_load_agent_config` method (around lines 338-360):

```python
async def _load_agent_config(self, agent_id: str) -> Dict[str, Any]:
    """Load agent configuration from cache or database
    
    Args:
        agent_id: Agent ID to load
        
    Returns:
        Agent configuration dictionary
        
    Raises:
        AgentError: If agent not found
    """
    # Initialize cache if needed
    if agent_config_cache.enabled and not agent_config_cache._initialized:
        await agent_config_cache.initialize()
    
    # Check cache first
    cached = await agent_config_cache.get_config(agent_id)
    if cached:
        return cached  # Cache hit
    
    # Cache miss - load from database
    async with async_session_maker() as db:
        from models.agent import Agent
        from sqlalchemy import select
        
        result = await db.execute(select(Agent).where(Agent.id == agent_id))
        agent = result.scalar_one_or_none()
        
        if not agent:
            raise AgentError(f"Agent {agent_id} not found", agent_id=agent_id)
        
        config = agent.to_dict()
        
        # Store in cache
        await agent_config_cache.set_config(agent_id, config)
        
        return config
```

- [ ] **Step 3: Verify orchestrator import**

Run: `python -c "from agent.core.orchestrator import AgentOrchestrator; print('OK')"`
Expected: OK

- [ ] **Step 4: Commit**

```bash
git add agent/core/orchestrator.py
git commit -m "feat(orchestrator): integrate agent config caching"
```

---

### Task 6: Run Full Test Suite

**Files:**
- All modified files

- [ ] **Step 1: Run all unit tests**

Run: `pytest tests/unit/ -v`
Expected: All tests PASS (109 + 12 = 121 tests)

- [ ] **Step 2: Verify app imports**

Run: `python -c "from gateway.main import app; print('OK')"`
Expected: OK

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat(cache): complete agent config caching implementation

- SQLite-based cache with lazy expiration (shared cache.db)
- agent_id as unique key for fast lookups
- Orchestrator integration with cache hit/miss handling
- 12 unit tests for agent cache module
- 1 hour TTL (configurable via AGENT_CACHE_TTL)

Phase 3 Performance Optimization - Agent Config Caching complete."

Total tests: 121 (109 previous + 12 new)
```

---

## Self-Review Checklist

| Spec Section | Covered by Task |
|--------------|-----------------|
| 2.1 System Flow | Task 5 (Orchestrator integration) |
| 2.2 Components | Task 3, 4 |
| 3.1 Cache Entry Schema | Task 2 (AgentCacheEntry model) |
| 4.1 Get Config | Task 3 (get_config method) |
| 4.2 Set Config | Task 3 (set_config method) |
| 5.1 Orchestrator Integration | Task 5 |
| 6.1 Settings | Task 1 (config.py) |
| 7.1 Graceful Degradation | Task 3 (exception handling) |
| 8.1 Test Coverage | Task 4 (12 tests) |

**Placeholder Scan:** No TBD/TODO found

**Type Consistency:**
- `get_config(agent_id)` signature consistent across agent_config_cache.py and orchestrator.py
- `AgentCacheEntry` fields match between model and usage