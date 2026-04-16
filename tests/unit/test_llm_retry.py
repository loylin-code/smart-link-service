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

    def test_rate_limit_429_retryable(self):
        """HTTP 429 status code should be retryable"""
        class MockRateLimit(Exception):
            status_code = 429
        
        error = MockRateLimit("Too many requests")
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

    def test_extract_from_headers(self):
        """Should extract from headers dict"""
        class MockError(Exception):
            headers = {'retry-after': '3.0'}
        
        error = MockError("Rate limited")
        result = get_retry_after(error)
        assert result == 3.0


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

    def test_first_attempt_backoff(self):
        """First attempt should use base backoff"""
        error = Exception("Generic error")
        wait_time = get_wait_time(error, 0)
        assert wait_time == 1.0


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