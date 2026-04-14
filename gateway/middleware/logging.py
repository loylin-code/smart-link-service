"""
Request logging middleware with structured JSON format
"""
import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from core.logging import get_logger

logger = get_logger("gateway.middleware.logging")


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Enhanced logging middleware with structured JSON format.
    
    Features:
    - JSON structured logging
    - request_id correlation from RequestIDMiddleware
    - tenant_id and user_id context
    - duration tracking in milliseconds
    - stdout + file dual output
    
    Note: Requires RequestIDMiddleware to be registered before this middleware
    """
    
    # Paths to exclude from logging
    EXCLUDE_PATHS = ['/health', '/metrics', '/docs', '/openapi.json', '/redoc']
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with structured logging"""
        
        # Skip excluded paths
        path = request.url.path
        if path in self.EXCLUDE_PATHS or path.startswith('/docs') or path.startswith('/openapi'):
            return await call_next(request)
        
        # Get context from request state (set by RequestIDMiddleware)
        request_id = getattr(request.state, 'request_id', 'unknown')
        tenant_id = getattr(request.state, 'tenant_id', None)
        user_id = getattr(request.state, 'user_id', None)
        
        start_time = time.time()
        
        # Log request started
        logger.info(
            "Request started",
            extra={
                'request_id': request_id,
                'tenant_id': tenant_id,
                'user_id': user_id,
                'path': path,
                'method': request.method,
            }
        )
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Log request completed
            logger.info(
                "Request completed",
                extra={
                    'request_id': request_id,
                    'tenant_id': tenant_id,
                    'user_id': user_id,
                    'path': path,
                    'method': request.method,
                    'status': response.status_code,
                    'duration_ms': duration_ms,
                }
            )
            
            # Add timing and request_id headers
            response.headers["X-Process-Time"] = str(duration_ms)
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Log request failed
            logger.error(
                "Request failed",
                extra={
                    'request_id': request_id,
                    'tenant_id': tenant_id,
                    'user_id': user_id,
                    'path': path,
                    'method': request.method,
                    'status': 500,
                    'duration_ms': duration_ms,
                },
                exc_info=True
            )
            
            raise