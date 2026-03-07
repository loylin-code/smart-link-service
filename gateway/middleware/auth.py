"""
Authentication middleware for API Key and JWT validation
"""
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from sqlalchemy import select

from core.config import settings
from core.exceptions import AuthenticationError
from db.session import async_session_maker
from models import APIKey, User, Tenant, TenantStatus
from services.auth_service import AuthService


# API Key header scheme
api_key_header = APIKeyHeader(name=settings.API_KEY_HEADER, auto_error=False)

# Bearer token scheme
bearer_scheme = HTTPBearer(auto_error=False)


class TenantContext:
    """Tenant context for request"""
    
    def __init__(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
        user: Optional[User] = None,
        tenant: Optional[Tenant] = None,
        scopes: Optional[list] = None,
        is_master: bool = False
    ):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.user = user
        self.tenant = tenant
        self.scopes = scopes or []
        self.is_master = is_master
    
    def has_scope(self, scope: str) -> bool:
        """Check if context has a specific scope"""
        if "*" in self.scopes:
            return True
        
        # Check exact match
        if scope in self.scopes:
            return True
        
        # Check wildcard (e.g., "app:*" matches "app:read")
        for s in self.scopes:
            if s.endswith(":*"):
                prefix = s[:-1]
                if scope.startswith(prefix):
                    return True
        
        return False


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Authentication middleware supporting:
    - API Key authentication (X-API-Key header)
    - JWT Bearer token authentication (Authorization: Bearer <token>)
    - Master API key for admin access
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
    
    # Paths that allow optional auth
    OPTIONAL_AUTH_PATHS = {
        # Add paths where auth is optional
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
        
        # Skip for auth endpoints (login, register, etc.)
        if request.url.path.startswith("/api/v1/auth"):
            # Except /me which requires auth
            if not request.url.path.endswith("/me"):
                return await call_next(request)
        
        # Try authentication methods in order
        tenant_context = None
        
        # 1. Try Bearer token (JWT)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
            tenant_context = await self._validate_jwt_token(token)
        
        # 2. Try API Key
        if not tenant_context:
            api_key = request.headers.get(settings.API_KEY_HEADER)
            if api_key:
                tenant_context = await self._validate_api_key(api_key)
        
        # Check if authentication is required
        if not tenant_context:
            if request.url.path not in self.OPTIONAL_AUTH_PATHS:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={
                        "code": 401,
                        "message": "Authentication required",
                        "detail": "Provide either a Bearer token or X-API-Key header"
                    },
                    headers={"WWW-Authenticate": "Bearer"}
                )
        
        # Store tenant context in request state
        if tenant_context:
            request.state.tenant_context = tenant_context
            request.state.user = tenant_context.user
            request.state.tenant = tenant_context.tenant
            request.state.tenant_id = tenant_context.tenant_id
            request.state.user_id = tenant_context.user_id
        
        # Proceed to next handler
        response = await call_next(request)
        return response
    
    async def _validate_jwt_token(self, token: str) -> Optional[TenantContext]:
        """
        Validate JWT Bearer token
        
        Args:
            token: JWT token string
            
        Returns:
            TenantContext if valid, None otherwise
        """
        try:
            async with async_session_maker() as db:
                auth_service = AuthService(db)
                payload = auth_service.validate_access_token(token)
                
                user_id = payload.get("sub")
                tenant_id = payload.get("tenant_id")
                scopes = payload.get("permissions", [])
                
                if not user_id:
                    return None
                
                # Get user and tenant
                result = await db.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                
                if not user or not user.is_active:
                    return None
                
                result = await db.execute(
                    select(Tenant).where(Tenant.id == tenant_id)
                )
                tenant = result.scalar_one_or_none()
                
                if not tenant or tenant.status != TenantStatus.ACTIVE:
                    return None
                
                return TenantContext(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    user=user,
                    tenant=tenant,
                    scopes=scopes
                )
                
        except Exception:
            return None
    
    async def _validate_api_key(self, api_key: str) -> Optional[TenantContext]:
        """
        Validate API key
        
        Args:
            api_key: API key string
            
        Returns:
            TenantContext if valid, None otherwise
        """
        try:
            async with async_session_maker() as db:
                auth_service = AuthService(db)
                key_info = await auth_service.validate_api_key(api_key)
                
                if not key_info:
                    return None
                
                tenant_id = key_info.get("tenant_id")
                user_id = key_info.get("user_id")
                scopes = key_info.get("scopes", [])
                is_master = key_info.get("is_master", False)
                
                user = None
                tenant = None
                
                if tenant_id:
                    result = await db.execute(
                        select(Tenant).where(Tenant.id == tenant_id)
                    )
                    tenant = result.scalar_one_or_none()
                    
                    if tenant and tenant.status != TenantStatus.ACTIVE:
                        return None
                
                if user_id:
                    result = await db.execute(
                        select(User).where(User.id == user_id)
                    )
                    user = result.scalar_one_or_none()
                
                return TenantContext(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    user=user,
                    tenant=tenant,
                    scopes=scopes,
                    is_master=is_master
                )
                
        except Exception:
            return None


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Simplified API Key middleware for backward compatibility
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
        api_key = request.headers.get(settings.API_KEY_HEADER)
        
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
        
        # Validate the key
        is_valid = await self._validate_key(api_key)
        
        if not is_valid:
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
    
    async def _validate_key(self, api_key: str) -> bool:
        """Validate API key"""
        # Check master key first
        if api_key == settings.MASTER_API_KEY:
            return True
        
        # Check database
        try:
            async with async_session_maker() as db:
                auth_service = AuthService(db)
                key_info = await auth_service.validate_api_key(api_key)
                return key_info is not None
        except Exception:
            return False


