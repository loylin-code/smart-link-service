"""Client Credentials Flow 处理器"""
from datetime import datetime, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import secrets
import hashlib
import json

from models.oauth import OAuthClient
from services.auth_service import AuthService
from core.exceptions import AuthenticationError


class ClientCredentialsFlow:
    """Client Credentials Flow 处理器
    
    用于 API 服务间认证 (machine-to-machine):
    1. authenticate() - 验证 client credentials 并颁发 token
    2. create_client() - 创建 OAuth 客户端 (管理员操作)
    """
    
    def __init__(self, db: AsyncSession):
        """初始化 Client Credentials Flow 处理器
        
        Args:
            db: 异步数据库会话
        """
        self.db: AsyncSession = db
        self.auth_service: AuthService = AuthService(db)
    
    async def authenticate(
        self,
        client_id: str,
        client_secret: str,
        scope: str | None = None
    ) -> dict[str, any]:
        """验证 client credentials 并颁发 token
        
        Args:
            client_id: OAuth 客户端 ID
            client_secret: OAuth 客户端 secret
            scope: 可选的 scope 参数
            
        Returns:
            Dict containing:
                - access_token: JWT access token
                - token_type: Token 类型 ('Bearer')
                - expires_in: Token 有效期 (秒)
                - scope: 授权的 scope
                
        Raises:
            AuthenticationError: client_id 无效、secret 无效、client 过期、scope 不允许
        """
        # 1. 验证 client credentials
        client = await self._validate_client(client_id, client_secret)
        
        # 2. 验证 scope
        allowed_scopes = json.loads(client.allowed_scopes) if client.allowed_scopes else []
        granted_scopes = self._validate_scope(allowed_scopes, scope)
        
        # 3. 创建服务账号 token (role="service")
        access_token = self.auth_service.create_access_token(
            user_id=client.id,
            tenant_id=client.tenant_id,
            role="service",
            email=client.name,
            permissions=granted_scopes,
            expires_delta=timedelta(hours=1)
        )
        
        # 4. 更新使用记录
        client.last_used_at = datetime.utcnow()
        client.total_requests += 1
        await self.db.commit()
        
        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": " ".join(granted_scopes)
        }
    
    async def _validate_client(
        self,
        client_id: str,
        client_secret: str
    ) -> OAuthClient:
        """验证客户端凭证
        
        Args:
            client_id: OAuth 客户端 ID
            client_secret: OAuth 客户端 secret
            
        Returns:
            OAuthClient 对象
            
        Raises:
            AuthenticationError: client_id 无效、secret 无效、client 过期
        """
        result = await self.db.execute(
            select(OAuthClient).where(
                OAuthClient.client_id == client_id,
                OAuthClient.is_active == True
            )
        )
        client = result.scalar_one_or_none()
        
        if not client:
            raise AuthenticationError("Invalid client_id")
        
        # 验证 secret (SHA-256 hash)
        secret_hash = hashlib.sha256(client_secret.encode()).hexdigest()
        if client.secret_hash != secret_hash:
            raise AuthenticationError("Invalid client_secret")
        
        # 检查过期
        if client.expires_at and client.expires_at < datetime.utcnow():
            raise AuthenticationError("Client credentials expired")
        
        return client
    
    def _validate_scope(
        self,
        allowed_scopes: list[str],
        requested_scope: str | None
    ) -> list[str]:
        """验证并返回授权的 scope
        
        Args:
            allowed_scopes: 客户端允许的 scope 列表
            requested_scope: 请求的 scope (空格分隔)
            
        Returns:
            授权的 scope 列表
            
        Raises:
            AuthenticationError: 请求了不允许的 scope
        """
        if not requested_scope:
            return allowed_scopes
        
        requested = requested_scope.split()
        allowed = set(allowed_scopes)
        
        granted = [s for s in requested if s in allowed]
        
        if len(granted) != len(requested):
            denied = [s for s in requested if s not in allowed]
            raise AuthenticationError(f"Scope not allowed: {denied}")
        
        return granted
    
    async def create_client(
        self,
        tenant_id: str,
        name: str,
        allowed_scopes: list[str],
        expires_days: int | None = 365
    ) -> dict[str, str]:
        """创建 OAuth 客户端（管理员操作）
        
        Args:
            tenant_id: 租户 ID
            name: 客户端名称
            allowed_scopes: 允许的 scope 列表
            expires_days: 过期天数 (None 表示永不过期)
            
        Returns:
            Dict containing:
                - client_id: 客户端 ID
                - client_secret: 客户端 secret (仅显示一次!)
        """
        client_id = f"client_{secrets.token_urlsafe(16)}"
        client_secret = secrets.token_urlsafe(32)
        secret_hash = hashlib.sha256(client_secret.encode()).hexdigest()
        
        expires_at = None
        if expires_days:
            expires_at = datetime.utcnow() + timedelta(days=expires_days)
        
        client = OAuthClient(
            tenant_id=tenant_id,
            client_id=client_id,
            secret_hash=secret_hash,
            name=name,
            allowed_scopes=json.dumps(allowed_scopes),
            is_active=True,
            expires_at=expires_at
        )
        self.db.add(client)
        await self.db.commit()
        
        return {
            "client_id": client_id,
            "client_secret": client_secret  # 仅显示一次！
        }