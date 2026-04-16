# LLM Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement retry logic for LLM API calls with exponential backoff and Retry-After header support.

**Architecture:** Retry helpers in `agent/llm/retry.py` wrap LLM API calls. LLMClient uses retry loop on retryable errors (429, timeout, connection). Non-retryable errors (401, 400) fail immediately.

**Tech Stack:** Python asyncio, exponential backoff, LiteLLM error handling

---

## File Structure

| File | Action | Purpose |
|------|--------|---------|
| `agent/llm/retry.py` | Create | Retry helpers (backoff, error classification) |
| `agent/llm/client.py` | Modify | Add retry loop to chat() method |
| `core/config.py` | Modify | Add LLM retry config variables |
| `tests/unit/test_llm_retry.py` | Create | Unit tests (~13 tests) |

---

### Task 1: Add Configuration Variables

**Files:**
- Modify: `core/config.py`

- [ ] **Step 1: Add LLM retry configuration to Settings class**

Locate the `# LLM Retry Configuration` section in `core/config.py` (after LLM cache settings) and add:

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

- [ ] **Step 2: Verify settings import**

Run: `python -c "from core.config import settings; print(settings.LLM_MAX_RETRIES, settings.LLM_RETRY_BASE_DELAY, settings.LLM_RETRY_MAX_DELAY)"`
Expected: `3 1.0 10.0`

- [ ] **Step 3: Commit**

```bash
git add core/config.py
git commit -m "feat(config): add LLM retry configuration variables"
```

---

### Task 2: Create Retry Helpers Module

**Files:**
- Create: `agent/llm/retry.py`

- [ ] **Step 1: Create agent/llm/retry.py with retry helpers**

```python
"""
LLM retry logic helpers
"""
import asyncio
import logging
from typing import Optional

from core.config import settings

logger = logging.getLogger(__name__)


def calculate_backoff(
    attempt: int,
    base_delay: float = None,
    max_delay: float = None
) -> float:
    """
    Calculate exponential backoff delay.
    
    Pattern:
    - Attempt 0: base_delay (1.0s)
    - Attempt 1: 2 * base_delay (2.0s)
    - Attempt 2: 4 * base_delay (4.0s)
    - Capped at max_delay (10.0s)
    
    Args:
        attempt: Current retry attempt (0-indexed)
        base_delay: Base delay in seconds (default from settings)
        max_delay: Maximum delay cap (default from settings)
    
    Returns:
        Wait time in seconds
    """
    if base_delay is None:
        base_delay = settings.LLM_RETRY_BASE_DELAY
    if max_delay is None:
        max_delay = settings.LLM_RETRY_MAX_DELAY
    
    delay = base_delay * (2 ** attempt)
    return min(delay, max_delay)


def is_retryable_error(error: Exception) -> bool:
    """
    Determine if an error should trigger retry.
    
    Retryable errors:
    - Rate limit (HTTP 429)
    - Timeout errors
    - Connection errors
    - Server errors (500, 502, 503)
    
    Non-retryable errors:
    - Auth errors (401, 403)
    - Invalid request (400)
    - Not found (404)
    
    Args:
        error: Exception from LLM call
    
    Returns:
        True if error should trigger retry
    """
    # Check for common retryable error types
    error_name = type(error).__name__
    
    # LiteLLM rate limit error
    if 'RateLimitError' in error_name or 'rate' in str(error).lower():
        return True
    
    # Timeout and connection errors
    if isinstance(error, (asyncio.TimeoutError, TimeoutError)):
        return True
    
    if 'timeout' in error_name.lower() or 'connection' in error_name.lower():
        return True
    
    # Check HTTP status code if available
    status_code = getattr(error, 'status_code', None)
    if status_code:
        # Retryable: rate limit, server errors
        if status_code in [429, 500, 502, 503]:
            return True
        # Non-retryable: auth, bad request, not found
        if status_code in [400, 401, 403, 404]:
            return False
    
    # Default: retry unknown errors (transient failures are common)
    return True


def get_retry_after(error: Exception) -> Optional[float]:
    """
    Extract Retry-After header value from error.
    
    Some APIs (OpenAI, Anthropic) return a Retry-After header
    on 429 rate limit responses indicating when to retry.
    
    Args:
        error: Exception from LLM call
    
    Returns:
        Wait time in seconds, or None if not available
    """
    # Check for retry_after attribute (set by LiteLLM)
    retry_after = getattr(error, 'retry_after', None)
    if retry_after:
        try:
            return float(retry_after)
        except (TypeError, ValueError):
            pass
    
    # Check headers if available
    headers = getattr(error, 'headers', None)
    if headers and 'retry-after' in headers:
        try:
            return float(headers['retry-after'])
        except (TypeError, ValueError):
            pass
    
    return None


def get_wait_time(error: Exception, attempt: int) -> float:
    """
    Determine wait time before retry.
    
    Priority:
    1. Retry-After header (if present on error)
    2. Exponential backoff
    
    Args:
        error: Exception from LLM call
        attempt: Current retry attempt (0-indexed)
    
    Returns:
        Wait time in seconds
    """
    # Try Retry-After header first
    retry_after = get_retry_after(error)
    if retry_after is not None:
        return retry_after
    
    # Fall back to exponential backoff
    return calculate_backoff(attempt)


class RetryableError(Exception):
    """Wrapper for errors that should trigger retry"""
    def __init__(self, original_error: Exception, attempt: int):
        self.original_error = original_error
        self.attempt = attempt
        super().__init__(f"Retryable error on attempt {attempt}: {original_error}")
```

