"""
Request logging middleware
"""
import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging HTTP requests
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Log request and response
        
        Args:
            request: FastAPI request
            call_next: Next middleware/handler
            
        Returns:
            Response
        """
        # Skip logging for health checks
        if request.url.path == "/health":
            return await call_next(request)
        
        # Log request
        start_time = time.time()
        
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration = time.time() - start_time
        
        # Log response
        print(
            f"{request.method} {request.url.path} "
            f"- Status: {response.status_code} "
            f"- Duration: {duration:.3f}s"
        )
        
        # Add timing header
        response.headers["X-Process-Time"] = str(duration)
        
        return response