async def verify_api_key_ws(websocket) -> Optional[TenantContext]:
    """
    Verify API key for WebSocket connections
    
    Args:
        websocket: WebSocket connection
        
    Returns:
        TenantContext if valid, None otherwise
    """
    # Get API key from query params or headers
    api_key = websocket.query_params.get("api_key")
    
    if not api_key:
        # Try to get from headers
        api_key = websocket.headers.get(settings.API_KEY_HEADER)
    
    if not api_key:
        return None
    
    # Validate
    try:
        async with async_session_maker() as db:
            auth_service = AuthService(db)
            key_info = await auth_service.validate_api_key(api_key)
            
            if not key_info:
                return None
            
            return TenantContext(
                tenant_id=key_info.get("tenant_id"),
                user_id=key_info.get("user_id"),
                scopes=key_info.get("scopes", []),
                is_master=key_info.get("is_master", False)
            )
    except Exception:
        return None


async def verify_jwt_ws(websocket) -> Optional[TenantContext]:
    """
    Verify JWT token for WebSocket connections
    
    Args:
        websocket: WebSocket connection
        
    Returns:
        TenantContext if valid, None otherwise
    """
    # Get token from query params or headers
    token = websocket.query_params.get("token")
    
    if not token:
        # Try Authorization header
        auth_header = websocket.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
    
    if not token:
        return None
    
    # Validate
    try:
        async with async_session_maker() as db:
            auth_service = AuthService(db)
            payload = auth_service.validate_access_token(token)
            
            return TenantContext(
                tenant_id=payload.get("tenant_id"),
                user_id=payload.get("sub"),
                scopes=payload.get("permissions", [])
            )
    except Exception:
        return None


# Dependency for getting tenant context
async def get_tenant_context(request: Request) -> TenantContext:
    """
    Get tenant context from request state
    
    Raises HTTPException if not authenticated
    """
    context = getattr(request.state, "tenant_context", None)
    if not context:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return context


async def get_current_user(request: Request) -> User:
    """Get current user from request state"""
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return user


async def get_current_tenant(request: Request) -> Tenant:
    """Get current tenant from request state"""
    tenant = getattr(request.state, "tenant", None)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return tenant