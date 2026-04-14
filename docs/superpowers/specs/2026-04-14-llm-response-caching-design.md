# LLM Response Caching Design Spec

**Created:** 2026-04-14
**Phase:** 3 - Performance Optimization
**Status:** Ready for Implementation

---

## 1. Overview

### 1.1 Purpose

Implement LLM response caching to reduce latency and API costs for repeated queries. Cache responses using SQLite with lazy expiration.

### 1.2 Goals

- Reduce LLM API calls by 80-90% for repeated queries
- Reduce response latency from ~2-3s to <10ms for cache hits
- Provide predictable, deterministic caching behavior
- Zero external dependencies (SQLite-based)

### 1.3 Non-Goals

- Semantic similarity caching (future enhancement)
- Distributed cache sharing (horizontal scaling)
- Real-time data caching (news, live updates)

---

## 2. Architecture

### 2.1 System Flow

```
User Request → Orchestrator → LLMClient → Cache Check → [Cache Hit: Return Cached]
                                                    → [Cache Miss: Call LLM → Store → Return]
```

### 2.2 Components

| Component | File | Purpose |
|-----------|------|---------|
| `LLMCache` | `agent/cache/llm_cache.py` | Cache service - get/set/expire |
| `LLMCacheEntry` | `models/cache.py` | SQLAlchemy model for cache entries |
| `LLMClient` | `agent/llm/client.py` | Modified to integrate cache |

### 2.3 Storage

- **Backend:** SQLite (file-based, persistent)
- **Database:** `cache.db` (separate from main application database)
- **TTL:** Lazy expiration (check on read, delete if expired)

---

## 3. Cache Entry Schema

### 3.1 Model Definition

```python
class LLMCacheEntry(Base):
    __tablename__ = "llm_cache_entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    cache_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # SHA-256
    system_prompt: Mapped[str] = mapped_column(Text)  # For verification/debug
    user_message: Mapped[str] = mapped_column(Text)  # For debug
    response: Mapped[str] = mapped_column(Text)  # JSON response
    model: Mapped[str] = mapped_column(String(50))  # e.g., "gpt-4o-mini"
    provider: Mapped[str] = mapped_column(String(50))  # e.g., "openai"
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)  # created_at + TTL
```

### 3.2 Indexes

- **Primary:** `id` (UUID)
- **Unique:** `cache_key` (SHA-256 hash)
- **Query optimization:** Index on `cache_key` for fast lookups

---

## 4. Cache Key Generation

### 4.1 Key Composition

```
cache_key = SHA-256(system_prompt | user_message | model)
```

### 4.2 Implementation

```python
import hashlib

def generate_cache_key(system_prompt: str, user_message: str, model: str) -> str:
    """Generate unique cache key for LLM request."""
    content = f"{system_prompt}|{user_message}|{model}"
    return hashlib.sha256(content.encode('utf-8')).hexdigest()
```

### 4.3 Key Characteristics

- **Deterministic:** Same inputs always produce same key
- **Unique:** Different prompts/models produce different keys
- **Length:** 64 characters (SHA-256 hex digest)
- **Collision resistance:** SHA-256 is cryptographically secure

---

## 5. Cache Operations

### 5.1 Get (with Lazy Expiration)

```python
async def get(cache_key: str) -> Optional[Dict[str, Any]]:
    """
    Get cached response with lazy expiration.
    
    Returns:
        Cached response if valid, None if expired or not found
    """
    entry = await self._get_entry(cache_key)
    
    if entry is None:
        return None  # Cache miss
    
    if entry.expires_at <= datetime.now(timezone.utc):
        await self._delete_entry(cache_key)  # Lazy expiration
        return None  # Expired
    
    return json.loads(entry.response)  # Cache hit
```

### 5.2 Set

```python
async def set(
    cache_key: str,
    system_prompt: str,
    user_message: str,
    response: Dict[str, Any],
    model: str,
    provider: str,
    tokens_used: int = 0
) -> None:
    """
    Store response in cache.
    
    TTL is read from settings.LLM_CACHE_TTL.
    """
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=self.ttl)
    
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
    
    await self._store_entry(entry)
```

### 5.3 Clear (Optional)

```python
async def clear_all() -> int:
    """Clear all cache entries. Returns count of deleted entries."""
    return await self._delete_all_entries()
```

---

## 6. LLM Client Integration

### 6.1 Modified Chat Method

