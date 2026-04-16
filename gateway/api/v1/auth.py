"""
Authentication API endpoints
OAuth2 + JWT authentication flows
"""
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr, Field
import json

from db.session import get_db
from services.auth_service import AuthService
from models import User, Tenant, UserRole, TenantStatus
from models.oauth import OAuthClient
from core.config import settings
from core.exceptions import AuthenticationError, AuthorizationError

# OAuth infrastructure imports
from auth.flows.authorization_code import AuthorizationCodeFlow
from auth.flows.client_credentials import ClientCredentialsFlow
from auth.callbacks.html_callback import HTMLCallbackHandler
from auth.providers.registry import ProviderRegistry


router = APIRouter(prefix="/auth", tags=["Authentication"])

# OAuth2 scheme for Swagger UI
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


# ==================== Schemas ====================

class LoginRequest(BaseModel):
    """Login request schema"""
    email: EmailStr
    password: str


class RegisterRequest(BaseModel):
    """Registration request schema"""
    email: EmailStr
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = None
    tenant_id: Optional[str] = None


class TokenResponse(BaseModel):
    """Token response schema"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class RefreshRequest(BaseModel):
    """Refresh token request"""
    refresh_token: str


class OAuthCallbackRequest(BaseModel):
    """OAuth callback request"""
    provider: str
    code: str
    state: Optional[str] = None


class OAuthInitiateRequest(BaseModel):
    """OAuth initiate request - Authorization Code Flow"""
    redirect_uri: str = Field(..., description="Frontend callback URL")
    tenant_id: Optional[str] = Field(None, description="Tenant ID for new users")


class ClientCredentialsRequest(BaseModel):
    """Client Credentials Flow request (OAuth2 standard)"""
    grant_type: str = Field(default="client_credentials", description="OAuth2 grant type")
    client_id: str = Field(..., description="OAuth client ID")
    client_secret: str = Field(..., description="OAuth client secret")
    scope: Optional[str] = Field(None, description="Requested scope (space-separated)")


class ClientCredentialsResponse(BaseModel):
    """Client Credentials Flow response"""
    access_token: str
    token_type: str = Field(default="Bearer")
    expires_in: int = Field(default=3600, description="Token expiry in seconds")
    scope: Optional[str] = None


class CreateOAuthClientRequest(BaseModel):
    """Create OAuth client request"""
    name: str = Field(..., min_length=1, max_length=255)
    allowed_scopes: List[str] = Field(..., min_length=1)
    expires_days: Optional[int] = Field(default=365, ge=1, le=3650)


class OAuthClientResponse(BaseModel):
    """OAuth client response"""
    id: str
    tenant_id: str
    client_id: str
    name: str
    allowed_scopes: List[str]
    is_active: bool
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    total_requests: int
    created_at: datetime


class UserResponse(BaseModel):
    """User response schema"""
    id: str
    email: str
    full_name: Optional[str]
    role: str
    tenant_id: str
    is_active: bool
    created_at: datetime


# ==================== Dependencies ====================

async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """
    Get current user from JWT token
    Returns None if no token provided (for optional auth)
    """
    if not token:
        return None
    
    auth_service = AuthService(db)
    try:
        payload = auth_service.validate_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        user = await auth_service.get_user_by_id(user_id)
        return user
    except AuthenticationError:
        return None


async def get_current_user_required(
    user: Optional[User] = Depends(get_current_user)
) -> User:
    """
    Get current user (required)
    Raises 401 if not authenticated
    """
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_tenant_context(
    user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Get tenant context for the current user
    Returns tenant info and validates tenant is active
    """
    from sqlalchemy import select
    
    result = await db.execute(
        select(Tenant).where(Tenant.id == user.tenant_id)
    )
    tenant = result.scalar_one_or_none()
    
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    if tenant.status != TenantStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant is not active"
        )
    
    return {
        "user": user,
        "tenant": tenant,
        "tenant_id": tenant.id
    }


# ==================== Endpoints ====================

