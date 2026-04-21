"""
Rate limiting middleware and utilities
"""
import time
from typing import Dict, Optional, Tuple
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import redis.asyncio as redis

from core.config import settings


class RateLimiter:
    """
    Redis-based rate limiter using sliding window algorithm
    """
    
    def __init__(self, redis_client: redis.Redis = None):
        self.redis = redis_client
        self.prefix = "ratelimit"
    
    async def check_rate(
        self,
        key: str,
        max_requests: int,
        window_seconds: int = 60
    ) -> Tuple[bool, int, int]:
        """
        Check if request is within rate limit
        
        Args:
            key: Unique identifier (e.g., tenant_id, user_id, ip)
            max_requests: Maximum requests allowed
            window_seconds: Time window in seconds
            
        Returns:
            Tuple of (allowed, remaining, retry_after)
        """
        # If no Redis, allow all requests (development mode)
        if not self.redis:
            return True, max_requests, 0
        
        redis_key = f"{self.prefix}:{key}"
        now = time.time()
        window_start = now - window_seconds
        
        # Use Redis pipeline for atomic operations
        pipe = self.redis.pipeline()
        
        # Remove old entries
        pipe.zremrangebyscore(redis_key, 0, window_start)
        # Count current entries
        pipe.zcard(redis_key)
        
        results = await pipe.execute()
        current_count = results[1]
        
        if current_count >= max_requests:
            # Get oldest entry to calculate retry_after
            oldest = await self.redis.zrange(redis_key, 0, 0, withscores=True)
            if oldest:
                retry_after = int(oldest[0][1] + window_seconds - now)
            else:
                retry_after = window_seconds
            return False, 0, max(1, retry_after)
        
        # Add current request
        await self.redis.zadd(redis_key, {str(now): now})
        await self.redis.expire(redis_key, window_seconds)
        
        remaining = max(0, max_requests - current_count - 1)
        return True, remaining, 0
    
    async def increment_usage(
        self,
        tenant_id: str,
        resource: str,
        amount: int = 1
    ):
        """Increment resource usage counter"""
        if not self.redis:
            return
        key = f"{self.prefix}:usage:{tenant_id}:{resource}"
        await self.redis.incrby(key, amount)
    
    async def get_usage(
        self,
        tenant_id: str,
        resource: str
    ) -> int:
        """Get current resource usage"""
        if not self.redis:
            return 0
        key = f"{self.prefix}:usage:{tenant_id}:{resource}"
        value = await self.redis.get(key)
        return int(value) if value else 0


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware
    """
    
    # Paths exempt from rate limiting
    EXEMPT_PATHS = {"/", "/health", "/docs", "/redoc", "/openapi.json", "/metrics"}
    
    def __init__(self, app, redis_client: redis.Redis = None):
        super().__init__(app)
        self.limiter = RateLimiter(redis_client)
        self.redis_available = redis_client is not None
    
    async def dispatch(self, request: Request, call_next):
        # Skip exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)
        
        # Skip WebSocket paths
        websocket_paths = ("/ws", "/smart-link-service/api/v1/ws", "/smart-link-service/api/v1/chat", "/smart-link-service/api/v1/stream")
        if request.url.path.startswith(websocket_paths):
            return await call_next(request)
        
        # Skip rate limiting if Redis is not available (development mode)
        if not self.redis_available:
            return await call_next(request)
        
        # Get rate limit key
        tenant_context = getattr(request.state, "tenant_context", None)
        
        if tenant_context and tenant_context.tenant_id:
            # Authenticated request - use tenant_id
            key = f"tenant:{tenant_context.tenant_id}"
            max_requests = settings.RATE_LIMIT_REQUESTS_PER_MINUTE
        else:
            # Unauthenticated - use IP
            forwarded = request.headers.get("X-Forwarded-For")
            ip = forwarded.split(",")[0].strip() if forwarded else request.client.host
            key = f"ip:{ip}"
            max_requests = settings.RATE_LIMIT_REQUESTS_PER_MINUTE // 2
        
        # Check rate limit
        allowed, remaining, retry_after = await self.limiter.check_rate(
            key,
            max_requests=max_requests,
            window_seconds=60
        )
        
        if not allowed:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "code": 429,
                    "message": "Rate limit exceeded",
                    "retry_after": retry_after
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0"
                }
            )
        
        # Add rate limit headers
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        
        return response


def check_permission(required_permission: str):
    """
    Dependency to check user permission
    """
    async def permission_checker(request: Request):
        tenant_context = getattr(request.state, "tenant_context", None)
        
        if not tenant_context:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required"
            )
        
        # Master key has all permissions
        if tenant_context.is_master:
            return tenant_context
        
        # Check if user has required permission
        if not tenant_context.has_scope(required_permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {required_permission}"
            )
        
        return tenant_context
    
    return permission_checker