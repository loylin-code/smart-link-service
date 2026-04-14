"""
Request ID Middleware - Adds unique identifier to each request
"""
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware that generates a unique request ID for each request.
    
    The request ID is:
    - Stored in request.state.request_id
    - Added to response headers as X-Request-ID
    - Available to exception handlers for error responses
    """
    
    async def dispatch(self, request: Request, call_next):
        # Generate unique request ID
        request_id = f"req_{uuid.uuid4().hex[:16]}"
        
        # Store in request state for access in handlers
        request.state.request_id = request_id
        
        # Process request
        response = await call_next(request)
        
        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response