- [ ] **Step 2: Verify retry module import**

Run: `python -c "from agent.llm.retry import calculate_backoff, is_retryable_error; print('OK')"`
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add agent/llm/retry.py
git commit -m "feat(llm): add retry helpers module"
```

---

### Task 3: Write Unit Tests for Retry Helpers

**Files:**
- Create: `tests/unit/test_llm_retry.py`

- [ ] **Step 1: Create tests/unit/test_llm_retry.py**

```python
"""
LLM retry logic unit tests
"""
import pytest
import asyncio

from agent.llm.retry import (
    calculate_backoff,
    is_retryable_error,
    get_retry_after,
    get_wait_time,
)


class TestBackoffCalculation:
    """Test exponential backoff calculation"""

    def test_first_attempt_base_delay(self):
        """First attempt (0) should use base delay"""
        delay = calculate_backoff(0, base_delay=1.0, max_delay=10.0)
        assert delay == 1.0

    def test_second_attempt_doubled(self):
        """Second attempt (1) should be 2x base"""
        delay = calculate_backoff(1, base_delay=1.0, max_delay=10.0)
        assert delay == 2.0

    def test_third_attempt_quadrupled(self):
        """Third attempt (2) should be 4x base"""
        delay = calculate_backoff(2, base_delay=1.0, max_delay=10.0)
        assert delay == 4.0

    def test_cap_at_max_delay(self):
        """Large attempts should cap at max_delay"""
        delay = calculate_backoff(10, base_delay=1.0, max_delay=10.0)
        assert delay == 10.0

    def test_default_settings_values(self):
        """Should use settings defaults when not specified"""
        delay = calculate_backoff(0)
        assert delay == 1.0  # Default base_delay


class TestErrorClassification:
    """Test retryable vs non-retryable error detection"""

    def test_rate_limit_is_retryable(self):
        """Rate limit errors should be retryable"""
        # Mock rate limit error
        class MockRateLimitError(Exception):
            pass
        
        error = MockRateLimitError("Rate limit exceeded")
        # Name contains 'Rate' which should trigger retry
        assert is_retryable_error(error) is True

    def test_timeout_is_retryable(self):
        """Timeout errors should be retryable"""
        error = asyncio.TimeoutError()
        assert is_retryable_error(error) is True

    def test_auth_error_not_retryable(self):
        """401 auth errors should not be retryable"""
        class MockAuthError(Exception):
            status_code = 401
        
        error = MockAuthError("Unauthorized")
        assert is_retryable_error(error) is False

    def test_bad_request_not_retryable(self):
        """400 bad request errors should not be retryable"""
        class MockBadRequest(Exception):
            status_code = 400
        
        error = MockBadRequest("Invalid request")
        assert is_retryable_error(error) is False

    def test_server_error_is_retryable(self):
        """500 server errors should be retryable"""
        class MockServerError(Exception):
            status_code = 500
        
        error = MockServerError("Internal server error")
        assert is_retryable_error(error) is True


class TestRetryAfterHeader:
    """Test Retry-After header extraction"""

    def test_extract_retry_after_attribute(self):
        """Should extract retry_after attribute"""
        class MockError(Exception):
            retry_after = 2.5
        
        error = MockError("Rate limited")
        result = get_retry_after(error)
        assert result == 2.5

    def test_no_retry_after_returns_none(self):
        """Should return None if no retry_after"""
        error = Exception("Generic error")
        result = get_retry_after(error)
        assert result is None


class TestWaitTimeCalculation:
    """Test wait time determination"""

    def test_uses_retry_after_when_present(self):
        """Should use Retry-After value if available"""
        class MockError(Exception):
            retry_after = 5.0
        
        error = MockError("Rate limited")
        wait_time = get_wait_time(error, 0)
        assert wait_time == 5.0

    def test_uses_backoff_when_no_retry_after(self):
        """Should use backoff when Retry-After not available"""
        error = asyncio.TimeoutError()
        wait_time = get_wait_time(error, 1)
        assert wait_time == 2.0  # Second attempt backoff


