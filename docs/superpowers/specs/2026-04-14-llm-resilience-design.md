# LLM Resilience Design Spec

**Created:** 2026-04-14
**Phase:** 3 - Performance Optimization
**Status:** Ready for Implementation

---

## 1. Overview

### 1.1 Purpose

Implement retry logic for LLM API calls to handle transient failures (rate limits, timeouts, network errors). Currently, any LLM API failure immediately throws `LLMError` - retry logic will recover from temporary issues.

### 1.2 Goals

- Recover from transient LLM API failures automatically
- Respect API rate limit guidance (Retry-After header)
- Prevent cascade failures from temporary outages
- Maintain clear logging for retry attempts

### 1.3 Non-Goals

- Circuit breaker pattern (future enhancement)
- Request queuing/throttling
- Multi-provider fallback

---

## 2. Architecture

### 2.1 System Flow

```
LLM Request → RetryWrapper → Call LLM API → [Success: Return]
                                   → [Retryable Error: Wait + Retry]
                                   → [Max Retries: Raise LLMError]
```

### 2.2 Components

| Component | File | Purpose |
|-----------|------|---------|
| `RetryConfig` | `agent/llm/retry.py` | Retry settings and helpers |
| `LLMClient` | `agent/llm/client.py` (modified) | Retry wrapper integration |
| `Settings` | `core/config.py` (modified) | Retry config variables |

### 2.3 Retry Strategy

- **Max retries:** 3 (configurable)
- **Backoff:** Exponential (1s → 2s → 4s)
- **Max delay:** 10 seconds
- **Retry-After:** Respected when provided by API

---

## 3. Configuration

### 3.1 Settings (core/config.py)

```python
# LLM Retry Configuration
LLM_MAX_RETRIES: int = Field(
    default=3,
    description="Maximum retry attempts for LLM calls"
)
LLM_RETRY_BASE_DELAY: float = Field(
    default=1.0,
    description="Base delay for exponential backoff (seconds)"
)
LLM_RETRY_MAX_DELAY: float = Field(
    default=10.0,
    description="Maximum delay between retries (seconds)"
)
```

---

## 4. Error Classification

### 4.1 Retryable Errors

| Error Type | HTTP Code | Retryable? | Reason |
|------------|-----------|------------|--------|
| Rate Limit | 429 | ✅ Yes | Temporary - wait and retry |
| Timeout | - | ✅ Yes | Network/processing delay |
| Connection Error | - | ✅ Yes | Transient network issue |
| Server Error | 500, 502, 503 | ✅ Yes | Temporary server issue |

### 4.2 Non-Retryable Errors

| Error Type | HTTP Code | Retryable? | Reason |
|------------|-----------|------------|--------|
| Auth Error | 401, 403 | ❌ No | Permanent - credentials issue |
| Invalid Request | 400 | ❌ No | Permanent - bad input |
| Not Found | 404 | ❌ No | Permanent - resource missing |

---

## 5. Retry Logic

### 5.1 Exponential Backoff

```python
def calculate_backoff(attempt: int, base_delay: float = 1.0, max_delay: float = 10.0) -> float:
    """
    Calculate exponential backoff delay.
    
    Pattern:
    - Attempt 0: 1.0s
    - Attempt 1: 2.0s
    - Attempt 2: 4.0s
    - Capped at max_delay
    """
    delay = base_delay * (2 ** attempt)
    return min(delay, max_delay)
```

### 5.2 Retry-After Handling

```python
def get_wait_time(error: Exception, attempt: int) -> float:
    """
    Determine wait time before retry.
    
    Priority:
    1. Retry-After header (if present)
    2. Exponential backoff
    """
    # Check for Retry-After header
    if hasattr(error, 'retry_after') and error.retry_after:
        return float(error.retry_after)
    
    # Fall back to exponential backoff
    return calculate_backoff(attempt)
```

### 5.3 Retry Loop

