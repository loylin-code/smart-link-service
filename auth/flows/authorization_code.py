"""Authorization Code Flow 处理器"""
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from auth.providers.registry import ProviderRegistry
from auth.providers.state import StateManager
from services.auth_service import AuthService
from core.exceptions import AuthenticationError


class AuthorizationCodeFlow:
    """Authorization Code Flow 处理器
    
    处理 OAuth2 Authorization Code Grant 流程:
    1. initiate() - 发起授权请求，生成授权 URL 和 state
    2. handle_callback() - 处理 OAuth provider 回调，完成用户登录
    """
    
    def __init__(self, db: AsyncSession):
        """初始化 Authorization Code Flow 处理器
        
        Args:
            db: 异步数据库会话
        """
        self.db = db
        self.state_manager = StateManager(db)
        self.auth_service = AuthService(db)
    
    async def initiate(
        self,
        provider: str,
        redirect_uri: str,
        tenant_id: Optional[str] = None
    ) -> Dict[str, str]:
        """发起 OAuth 授权流程
        
        Args:
            provider: OAuth provider 名称 (e.g., 'google', 'github')
            redirect_uri: OAuth callback URI
            tenant_id: 可选的 tenant ID，用于多租户场景
            
        Returns:
            Dict containing:
                - authorization_url: Provider 授权页面 URL
                - state: OAuth state 参数 (用于 CSRF 防护)
                - provider: Provider 名称
                
        Raises:
            AuthenticationError: Provider 未配置或不存在
        """
        # 1. 获取 Provider 实例
        provider_instance = ProviderRegistry.get_provider(provider)
        if not provider_instance:
            raise AuthenticationError(f"Provider '{provider}' not configured")
        
        # 2. 创建并存储 state
        state_record = await self.state_manager.create_state(
            provider=provider,
            redirect_uri=redirect_uri,
            tenant_id=tenant_id
        )
        state = state_record.state
        
        # 3. 构建授权 URL
        authorize_url = provider_instance.get_authorize_url(
            state=state,
            redirect_uri=redirect_uri
        )
        
        return {
            "authorization_url": authorize_url,
            "state": state,
            "provider": provider
        }
    
    async def handle_callback(
        self,
        provider: str,
        code: str,
        state: str
    ) -> Dict[str, Any]:
        """处理 OAuth 回调
        
        Args:
            provider: OAuth provider 名称
            code: Provider 返回的 authorization code
            state: OAuth state 参数
            
        Returns:
            Dict containing:
                - access_token: JWT access token
                - refresh_token: JWT refresh token
                - token_type: Token 类型 ('bearer')
                - expires_in: Access token 有效期 (秒)
                - user: 用户信息
                
        Raises:
            AuthenticationError: State 无效/过期、Provider 不匹配、缺少 tenant_id
        """
        # 1. 验证 state
        state_record = await self.state_manager.validate_state(state)
        if not state_record:
            raise AuthenticationError("Invalid or expired state")
        
        # 2. 确认 provider 匹配
        if state_record.provider != provider:
            raise AuthenticationError("Provider mismatch")
        
        # 3. 获取 Provider 实例
        provider_instance = ProviderRegistry.get_provider(provider)
        if not provider_instance:
            raise AuthenticationError(f"Provider '{provider}' not configured")
        
        # 4. 交换 code 获取 token
        oauth_token = await provider_instance.exchange_code(
            code=code,
            redirect_uri=state_record.redirect_uri
        )
        
        # 5. 获取用户信息
        userinfo = await provider_instance.get_userinfo(oauth_token)
        
        # 6. 创建或获取用户
        tenant_id = state_record.tenant_id
        if not tenant_id:
            raise AuthenticationError("Tenant ID required for OAuth users")
        
        user = await self.auth_service.get_or_create_oauth_user(
            provider=userinfo.provider,
            oauth_id=userinfo.provider_user_id,
            email=userinfo.email,
            name=userinfo.name,
            avatar_url=userinfo.avatar_url,
            tenant_id=tenant_id
        )
        
        # 7. 生成 JWT token pair
        tokens = await self.auth_service.create_token_pair(user)
        
        return tokens