class TestConfigSettings:
    """Test LLM retry configuration"""

    def test_settings_has_max_retries(self):
        """Settings should have LLM_MAX_RETRIES"""
        from core.config import settings
        assert hasattr(settings, 'LLM_MAX_RETRIES')
        assert settings.LLM_MAX_RETRIES == 3

    def test_settings_has_base_delay(self):
        """Settings should have LLM_RETRY_BASE_DELAY"""
        from core.config import settings
        assert hasattr(settings, 'LLM_RETRY_BASE_DELAY')
        assert settings.LLM_RETRY_BASE_DELAY == 1.0

    def test_settings_has_max_delay(self):
        """Settings should have LLM_RETRY_MAX_DELAY"""
        from core.config import settings
        assert hasattr(settings, 'LLM_RETRY_MAX_DELAY')
        assert settings.LLM_RETRY_MAX_DELAY == 10.0
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/unit/test_llm_retry.py -v`
Expected: 13 tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_llm_retry.py
git commit -m "test(llm): add unit tests for retry helpers"
```

---

### Task 4: Integrate Retry Logic into LLMClient

**Files:**
- Modify: `agent/llm/client.py`

- [ ] **Step 1: Add retry import to client.py**

Add at top of `agent/llm/client.py` (after existing imports):

```python
import asyncio
from agent.llm.retry import is_retryable_error, get_wait_time
```

- [ ] **Step 2: Modify __init__ to include retry config**

In the `LLMClient.__init__` method (around line 18-32), add after `self.model`:

```python
# Retry configuration
self.max_retries = settings.LLM_MAX_RETRIES
```

- [ ] **Step 3: Modify chat() method to add retry loop**

Replace the entire `chat()` method (lines 67-146). The new version adds retry logic while keeping cache integration:

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
    Send chat completion request with caching and retry.
    
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
    
    # Retry loop
    for attempt in range(self.max_retries + 1):
        try:
            # Build request
            request_params = {
                "model": self._get_model_string(),
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
            
            if tools:
                request_params["tools"] = tools
                request_params["tool_choice"] = tool_choice
            
            request_params.update(kwargs)
            
            # Call LLM
            response = await acompletion(**request_params)
            
            # Extract result
            message = response.choices[0].message
            
            result = {
                "content": message.content or "",
                "role": message.role,
            }
            
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
            # Check if retryable
            if not is_retryable_error(e):
                # Non-retryable error - raise immediately
                raise LLMError(
                    f"LLM request failed (non-retryable): {str(e)}",
                    provider=self.provider
                )
            
            # Check if max retries exhausted
            if attempt >= self.max_retries:
                raise LLMError(
                    f"LLM request failed after {self.max_retries} retries: {str(e)}",
                    provider=self.provider
                )
            
            # Calculate wait time
            wait_time = get_wait_time(e, attempt)
            
            # Log retry attempt
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(
                f"LLM call failed, retrying",
                extra={
                    "attempt": attempt + 1,
                    "max_retries": self.max_retries,
                    "error_type": type(e).__name__,
                    "error_message": str(e),
                    "wait_seconds": wait_time,
                    "provider": self.provider,
                    "model": self.model,
                }
            )
            
            # Wait before retry
            await asyncio.sleep(wait_time)
```

- [ ] **Step 4: Verify LLMClient import**

Run: `python -c "from agent.llm.client import LLMClient; print('OK')"`
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add agent/llm/client.py
git commit -m "feat(llm): add retry logic to LLMClient.chat"
```

---

### Task 5: Run Full Test Suite

**Files:**
- All modified files

- [ ] **Step 1: Run all unit tests**

Run: `pytest tests/unit/ -v`
Expected: All tests PASS (120 + 13 = 133 tests)

- [ ] **Step 2: Verify app imports**

Run: `python -c "from gateway.main import app; print('OK')"`
Expected: OK

- [ ] **Step 3: Final commit**

```bash
git add -A
git commit -m "feat(llm): complete LLM resilience implementation

- Retry logic with exponential backoff (1s → 2s → 4s)
- 3 retries max, 10s max delay cap
- Retryable: 429, timeouts, connection errors, 500s
- Non-retryable: 401, 400, 404
- Retry-After header support
- 13 unit tests for retry helpers

Phase 3 Performance Optimization - LLM Resilience complete."

Total tests: 133 (120 previous + 13 new)
```

---

## Self-Review Checklist

| Spec Section | Covered by Task |
|--------------|-----------------|
| 3.1 Settings | Task 1 |
| 4.1 Retryable Errors | Task 2 (is_retryable_error) |
| 4.2 Non-Retryable Errors | Task 2 |
| 5.1 Exponential Backoff | Task 2 (calculate_backoff) |
| 5.2 Retry-After | Task 2 (get_retry_after) |
| 5.3 Retry Loop | Task 4 (LLMClient.chat) |
| 6.1 Logging | Task 4 (logger.warning) |
| 8.1 Test Coverage | Task 3 (13 tests) |

**Placeholder Scan:** No TBD/TODO found

**Type Consistency:**
- `calculate_backoff(attempt, base_delay, max_delay)` signature consistent
- `is_retryable_error(error)` signature consistent
- `get_wait_time(error, attempt)` signature consistent