```python
class LLMClient:
    async def chat(self, messages: List[Dict], ...) -> Dict[str, Any]:
        # Skip cache if disabled
        if not self.cache_enabled:
            return await self._call_llm(messages, ...)
        
        # Extract prompts for cache key
        system_prompt = self._extract_system_prompt(messages)
        user_message = self._extract_user_message(messages)
        
        # Generate cache key
        cache_key = generate_cache_key(system_prompt, user_message, self.model)
        
        # Check cache
        cached = await self.cache.get(cache_key)
        if cached:
            return cached  # Cache hit
        
        # Cache miss - call LLM
        response = await self._call_llm(messages, ...)
        
        # Store in cache
        await self.cache.set(
            cache_key=cache_key,
            system_prompt=system_prompt,
            user_message=user_message,
            response=response,
            model=self.model,
            provider=self.provider,
            tokens_used=response.get("usage", {}).get("total_tokens", 0)
        )
        
        return response
```

### 6.2 Streaming Consideration

**Decision:** Do NOT cache streaming responses.

- Streaming responses are partial chunks, not complete responses
- Cache only applies to non-streaming `chat()` method
- `chat_stream()` always calls LLM directly

---

## 7. Configuration

### 7.1 Settings (core/config.py)

```python
# LLM Cache Configuration
LLM_CACHE_ENABLED: bool = Field(
    default=True,
    description="Enable LLM response caching"
)
LLM_CACHE_TTL: int = Field(
    default=3600,  # 1 hour
    description="Cache TTL in seconds"
)
LLM_CACHE_DB: str = Field(
    default="cache.db",
    description="SQLite cache database file path"
)
```

### 7.2 Environment Variables

```bash
# .env
LLM_CACHE_ENABLED=true
LLM_CACHE_TTL=3600
LLM_CACHE_DB=cache.db
```

---

## 8. Error Handling

### 8.1 Graceful Degradation

| Error | Handling |
|-------|----------|
| Cache DB unavailable | Skip cache, proceed with LLM call directly |
| Cache read error | Log warning, treat as cache miss |
| Cache write error | Log warning, response still returned to user |
| Corrupted cached data | Delete entry, treat as cache miss |

### 8.2 Implementation

```python
async def get(cache_key: str) -> Optional[Dict]:
    try:
        entry = await self._get_entry(cache_key)
        # ... expiration check ...
    except Exception as e:
        logger.warning(f"Cache read error: {e}")
        return None  # Treat as miss, proceed with LLM
```

---

## 9. Testing Strategy

### 9.1 Test Coverage

| Test Class | Tests | Purpose |
|------------|-------|---------|
| `TestCacheKeyGeneration` | `test_key_deterministic`, `test_key_unique_different_prompts`, `test_key_same_model_different_messages`, `test_key_different_models_same_message` | Key generation correctness |
| `TestLLMCache` | `test_set_and_get`, `test_get_expired_entry`, `test_get_nonexistent`, `test_cache_disabled`, `test_clear_all` | Cache operations |
| `TestLLMClientCaching` | `test_cache_hit_bypasses_llm`, `test_cache_miss_calls_llm`, `test_cache_disabled_calls_llm`, `test_tokens_recorded` | Integration |
| `TestCacheDB` | `test_db_connection`, `test_table_creation` | Database setup |

### 9.2 Mocking Strategy

- Mock `acompletion` for LLM call tests
- Use separate test cache database (in-memory SQLite)
- Clean up cache entries between tests

---

## 10. Performance Impact

### 10.1 Expected Metrics

| Metric | Without Cache | With Cache (Hit) | Improvement |
|--------|--------------|------------------|-------------|
| Response latency | 2-3 seconds | <10ms | ~300x faster |
| API cost | Full token cost | $0 | 100% savings |
| Throughput | Limited by LLM API | Limited by SQLite | Higher |

### 10.2 Cache Hit Rate Estimation

- **FAQ/Support queries:** 60-80% hit rate
- **Creative writing:** 10-20% hit rate (unique prompts)
- **Agent workflows:** 40-60% hit rate (repeated tool patterns)

---

## 11. File Structure

```
agent/
├── cache/
│   ├── __init__.py          # Exports LLMCache
│   └── llm_cache.py         # LLMCache class
│   └── keygen.py            # Cache key generation

models/
├── cache.py                 # LLMCacheEntry SQLAlchemy model

agent/llm/
├── client.py                # Modified with cache integration

core/
├── config.py                # Added LLM cache settings

tests/unit/
├── test_llm_cache.py        # Cache unit tests
```

---

## 12. Implementation Sequence

1. Add config variables to `core/config.py`
2. Create `LLMCacheEntry` model in `models/cache.py`
3. Create cache key generation in `agent/cache/keygen.py`
4. Create `LLMCache` class in `agent/cache/llm_cache.py`
5. Modify `LLMClient` to integrate cache
6. Add unit tests in `tests/unit/test_llm_cache.py`
7. Run full test suite

---

## 13. Future Enhancements (Not in this phase)

- Semantic similarity caching (embeddings-based)
- Redis backend for horizontal scaling
- Cache analytics dashboard
- Per-agent TTL configuration
- Cache warmup for common queries