# Agent Config Caching Design Spec

**Created:** 2026-04-14
**Phase:** 3 - Performance Optimization
**Status:** Ready for Implementation

---

## 1. Overview

### 1.1 Purpose

Implement agent configuration caching to reduce database load and latency for repeated agent executions. Agent configs are loaded from DB on every execution - caching them eliminates redundant queries.

### 1.2 Goals

- Reduce database queries for agent config loading by 90%+ for repeated executions
- Reduce agent execution startup latency
- Share cache infrastructure with LLM response cache (same SQLite file)
- Simple TTL-based invalidation

### 1.3 Non-Goals

- Event-based invalidation (future enhancement)
- Redis backend for horizontal scaling
- Usage-based selective caching

---

## 2. Architecture

### 2.1 System Flow

```
Agent Execution Request → Orchestrator → AgentConfigCache → [Cache Hit: Return Config]
                                                      → [Cache Miss: Query DB → Store → Return]
```

### 2.2 Components

| Component | File | Purpose |
|-----------|------|---------|
| `AgentConfigCache` | `agent/cache/agent_config_cache.py` | Cache service - get/set |
| `AgentCacheEntry` | `models/agent_cache.py` | SQLAlchemy model |
| `AgentOrchestrator` | `agent/core/orchestrator.py` | Integration point |

### 2.3 Storage

- **Backend:** SQLite (file-based, persistent)
- **Database:** `cache.db` (shared with LLM response cache)
- **Table:** `agent_cache_entries` (separate from `llm_cache_entries`)
- **TTL:** 1 hour (3600 seconds), lazy expiration

---

## 3. Cache Entry Schema

### 3.1 Model Definition

```python
class AgentCacheEntry(Base):
    __tablename__ = "agent_cache_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    agent_id: Mapped[str] = mapped_column(String(36), unique=True, index=True)
    config_json: Mapped[str] = mapped_column(Text)  # Full agent config as JSON
    model: Mapped[str] = mapped_column(String(50))  # Model name for metadata
    created_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
```

### 3.2 Indexes

- **Primary:** `id` (UUID)
- **Unique:** `agent_id` (indexed for fast lookups)

---

## 4. Cache Operations

### 4.1 Get Config

```python
async def get_config(agent_id: str) -> Optional[Dict[str, Any]]:
    """
    Get cached agent config with lazy expiration.
    Returns cached config if valid, None if expired or not found.
    """
    entry = await self._get_entry(agent_id)
    
    if entry is None:
        return None  # Cache miss
    
    if entry.expires_at <= utcnow():
        await self._delete_entry(agent_id)  # Lazy expiration
        return None  # Expired
    
    return json.loads(entry.config_json)  # Cache hit
```

### 4.2 Set Config

```python
async def set_config(agent_id: str, config: Dict[str, Any]) -> bool:
    """
    Store agent config in cache.
    TTL is read from settings.AGENT_CACHE_TTL (1 hour).
    """
    expires_at = utcnow() + timedelta(seconds=self.ttl)
    
    # Upsert: update if exists, insert if not
    entry = AgentCacheEntry(
        agent_id=agent_id,
        config_json=json.dumps(config),
        model=config.get("capabilities", {}).get("llm", {}).get("model", ""),
        expires_at=expires_at
    )
    
    await self._upsert_entry(entry)
    return True
```

---

## 5. Orchestrator Integration

### 5.1 Modified _load_agent_config

```python
async def _load_agent_config(self, agent_id: str) -> Dict[str, Any]:
    """Load agent config from cache or database"""
    
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
            raise AgentError(f"Agent {agent_id} not found")
        
        config = agent.to_dict()
        
        # Store in cache
        await agent_config_cache.set_config(agent_id, config)
        
        return config
```

---

## 6. Configuration

### 6.1 Settings (core/config.py)

```python
# Agent Cache Configuration
AGENT_CACHE_ENABLED: bool = Field(
    default=True,
    description="Enable agent config caching"
)
AGENT_CACHE_TTL: int = Field(
    default=3600,  # 1 hour
    description="Agent config cache TTL in seconds"
)
AGENT_CACHE_DB: str = Field(
    default="cache.db",
    description="SQLite cache database (shared with LLM cache)"
)
```

---

## 7. Error Handling

### 7.1 Graceful Degradation

| Error | Handling |
|-------|----------|
| Cache DB unavailable | Skip cache, load from DB directly |
| Cache read error | Log warning, load from DB |
| Cache write error | Log warning, continue execution |
| Corrupted cached config | Delete entry, load from DB |

---

## 8. Testing Strategy

### 8.1 Test Coverage

| Test Class | Tests | Purpose |
|------------|-------|---------|
| `TestAgentConfigCache` | 5 | set/get, expiration, clear |
| `TestOrchestratorCache` | 3 | Integration - cache hit bypasses DB |
| `TestConfigSettings` | 3 | Configuration variables |

### 8.2 Mocking Strategy

- Use same test cache database fixture as LLM cache tests
- Mock database queries for orchestrator integration tests

---

## 9. Performance Impact

### 9.1 Expected Metrics

| Metric | Without Cache | With Cache (Hit) | Improvement |
|--------|--------------|------------------|-------------|
| Config load latency | 5-10ms (DB query) | <1ms (SQLite) | ~10x faster |
| DB queries per execution | 1 query | 0 queries (cache hit) | 100% reduction |

### 9.2 Cache Hit Rate Estimation

- **Repeated agent executions:** 80-90% hit rate
- **One-time executions:** 0% (first run always misses)

---

## 10. File Structure

```
agent/
├── cache/
│   ├── __init__.py              # Updated exports
│   ├── llm_cache.py             # Existing
│   ├── agent_config_cache.py    # NEW
│   └── keygen.py                # Existing

models/
├── cache.py                     # Existing (LLMCacheEntry)
├── agent_cache.py               # NEW (AgentCacheEntry)

agent/core/
├── orchestrator.py              # Modified (cache integration)

core/
├── config.py                    # Modified (AGENT_CACHE settings)

tests/unit/
├── test_llm_cache.py            # Existing
├── test_agent_config_cache.py   # NEW
```

---

## 11. Implementation Sequence

1. Add AGENT_CACHE config variables to `core/config.py`
2. Create `AgentCacheEntry` model in `models/agent_cache.py`
3. Create `AgentConfigCache` in `agent/cache/agent_config_cache.py`
4. Modify `AgentOrchestrator._load_agent_config` to use cache
5. Add unit tests in `tests/unit/test_agent_config_cache.py`
6. Run full test suite

---

## 12. Shared Database Design

```
cache.db (SQLite):
├── llm_cache_entries
│   ├── id (PK)
│   ├── cache_key (unique)
│   ├── system_prompt
│   ├── user_message
│   ├── response
│   ├── model
│   ├── provider
│   ├── tokens_used
│   ├── created_at
│   └── expires_at
│
└── agent_cache_entries  ← NEW
│   ├── id (PK)
│   ├── agent_id (unique, indexed)
│   ├── config_json
│   ├── model
│   ├── created_at
│   └── expires_at
```

Both tables share the same SQLite file, managed by the same cache engine in `db/session.py`.