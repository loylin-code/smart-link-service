"""OAuth2 Authorization Code Flow 单元测试"""
import pytest
import sys
import os
from unittest.mock import AsyncMock, patch, MagicMock

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


class TestAuthorizationCodeFlowInitiate:
    """AuthorizationCodeFlow.initiate() 测试"""

    @pytest.mark.asyncio
    async def test_initiate_success(self, async_session):
        """测试成功发起 OAuth 授权流程"""
        from auth.flows.authorization_code import AuthorizationCodeFlow
        from auth.providers.registry import ProviderRegistry
        from auth.providers.google import GoogleOAuth2Provider
        
        # Configure provider
        ProviderRegistry._providers = {}
        ProviderRegistry._configs = {}
        ProviderRegistry.register("google", GoogleOAuth2Provider)
        ProviderRegistry.configure("google", client_id="test_client_id", client_secret="test_secret")
        
        flow = AuthorizationCodeFlow(async_session)
        
        result = await flow.initiate(
            provider="google",
            redirect_uri="http://localhost:8000/oauth/callback",
            tenant_id="tenant-123"
        )
        
        # Verify result structure
        assert "authorization_url" in result
        assert "state" in result
        assert "provider" in result
        
        # Verify URL contains expected parameters
        assert "https://accounts.google.com/o/oauth2/v2/auth" in result["authorization_url"]
        assert "state=" in result["authorization_url"]
        assert "redirect_uri=" in result["authorization_url"]
        assert result["provider"] == "google"
        
        # Verify state is a valid token
        assert result["state"] is not None
        assert len(result["state"]) >= 40  # token_urlsafe(32)

    @pytest.mark.asyncio
    async def test_initiate_provider_not_configured(self, async_session):
        """测试未配置 Provider 抛出异常"""
        from auth.flows.authorization_code import AuthorizationCodeFlow
        from auth.providers.registry import ProviderRegistry
        from core.exceptions import AuthenticationError
        
        # Clear registry
        ProviderRegistry._providers = {}
        ProviderRegistry._configs = {}
        
        flow = AuthorizationCodeFlow(async_session)
        
        with pytest.raises(AuthenticationError) as exc_info:
            await flow.initiate(
                provider="nonexistent",
                redirect_uri="http://localhost:8000/oauth/callback"
            )
        
        assert "not configured" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_initiate_without_tenant_id(self, async_session):
        """测试无 tenant_id 时正常发起 (tenant_id 可选)"""
        from auth.flows.authorization_code import AuthorizationCodeFlow
        from auth.providers.registry import ProviderRegistry
        from auth.providers.github import GitHubOAuth2Provider
        
        # Configure provider
        ProviderRegistry._providers = {}
        ProviderRegistry._configs = {}
        ProviderRegistry.register("github", GitHubOAuth2Provider)
        ProviderRegistry.configure("github", client_id="gh_client_id", client_secret="gh_secret")
        
        flow = AuthorizationCodeFlow(async_session)
        
        result = await flow.initiate(
            provider="github",
            redirect_uri="http://localhost:8000/oauth/github/callback"
        )
        
        assert "authorization_url" in result
        assert "state" in result
        assert result["provider"] == "github"