```python
async def chat_with_retry(messages, ...):
    for attempt in range(max_retries + 1):  # 0, 1, 2, 3
        try:
            response = await self._call_llm(messages)
            return response
            
        except Exception as e:
            if not is_retryable_error(e):
                raise LLMError(f"Non-retryable error: {e}", provider=self.provider)
            
            if attempt >= max_retries:
                raise LLMError(
                    f"LLM failed after {max_retries} retries: {e}",
                    provider=self.provider
                )
            
            wait_time = get_wait_time(e, attempt)
            logger.warning(
                f"LLM call failed, retrying",
                extra={
                    "attempt": attempt + 1,
                    "max_retries": max_retries,
                    "error_type": type(e).__name__,
                    "wait_seconds": wait_time,
                }
            )
            await asyncio.sleep(wait_time)
```

---

## 6. Logging

### 6.1 Retry Attempt Logging

Each retry attempt logs a structured warning:

```json
{
  "timestamp": "2026-04-14T10:30:00Z",
  "level": "WARNING",
  "logger": "agent.llm.client",
  "message": "LLM call failed, retrying",
  "attempt": 1,
  "max_retries": 3,
  "error_type": "RateLimitError",
  "wait_seconds": 2.5
}
```

### 6.2 Final Failure Logging

When all retries exhausted:

```json
{
  "timestamp": "2026-04-14T10:30:15Z",
  "level": "ERROR",
  "logger": "agent.llm.client",
  "message": "LLM failed after 3 retries",
  "error_type": "TimeoutError",
  "total_wait_seconds": 7.0
}
```

---

## 7. Integration with Existing LLMClient

### 7.1 Modified chat() Method

The retry logic wraps the existing `_call_llm()` internal method:

```python
class LLMClient:
    def __init__(self, config=None):
        # ... existing init ...
        self.max_retries = settings.LLM_MAX_RETRIES
        self.retry_base_delay = settings.LLM_RETRY_BASE_DELAY
        self.retry_max_delay = settings.LLM_RETRY_MAX_DELAY
    
    async def chat(self, messages, ...):
        """Send chat request with retry logic"""
        # ... cache check (existing) ...
        
        # Retry loop
        for attempt in range(self.max_retries + 1):
            try:
                response = await self._execute_llm_call(messages, ...)
                # ... cache storage (existing) ...
                return response
            except Exception as e:
                # ... retry handling ...
    
    async def _execute_llm_call(self, messages, ...):
        """Internal method for actual LLM API call"""
        # ... existing acompletion call ...
```

---

## 8. Testing Strategy

### 8.1 Test Coverage

| Test Class | Tests | Purpose |
|------------|-------|---------|
| `TestBackoffCalculation` | 3 | Test exponential backoff math |
| `TestErrorClassification` | 4 | Test retryable vs non-retryable |
| `TestRetryAfterHeader` | 2 | Test header parsing |
| `TestLLMClientRetry` | 4 | Integration - retries happen correctly |

### 8.2 Mocking Strategy

- Mock `acompletion` to simulate failures
- Mock `asyncio.sleep` to avoid actual delays
- Test both retryable and non-retryable scenarios

---

## 9. Performance Impact

### 9.1 Latency Impact

| Scenario | Without Retry | With Retry | Notes |
|----------|--------------|------------|-------|
| Success (first call) | 2-3s | 2-3s | No difference |
| Rate limit (1 retry) | Error | ~3-5s | Recovered |
| Timeout (2 retries) | Error | ~5-7s | Recovered |
| All retries exhausted | Error | ~7s + Error | Failed with more attempts |

### 9.2 Success Rate Improvement

- **Before:** 0% recovery on transient failures
- **After:** 80-90% recovery on rate limits/timeout

---

## 10. File Structure

```
agent/llm/
├── retry.py              # NEW - retry helpers
├── client.py             # Modified - retry integration

core/
├── config.py             # Modified - retry settings

tests/unit/
├── test_llm_retry.py     # NEW - retry tests
```

---

## 11. Implementation Sequence

1. Add LLM retry config to `core/config.py`
2. Create `agent/llm/retry.py` with retry helpers
3. Modify `agent/llm/client.py` to add retry logic
4. Add unit tests in `tests/unit/test_llm_retry.py`
5. Run full test suite

---

## 12. Future Enhancements

- Circuit breaker pattern (stop retrying after consecutive failures)
- Multi-provider fallback (try different LLM on failure)
- Request queue with rate limit awareness
- Prometheus metrics for retry counts