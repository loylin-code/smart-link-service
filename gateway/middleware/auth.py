"""
Authentication middleware for API Key validation
"""
from typing import Optional
from fastapi import Request, HTTPException, status
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from core.config import settings
from core.security import verify_api_key


# API Key header scheme
api_key_header = APIKeyHeader(name=settings.API_KEY_HEADER, auto_error=False)


async def get_api_key(request: Request) -> Optional[str]:
    """
    Extract API key from request header
    
    Args:
        request: FastAPI request
        
    Returns:
        API key string or None
    """
    return await api_key_header(request)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Middleware for API key authentication
    Validates API key in request header
    """
    
    # Paths that don't require authentication
    PUBLIC_PATHS = {
        "/",
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/metrics"
    }
    
    async def dispatch(self, request: Request, call_next):
        """
        Process request through middleware
        
        Args:
            request: FastAPI request
            call_next: Next middleware/handler
            
        Returns:
            Response
        """
        # Skip authentication for public paths
        if request.url.path in self.PUBLIC_PATHS:
            return await call_next(request)
        
        # Skip authentication for WebSocket (handled separately)
        if request.url.path.startswith("/ws"):
            return await call_next(request)
        
        # Skip for static files
        if request.url.path.startswith("/static"):
            return await call_next(request)
        
        # Get API key from header
        api_key = await get_api_key(request)
        
        # Validate API key
        if not api_key:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "code": 401,
                    "message": "API key is required",
                    "detail": f"Provide API key in {settings.API_KEY_HEADER} header"
                }
            )
        
        if not verify_api_key(api_key):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "code": 403,
                    "message": "Invalid API key"
                }
            )
        
        # API key is valid, proceed
        response = await call_next(request)
        return response


async def verify_api_key_ws(websocket) -> bool:
    """
    Verify API key for WebSocket connections
    
    Args:
        websocket: WebSocket connection
        
    Returns:
        True if valid, False otherwise
    """
    # Get API key from query params or headers
    api_key = websocket.query_params.get("api_key")
    
    if not api_key:
        # Try to get from headers
        api_key = websocket.headers.get(settings.API_KEY_HEADER)
    
    if not api_key or not verify_api_key(api_key):
        return False
    
    return True