@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth2 compatible login endpoint
    
    - **username**: User email
    - **password**: User password
    """
    auth_service = AuthService(db)
    
    # OAuth2 form uses 'username' field for email
    user = await auth_service.authenticate_user(
        email=form_data.username,
        password=form_data.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    tokens = await auth_service.create_token_pair(user)
    return TokenResponse(**tokens)


@router.post("/login/json", response_model=TokenResponse)
async def login_json(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    JSON login endpoint
    
    - **email**: User email
    - **password**: User password
    """
    auth_service = AuthService(db)
    
    user = await auth_service.authenticate_user(
        email=request.email,
        password=request.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    tokens = await auth_service.create_token_pair(user)
    return TokenResponse(**tokens)


@router.post("/register", response_model=TokenResponse)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Register a new user
    
    - **email**: User email
    - **password**: User password (min 8 chars)
    - **full_name**: Optional full name
    - **tenant_id**: Optional tenant ID (required if not using invitations)
    """
    from sqlalchemy import select
    
    auth_service = AuthService(db)
    
    # Check if user already exists
    result = await db.execute(
        select(User).where(User.email == request.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # If no tenant_id, we need to create a new tenant
    tenant_id = request.tenant_id
    if not tenant_id:
        # Create personal tenant
        tenant = Tenant(
            name=request.full_name or request.email.split("@")[0],
            slug=request.email.split("@")[0].lower(),
            status=TenantStatus.ACTIVE,
            billing_plan="free",
        )
        db.add(tenant)
        await db.flush()
        tenant_id = tenant.id
    
    # Verify tenant exists
    result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found"
        )
    
    # Create user
    user = User(
        tenant_id=tenant_id,
        email=request.email,
        password_hash=auth_service.hash_password(request.password),
        full_name=request.full_name,
        role=UserRole.OWNER if tenant.created_at == tenant.updated_at else UserRole.DEVELOPER,
        is_active=True,
        is_verified=False,  # Email verification required
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    
    # Create tokens
    tokens = await auth_service.create_token_pair(user)
    return TokenResponse(**tokens)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Refresh access token using refresh token
    
    - **refresh_token**: Valid refresh token
    """
    auth_service = AuthService(db)
    
    try:
        tokens = await auth_service.refresh_tokens(request.refresh_token)
        return TokenResponse(**tokens)
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/logout")
async def logout(
    user: User = Depends(get_current_user_required)
):
    """
    Logout current user
    
    In a production system, this would invalidate the token
    by adding it to a blacklist in Redis.
    """
    # TODO: Implement token blacklisting in Redis
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
async def get_me(
    user: User = Depends(get_current_user_required)
):
    """Get current user profile"""
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.value,
        tenant_id=user.tenant_id,
        is_active=user.is_active,
        created_at=user.created_at
    )


# ==================== OAuth2 Endpoints ====================

@router.post("/oauth/{provider}/initiate")
async def oauth_initiate(
    provider: str,
    request: OAuthInitiateRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Initiate OAuth authorization flow
    
    Returns authorization URL and state for frontend to redirect user to provider.
    
    - **provider**: OAuth provider name (google, github, gitlab)
    - **redirect_uri**: Frontend callback URL
    - **tenant_id**: Optional tenant ID for new users
    """
    flow = AuthorizationCodeFlow(db)
    callback_handler = HTMLCallbackHandler()
    
    try:
        # Build the backend callback URL (for provider to redirect back to)
        backend_callback_url = f"{settings.OAUTH_CALLBACK_BASE_URL}/{provider}/callback"
        
        result = await flow.initiate(
            provider=provider,
            redirect_uri=backend_callback_url,
            tenant_id=request.tenant_id
        )
        
        return result
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/oauth/{provider}/callback")
async def oauth_callback_html(
    provider: str,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth callback endpoint (HTML response)
    
    This is the endpoint that OAuth providers redirect to after user authorization.
    Returns an HTML page that:
    1. Displays success/error message
    2. Stores tokens in localStorage
    3. Redirects to frontend application
    """
    flow = AuthorizationCodeFlow(db)
    callback_handler = HTMLCallbackHandler()
    
    try:
        tokens = await flow.handle_callback(
            provider=provider,
            code=code,
            state=state
        )
        
        return callback_handler.success_response(
            tokens=tokens,
            state=state,
            provider=provider
        )
    except AuthenticationError as e:
        return callback_handler.error_response(
            error="authentication_error",
            error_description=str(e),
            provider=provider
        )


@router.post("/oauth/{provider}/callback")
async def oauth_callback_json(
    provider: str,
    request: OAuthCallbackRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth callback endpoint (JSON response)
    
    Alternative endpoint for clients that prefer JSON response over HTML.
    Requires the frontend to handle the OAuth flow manually.
    
    - **provider**: OAuth provider name
    - **code**: Authorization code from provider
    - **state**: State parameter (must match stored state)
    """
    flow = AuthorizationCodeFlow(db)
    
    try:
        tokens = await flow.handle_callback(
            provider=provider,
            code=request.code,
            state=request.state or ""
        )
        
        return TokenResponse(**tokens)
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


# ==================== Client Credentials Flow ====================

@router.post("/oauth/token", response_model=ClientCredentialsResponse)
async def oauth_token(
    request: ClientCredentialsRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth2 Token Endpoint - Client Credentials Flow
    
    Standard OAuth2 endpoint for service-to-service authentication.
    
    - **grant_type**: Must be "client_credentials"
    - **client_id**: OAuth client ID
    - **client_secret**: OAuth client secret
    - **scope**: Optional scope parameter
    """
    if request.grant_type != "client_credentials":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported grant_type: {request.grant_type}"
        )
    
    flow = ClientCredentialsFlow(db)
    
    try:
        result = await flow.authenticate(
            client_id=request.client_id,
            client_secret=request.client_secret,
            scope=request.scope
        )
        
        return ClientCredentialsResponse(**result)
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


# ==================== OAuth Client Management ====================

@router.post("/oauth/clients")
async def create_oauth_client(
    request: CreateOAuthClientRequest,
    user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db)
):
    """
    Create OAuth client (requires authentication)
    
    Creates a new OAuth client for Client Credentials Flow.
    Returns client_id and client_secret - **secret is shown only once!**
    
    - **name**: Client name/identifier
    - **allowed_scopes**: List of allowed scopes
    - **expires_days**: Days until expiration (default: 365)
    """
    flow = ClientCredentialsFlow(db)
    
    result = await flow.create_client(
        tenant_id=user.tenant_id,
        name=request.name,
        allowed_scopes=request.allowed_scopes,
        expires_days=request.expires_days
    )
    
    return {
        "client_id": result["client_id"],
        "client_secret": result["client_secret"],
        "message": "Store the client_secret securely - it will not be shown again!"
    }


