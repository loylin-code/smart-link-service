"""
Authentication service for OAuth2 and JWT
"""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import secrets
import hashlib
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import User, Tenant, APIKey, UserRole, TenantStatus
from core.config import settings
from core.exceptions import AuthenticationError, AuthorizationError


# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """
    Authentication service handling:
    - Password hashing and verification
    - JWT token creation and validation
    - OAuth2 flows
    - API key validation
    """
    
    # JWT settings
    JWT_ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    REFRESH_TOKEN_EXPIRE_DAYS = 7
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    # ==================== Password Methods ====================
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against a hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)
    
    # ==================== JWT Token Methods ====================
    
    def create_access_token(
        self,
        user_id: str,
        tenant_id: str,
        role: str,
        email: str,
        permissions: Optional[List[str]] = None,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create JWT access token
        
        Args:
            user_id: User ID
            tenant_id: Tenant ID
            role: User role
            email: User email
            permissions: List of permissions
            expires_delta: Custom expiration time
            
        Returns:
            JWT token string
        """
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode = {
            "sub": user_id,
            "tenant_id": tenant_id,
            "role": role,
            "email": email,
            "permissions": permissions or [],
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        }
        
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=self.JWT_ALGORITHM
        )
        return encoded_jwt
    
    def create_refresh_token(
        self,
        user_id: str,
        tenant_id: str,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create JWT refresh token
        
        Args:
            user_id: User ID
            tenant_id: Tenant ID
            expires_delta: Custom expiration time
            
        Returns:
            JWT refresh token string
        """
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS)
        
        to_encode = {
            "sub": user_id,
            "tenant_id": tenant_id,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        }
        
        encoded_jwt = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=self.JWT_ALGORITHM
        )
        return encoded_jwt
    
    def decode_token(self, token: str) -> Dict[str, Any]:
        """
        Decode and validate JWT token
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded token payload
            
        Raises:
            AuthenticationError: If token is invalid
        """
        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[self.JWT_ALGORITHM]
            )
            return payload
        except JWTError as e:
            raise AuthenticationError(f"Invalid token: {str(e)}")
    
    def validate_access_token(self, token: str) -> Dict[str, Any]:
        """
        Validate access token and return payload
        
        Args:
            token: JWT access token
            
        Returns:
            Token payload
            
        Raises:
            AuthenticationError: If token is invalid or not an access token
        """
        payload = self.decode_token(token)
        
        if payload.get("type") != "access":
            raise AuthenticationError("Invalid token type. Expected access token.")
        
        return payload
    
    def validate_refresh_token(self, token: str) -> Dict[str, Any]:
        """
        Validate refresh token and return payload
        
        Args:
            token: JWT refresh token
            
        Returns:
            Token payload
            
        Raises:
            AuthenticationError: If token is invalid or not a refresh token
        """
        payload = self.decode_token(token)
        
        if payload.get("type") != "refresh":
            raise AuthenticationError("Invalid token type. Expected refresh token.")
        
        return payload
    
    # ==================== User Authentication ====================
    
    async def authenticate_user(
        self,
        email: str,
        password: str
    ) -> Optional[User]:
        """
        Authenticate user with email and password
        
        Args:
            email: User email
            password: User password
            
        Returns:
            User object if authenticated, None otherwise
        """
        # Find user by email
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            return None
        
        if not user.is_active:
            return None
        
        if not user.password_hash:
            # OAuth user, cannot authenticate with password
            return None
        
        if not self.verify_password(password, user.password_hash):
            return None
        
        # Update last login
        user.last_login = datetime.utcnow()
        user.login_count += 1
        await self.db.commit()
        
        return user
    
    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_user_permissions(self, user: User) -> List[str]:
        """
        Get user permissions based on role
        
        Args:
            user: User object
            
        Returns:
            List of permission strings
        """
        # Define permission matrix by role
        permissions_map = {
            UserRole.OWNER: [
                "tenant:read", "tenant:update", "tenant:delete",
                "user:create", "user:read", "user:update", "user:delete",
                "app:create", "app:read", "app:update", "app:delete", "app:execute",
                "conversation:create", "conversation:read", "conversation:delete",
                "resource:create", "resource:read", "resource:delete",
                "api_key:create", "api_key:read", "api_key:delete",
                "billing:read", "billing:update",
                "workflow:create", "workflow:read", "workflow:update", "workflow:delete",
            ],
            UserRole.ADMIN: [
                "user:create", "user:read", "user:update",
                "app:create", "app:read", "app:update", "app:delete", "app:execute",
                "conversation:create", "conversation:read", "conversation:delete",
                "resource:create", "resource:read", "resource:delete",
                "api_key:create", "api_key:read", "api_key:delete",
                "workflow:create", "workflow:read", "workflow:update", "workflow:delete",
            ],
            UserRole.DEVELOPER: [
                "app:create", "app:read", "app:update", "app:execute",
                "conversation:create", "conversation:read",
                "resource:create", "resource:read",
                "workflow:create", "workflow:read", "workflow:update",
            ],
            UserRole.VIEWER: [
                "app:read",
                "conversation:read",
                "resource:read",
                "workflow:read",
            ],
            UserRole.SERVICE: [
                "app:read", "app:execute",
                "conversation:create", "conversation:read",
            ],
        }
        
        return permissions_map.get(user.role, [])
    
    # ==================== OAuth2 Methods ====================
    
    async def get_or_create_oauth_user(
        self,
        provider: str,
        oauth_id: str,
        email: str,
        name: Optional[str] = None,
        avatar_url: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> User:
        """
        Get or create user from OAuth provider
        
        Args:
            provider: OAuth provider name (google, github, etc.)
            oauth_id: Provider-specific user ID
            email: User email
            name: User full name
            avatar_url: User avatar URL
            tenant_id: Tenant ID (required for new users)
            
        Returns:
            User object
        """
        # Try to find existing user by OAuth ID
        result = await self.db.execute(
            select(User).where(
                User.oauth_provider == provider,
                User.oauth_id == oauth_id
            )
        )
        user = result.scalar_one_or_none()
        
        if user:
            # Update user info
            if name:
                user.full_name = name
            if avatar_url:
                user.avatar_url = avatar_url
            user.last_login = datetime.utcnow()
            user.login_count += 1
            await self.db.commit()
            return user
        
        # Try to find by email
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalar_one_or_none()
        
        if user:
            # Link OAuth to existing user
            user.oauth_provider = provider
            user.oauth_id = oauth_id
            if avatar_url:
                user.avatar_url = avatar_url
            user.last_login = datetime.utcnow()
            user.login_count += 1
            await self.db.commit()
            return user
        
        # Create new user
        if not tenant_id:
            raise AuthenticationError("Tenant ID required for new OAuth users")
        
        # Verify tenant exists and is active
        result = await self.db.execute(
            select(Tenant).where(Tenant.id == tenant_id)
        )
        tenant = result.scalar_one_or_none()
        
        if not tenant:
            raise AuthenticationError(f"Tenant {tenant_id} not found")
        
        if tenant.status != TenantStatus.ACTIVE:
            raise AuthenticationError(f"Tenant {tenant_id} is not active")
        
        # Create user
        user = User(
            tenant_id=tenant_id,
            email=email,
            full_name=name,
            avatar_url=avatar_url,
            oauth_provider=provider,
            oauth_id=oauth_id,
            role=UserRole.DEVELOPER,
            is_active=True,
            is_verified=True,  # OAuth users are pre-verified
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        
        return user
    
    # ==================== API Key Methods ====================
    
    @staticmethod
    def generate_api_key() -> str:
        """Generate a secure API key"""
        return f"sk-{secrets.token_urlsafe(32)}"
    
    @staticmethod
    def hash_api_key(key: str) -> str:
        """Hash an API key for storage"""
        return hashlib.sha256(key.encode()).hexdigest()
    
    async def validate_api_key(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Validate API key and return context
        
        Args:
            key: API key string
            
        Returns:
            Dict with user_id, tenant_id, scopes if valid, None otherwise
        """
        # First check against master API key
        if key == settings.MASTER_API_KEY:
            return {
                "user_id": None,
                "tenant_id": None,
                "scopes": ["*"],
                "is_master": True
            }
        
        # Hash the key for lookup
        key_hash = self.hash_api_key(key)
        
        # Look up in database
        result = await self.db.execute(
            select(APIKey).where(
                APIKey.key_hash == key_hash,
                APIKey.is_active == True
            )
        )
        api_key = result.scalar_one_or_none()
        
        if not api_key:
            return None
        
        # Check expiration
        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            return None
        
        # Update last used
        api_key.last_used_at = datetime.utcnow()
        api_key.total_requests += 1
        await self.db.commit()
        
        return {
            "user_id": api_key.user_id,
            "tenant_id": api_key.tenant_id,
            "scopes": api_key.scopes,
            "is_master": False,
            "rate_limit": api_key.rate_limit
        }
    
    # ==================== Token Pair ====================
    
    async def create_token_pair(
        self,
        user: User
    ) -> Dict[str, Any]:
        """
        Create access and refresh token pair
        
        Args:
            user: User object
            
        Returns:
            Dict with access_token, refresh_token, token_type, expires_in
        """
        # Get tenant
        result = await self.db.execute(
            select(Tenant).where(Tenant.id == user.tenant_id)
        )
        tenant = result.scalar_one_or_none()
        
        if not tenant or tenant.status != TenantStatus.ACTIVE:
            raise AuthenticationError("Tenant not found or inactive")
        
        # Get permissions
        permissions = await self.get_user_permissions(user)
        
        # Create tokens
        access_token = self.create_access_token(
            user_id=user.id,
            tenant_id=user.tenant_id,
            role=user.role.value,
            email=user.email,
            permissions=permissions
        )
        
        refresh_token = self.create_refresh_token(
            user_id=user.id,
            tenant_id=user.tenant_id
        )
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": self.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "role": user.role.value,
                "tenant_id": user.tenant_id
            }
        }
    
    async def refresh_tokens(
        self,
        refresh_token: str
    ) -> Dict[str, Any]:
        """
        Refresh access token using refresh token
        
        Args:
            refresh_token: JWT refresh token
            
        Returns:
            New token pair
        """
        # Validate refresh token
        payload = self.validate_refresh_token(refresh_token)
        
        user_id = payload.get("sub")
        if not user_id:
            raise AuthenticationError("Invalid refresh token")
        
        # Get user
        user = await self.get_user_by_id(user_id)
        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive")
        
        # Create new token pair
        return await self.create_token_pair(user)