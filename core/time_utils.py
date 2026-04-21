"""
Time utilities for UTC+8 timezone handling.

All timestamps in SmartLink should use UTC+8 (China Standard Time).
"""
from datetime import datetime, timezone, timedelta


# UTC+8 timezone (China Standard Time)
UTC8 = timezone(timedelta(hours=8))


def now_utc8() -> datetime:
    """
    Get current datetime in UTC+8 timezone.
    
    Returns:
        datetime with UTC+8 timezone
    """
    return datetime.now(UTC8)


def now_utc8_ts() -> int:
    """
    Get current Unix timestamp in milliseconds (UTC+8).
    
    Returns:
        Unix timestamp in milliseconds
    """
    return int(now_utc8().timestamp() * 1000)


def now_utc8_ts_seconds() -> float:
    """
    Get current Unix timestamp in seconds (UTC+8).
    
    Returns:
        Unix timestamp in seconds
    """
    return now_utc8().timestamp()


__all__ = [
    "UTC8",
    "now_utc8",
    "now_utc8_ts",
    "now_utc8_ts_seconds",
]