"""
Authentication API endpoints
OAuth2 + JWT authentication flows
"""
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, EmailStr, Field

from db.session import get_db
from services.auth_service import AuthService
from models import User, Tenant, UserRole, TenantStatus
from core.config import settings
from core.exceptions import AuthenticationError, AuthorizationError


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


@router.post("/oauth/{provider}")
async def oauth_login(
    provider: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Initiate OAuth login flow
    
    Returns the OAuth authorization URL for the specified provider.
    Supported providers: google, github, gitlab
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


@router.get("/oauth/{provider}/callback")
async def oauth_callback(
    provider: str,
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth callback endpoint
    
    Exchanges authorization code for user info and creates/updates user.
    """
    # TODO: Implement full OAuth flow
    # 1. Verify state matches
    # 2. Exchange code for access token
    # 3. Get user info from provider
    # 4. Create or update user
    # 5. Generate JWT tokens
    
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="OAuth callback not yet implemented. Use email/password login."
    )


@router.post("/oauth/callback")
async def oauth_callback_json(
    request: OAuthCallbackRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth callback endpoint (JSON body)
    
    For clients that prefer to handle the OAuth flow themselves.
    """
    auth_service = AuthService(db)
    
    # TODO: Implement full OAuth flow
    # For now, this is a placeholder
    
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="OAuth callback not yet implemented. Use email/password login."
    )


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