class TestAuthorizationCodeFlowCallback:
    """AuthorizationCodeFlow.handle_callback() 测试"""

    @pytest.mark.asyncio
    async def test_handle_callback_success(self, async_session):
        """测试成功处理 OAuth 回调"""
        from auth.flows.authorization_code import AuthorizationCodeFlow
        from auth.providers.registry import ProviderRegistry
        from auth.providers.google import GoogleOAuth2Provider
        from auth.providers.base import OAuth2Token, OAuth2UserInfo
        from services.auth_service import AuthService
        from models import User, Tenant, TenantStatus
        from unittest.mock import AsyncMock
        
        # Configure provider
        ProviderRegistry._providers = {}
        ProviderRegistry._configs = {}
        ProviderRegistry.register("google", GoogleOAuth2Provider)
        ProviderRegistry.configure("google", client_id="test_id", client_secret="test_secret")
        
        flow = AuthorizationCodeFlow(async_session)
        
        # First, initiate to create a state
        initiate_result = await flow.initiate(
            provider="google",
            redirect_uri="http://localhost:8000/oauth/callback",
            tenant_id="tenant-test-001"
        )
        state = initiate_result["state"]
        
        # Mock the provider's exchange_code and get_userinfo methods
        mock_token = OAuth2Token(access_token="test_access_token", expires_in=3600)
        mock_userinfo = OAuth2UserInfo(
            provider="google",
            provider_user_id="google_user_123",
            email="test@example.com",
            name="Test User",
            avatar_url="https://example.com/avatar.jpg",
            raw_data={}
        )
        
        # Create a test tenant first
        from sqlalchemy import select
        from models import Tenant, TenantStatus
        
        # Check if tenant exists, create if not
        tenant_result = await async_session.execute(
            select(Tenant).where(Tenant.id == "tenant-test-001")
        )
        tenant = tenant_result.scalar_one_or_none()
        
        if not tenant:
            tenant = Tenant(
                id="tenant-test-001",
                name="Test Tenant",
                slug="test-tenant",
                status=TenantStatus.ACTIVE
            )
            async_session.add(tenant)
            await async_session.commit()
        
        # Mock the GoogleOAuth2Provider class methods (not instance)
        with patch.object(GoogleOAuth2Provider, 'exchange_code', new_callable=AsyncMock, return_value=mock_token):
            with patch.object(GoogleOAuth2Provider, 'get_userinfo', new_callable=AsyncMock, return_value=mock_userinfo):
                
                # Now handle callback - should create user and return tokens
                result = await flow.handle_callback(
                    provider="google",
                    code="test_auth_code",
                    state=state
                )
                
                # Verify result structure
                assert "access_token" in result
                assert "refresh_token" in result
                assert "token_type" in result
                assert "expires_in" in result
                assert "user" in result
                
                assert result["token_type"] == "bearer"
                assert isinstance(result["expires_in"], int)

    @pytest.mark.asyncio
    async def test_handle_callback_invalid_state(self, async_session):
        """测试无效 state 抛出异常"""
        from auth.flows.authorization_code import AuthorizationCodeFlow
        from auth.providers.registry import ProviderRegistry
        from auth.providers.google import GoogleOAuth2Provider
        from core.exceptions import AuthenticationError
        
        # Configure provider
        ProviderRegistry._providers = {}
        ProviderRegistry._configs = {}
        ProviderRegistry.register("google", GoogleOAuth2Provider)
        ProviderRegistry.configure("google", client_id="test_id", client_secret="test_secret")
        
        flow = AuthorizationCodeFlow(async_session)
        
        with pytest.raises(AuthenticationError) as exc_info:
            await flow.handle_callback(
                provider="google",
                code="test_code",
                state="invalid_state_token"
            )
        
        assert "Invalid or expired state" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_handle_callback_provider_mismatch(self, async_session):
        """测试 Provider 不匹配抛出异常"""
        from auth.flows.authorization_code import AuthorizationCodeFlow
        from auth.providers.registry import ProviderRegistry
        from auth.providers.google import GoogleOAuth2Provider
        from auth.providers.github import GitHubOAuth2Provider
        from core.exceptions import AuthenticationError
        
        # Configure both providers
        ProviderRegistry._providers = {}
        ProviderRegistry._configs = {}
        ProviderRegistry.register("google", GoogleOAuth2Provider)
        ProviderRegistry.register("github", GitHubOAuth2Provider)
        ProviderRegistry.configure("google", client_id="g_id", client_secret="g_secret")
        ProviderRegistry.configure("github", client_id="gh_id", client_secret="gh_secret")
        
        flow = AuthorizationCodeFlow(async_session)
        
        # Initiate with google
        initiate_result = await flow.initiate(
            provider="google",
            redirect_uri="http://localhost:8000/oauth/callback",
            tenant_id="tenant-test"
        )
        state = initiate_result["state"]
        
        # Try to handle callback with github (wrong provider)
        with pytest.raises(AuthenticationError) as exc_info:
            await flow.handle_callback(
                provider="github",  # Wrong provider
                code="test_code",
                state=state
            )
        
        assert "Provider mismatch" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_handle_callback_missing_tenant_id(self, async_session):
        """测试缺少 tenant_id 抛出异常"""
        from auth.flows.authorization_code import AuthorizationCodeFlow
        from auth.providers.registry import ProviderRegistry
        from auth.providers.google import GoogleOAuth2Provider
        from auth.providers.base import OAuth2Token, OAuth2UserInfo
        from core.exceptions import AuthenticationError
        
        # Configure provider
        ProviderRegistry._providers = {}
        ProviderRegistry._configs = {}
        ProviderRegistry.register("google", GoogleOAuth2Provider)
        ProviderRegistry.configure("google", client_id="test_id", client_secret="test_secret")
        
        flow = AuthorizationCodeFlow(async_session)
        
        # Initiate WITHOUT tenant_id
        initiate_result = await flow.initiate(
            provider="google",
            redirect_uri="http://localhost:8000/oauth/callback"
            # No tenant_id
        )
        state = initiate_result["state"]
        
        mock_token = OAuth2Token(access_token="test_token", expires_in=3600)
        mock_userinfo = OAuth2UserInfo(
            provider="google",
            provider_user_id="google_user_xyz",
            email="newuser@example.com",
            name="New User",
            raw_data={}
        )
        
        # Mock the GoogleOAuth2Provider class methods
        with patch.object(GoogleOAuth2Provider, 'exchange_code', new_callable=AsyncMock, return_value=mock_token):
            with patch.object(GoogleOAuth2Provider, 'get_userinfo', new_callable=AsyncMock, return_value=mock_userinfo):
                # Should raise error because no tenant_id and user doesn't exist
                with pytest.raises(AuthenticationError) as exc_info:
                    await flow.handle_callback(
                        provider="google",
                        code="test_code",
                        state=state
                    )
                
                assert "Tenant ID required" in str(exc_info.value)