@router.get("/oauth/clients", response_model=List[OAuthClientResponse])
async def list_oauth_clients(
    user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db)
):
    """
    List OAuth clients for current tenant
    
    Returns all OAuth clients belonging to the user's tenant.
    """
    result = await db.execute(
        select(OAuthClient).where(
            OAuthClient.tenant_id == user.tenant_id
        ).order_by(OAuthClient.created_at.desc())
    )
    clients = result.scalars().all()
    
    return [
        OAuthClientResponse(
            id=client.id,
            tenant_id=client.tenant_id,
            client_id=client.client_id,
            name=client.name,
            allowed_scopes=json.loads(client.allowed_scopes) if client.allowed_scopes else [],
            is_active=client.is_active,
            expires_at=client.expires_at,
            last_used_at=client.last_used_at,
            total_requests=client.total_requests,
            created_at=client.created_at
        )
        for client in clients
    ]


@router.delete("/oauth/clients/{client_id}")
async def delete_oauth_client(
    client_id: str,
    user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete OAuth client
    
    Deletes an OAuth client. Only clients belonging to the user's tenant can be deleted.
    
    - **client_id**: OAuth client ID to delete
    """
    result = await db.execute(
        select(OAuthClient).where(
            OAuthClient.client_id == client_id,
            OAuthClient.tenant_id == user.tenant_id
        )
    )
    client = result.scalar_one_or_none()
    
    if not client:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="OAuth client not found"
        )
    
    await db.delete(client)
    await db.commit()
    
    return {"message": "OAuth client deleted successfully"}


# ==================== Legacy OAuth Endpoint (Deprecated) ====================

@router.post("/oauth/{provider}", deprecated=True)
async def oauth_login_legacy(
    provider: str,
    db: AsyncSession = Depends(get_db)
):
    """
    [DEPRECATED] Use /oauth/{provider}/initiate instead
    
    Initiate OAuth login flow - legacy endpoint for backward compatibility.
    """
    # OAuth configuration
    oauth_configs = {
        "google": {
            "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
            "client_id": settings.GOOGLE_CLIENT_ID,
            "scope": "openid email profile",
        },
        "github": {
            "auth_url": "https://github.com/login/oauth/authorize",
            "client_id": settings.GITHUB_CLIENT_ID,
            "scope": "user:email",
        },
        "gitlab": {
            "auth_url": "https://gitlab.com/oauth/authorize",
            "client_id": settings.GITLAB_CLIENT_ID,
            "scope": "read_user",
        }
    }
    
    if provider not in oauth_configs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported OAuth provider: {provider}"
        )
    
    config = oauth_configs[provider]
    
    if not config["client_id"]:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"OAuth provider {provider} not configured"
        )
    
    # Build authorization URL
    from urllib.parse import urlencode
    import secrets
    
    state = secrets.token_urlsafe(16)
    
    params = {
        "client_id": config["client_id"],
        "redirect_uri": f"{settings.API_BASE_URL}/api/v1/auth/oauth/{provider}/callback",
        "response_type": "code",
        "scope": config["scope"],
        "state": state,
    }
    
    auth_url = f"{config['auth_url']}?{urlencode(params)}"
    
    return {
        "authorization_url": auth_url,
        "state": state,
        "provider": provider
    }


@router.post("/verify-email")
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Verify email address using token
    
    - **token**: Email verification token sent to user's email
    """
    # TODO: Implement email verification
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Email verification not yet implemented"
    )


@router.post("/forgot-password")
async def forgot_password(
    email: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Request password reset
    
    Sends a password reset link to the user's email.
    """
    # TODO: Implement password reset
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Password reset not yet implemented"
    )


@router.post("/reset-password")
async def reset_password(
    token: str,
    new_password: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Reset password using token
    
    - **token**: Password reset token from email
    - **new_password**: New password
    """
    # TODO: Implement password reset
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Password reset not yet implemented"
    )