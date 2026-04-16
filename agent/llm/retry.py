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
    error_str = str(error).lower()
    
    # LiteLLM rate limit error
    if 'RateLimitError' in error_name or 'rate' in error_str or '429' in error_str:
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
    if headers:
        retry_after_header = headers.get('retry-after')
        if retry_after_header:
            try:
                return float(retry_after_header)
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