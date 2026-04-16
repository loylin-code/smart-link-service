"""OAuth2 Provider 单元测试"""
import pytest
import sys
import os
from unittest.mock import AsyncMock, patch, MagicMock
from pydantic import ValidationError

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))


class TestOAuth2Token:
    """OAuth2Token 模型测试"""

    def test_create_token_valid(self):
        """测试创建有效的 token"""
        from auth.providers.base import OAuth2Token
        
        token = OAuth2Token(
            access_token="test_access_token",
            refresh_token="test_refresh_token",
            token_type="Bearer",
            expires_in=3600,
            scope="read write"
        )
        
        assert token.access_token == "test_access_token"
        assert token.refresh_token == "test_refresh_token"
        assert token.token_type == "Bearer"
        assert token.expires_in == 3600
        assert token.scope == "read write"

    def test_create_token_minimal(self):
        """测试创建最小化 token (只有必需字段)"""
        from auth.providers.base import OAuth2Token
        
        token = OAuth2Token(
            access_token="test_access_token",
            expires_in=3600
        )
        
        assert token.access_token == "test_access_token"
        assert token.refresh_token is None
        assert token.token_type == "Bearer"
        assert token.expires_in == 3600
        assert token.scope is None


class TestOAuth2UserInfo:
    """OAuth2UserInfo 模型测试"""

    def test_create_userinfo_valid(self):
        """测试创建完整的 userinfo"""
        from auth.providers.base import OAuth2UserInfo
        
        userinfo = OAuth2UserInfo(
            provider="google",
            provider_user_id="123456789",
            email="test@example.com",
            name="Test User",
            avatar_url="https://example.com/avatar.jpg",
            raw_data={"id": "123456789", "email": "test@example.com"}
        )
        
        assert userinfo.provider == "google"
        assert userinfo.provider_user_id == "123456789"
        assert userinfo.email == "test@example.com"
        assert userinfo.name == "Test User"
        assert userinfo.avatar_url == "https://example.com/avatar.jpg"

    def test_create_userinfo_minimal(self):
        """测试创建最小化 userinfo"""
        from auth.providers.base import OAuth2UserInfo
        
        userinfo = OAuth2UserInfo(
            provider="github",
            provider_user_id="987654321",
            email="user@example.com",
            raw_data={}
        )
        
        assert userinfo.provider == "github"
        assert userinfo.email == "user@example.com"
        assert userinfo.name is None
        assert userinfo.avatar_url is None


class TestBaseOAuth2Provider:
    """BaseOAuth2Provider 抽象类测试"""

    def test_cannot_instantiate_abstract(self):
        """测试不能直接实例化抽象类"""
        from auth.providers.base import BaseOAuth2Provider
        
        with pytest.raises(TypeError):
            BaseOAuth2Provider()

    @pytest.mark.asyncio
    async def test_google_provider_authorize_url(self):
        """测试 Google Provider 生成授权 URL"""
        from auth.providers.google import GoogleOAuth2Provider
        
        provider = GoogleOAuth2Provider(
            client_id="google-client-id",
            client_secret="google-client-secret"
        )
        
        url = provider.get_authorize_url(
            state="test_state_123",
            redirect_uri="http://localhost:8000/callback"
        )
        
        assert "https://accounts.google.com/o/oauth2/v2/auth" in url
        assert "client_id=google-client-id" in url
        assert "state=test_state_123" in url
        assert "redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fcallback" in url
        assert "scope=openid+email+profile" in url or "scope=email+openid+profile" in url or "scope=openid+profile+email" in url
        assert "response_type=code" in url

    @pytest.mark.asyncio
    async def test_google_provider_exchange_code(self):
        """测试 Google Provider 交换 token"""
        from auth.providers.google import GoogleOAuth2Provider, OAuth2Token
        import httpx
        
        provider = GoogleOAuth2Provider(
            client_id="google-client-id",
            client_secret="google-client-secret"
        )
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "ya29.access_token",
            "refresh_token": "1//09.refresh_token",
            "token_type": "Bearer",
            "expires_in": 3599,
            "scope": "openid email profile"
        }
        
        with patch.object(httpx, 'AsyncClient', autospec=True) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client
            
            token = await provider.exchange_code(
                code="auth_code_xyz",
                redirect_uri="http://localhost:8000/callback"
            )
            
            assert isinstance(token, OAuth2Token)
            assert token.access_token == "ya29.access_token"
            assert token.refresh_token == "1//09.refresh_token"
            assert token.token_type == "Bearer"
            assert token.expires_in == 3599

    @pytest.mark.asyncio
    async def test_google_provider_get_userinfo(self):
        """测试 Google Provider 获取用户信息"""
        from auth.providers.google import GoogleOAuth2Provider, OAuth2Token, OAuth2UserInfo
        
        provider = GoogleOAuth2Provider(
            client_id="google-client-id",
            client_secret="google-client-secret"
        )
        
        token = OAuth2Token(access_token="ya29.test_token", expires_in=3600)
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "123456789",
            "email": "user@gmail.com",
            "name": "Google User",
            "picture": "https://lh3.googleusercontent.com/avatar.jpg"
        }
        
        import httpx
        with patch.object(httpx, 'AsyncClient', autospec=True) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client
            
            userinfo = await provider.get_userinfo(token)
            
            assert isinstance(userinfo, OAuth2UserInfo)
            assert userinfo.provider == "google"
            assert userinfo.provider_user_id == "123456789"
            assert userinfo.email == "user@gmail.com"
            assert userinfo.name == "Google User"
            assert userinfo.avatar_url == "https://lh3.googleusercontent.com/avatar.jpg"

    @pytest.mark.asyncio
    async def test_github_provider_authorize_url(self):
        """测试 GitHub Provider 生成授权 URL"""
        from auth.providers.github import GitHubOAuth2Provider
        
        provider = GitHubOAuth2Provider(
            client_id="github-client-id",
            client_secret="github-client-secret"
        )
        
        url = provider.get_authorize_url(
            state="github_state_456",
            redirect_uri="http://localhost:8000/oauth/github/callback"
        )
        
        assert "https://github.com/login/oauth/authorize" in url
        assert "client_id=github-client-id" in url
        assert "state=github_state_456" in url
        assert "scope=user%3Aemail" in url  # URL encoded

    @pytest.mark.asyncio
    async def test_github_provider_exchange_code(self):
        """测试 GitHub Provider 交换 token"""
        from auth.providers.github import GitHubOAuth2Provider, OAuth2Token
        import httpx
        
        provider = GitHubOAuth2Provider(
            client_id="github-client-id",
            client_secret="github-client-secret"
        )
        
        # GitHub returns JSON when Accept: application/json header is set
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "gho_abc123",
            "token_type": "Bearer",
            "scope": "user:email"
        }
        
        with patch.object(httpx, 'AsyncClient', autospec=True) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client
            
            token = await provider.exchange_code(
                code="github_auth_code",
                redirect_uri="http://localhost:8000/oauth/github/callback"
            )
            
            assert isinstance(token, OAuth2Token)
            assert token.access_token == "gho_abc123"
            assert token.token_type == "Bearer"
            assert token.expires_in == 0  # GitHub tokens don't expire

    @pytest.mark.asyncio
    async def test_github_provider_get_userinfo(self):
        """测试 GitHub Provider 获取用户信息"""
        from auth.providers.github import GitHubOAuth2Provider, OAuth2Token, OAuth2UserInfo
        import httpx
        
        provider = GitHubOAuth2Provider(
            client_id="github-client-id",
            client_secret="github-client-secret"
        )
        
        token = OAuth2Token(access_token="gho_test_token", expires_in=0)
        
        # Mock user response (with email in user data)
        mock_user_response = MagicMock()
        mock_user_response.json.return_value = {
            "id": 123456,
            "login": "githubuser",
            "name": "GitHub User",
            "email": "github@example.com",
            "avatar_url": "https://avatars.githubusercontent.com/u/123456?v=4"
        }
        
        # Mock email response (not called since email is in user data)
        mock_email_response = MagicMock()
        mock_email_response.json.return_value = [
            {"email": "primary@example.com", "primary": True, "verified": True}
        ]
        
        with patch.object(httpx, 'AsyncClient', autospec=True) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.side_effect = [mock_user_response]  # Only user endpoint called
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client
            
            userinfo = await provider.get_userinfo(token)
            
            assert isinstance(userinfo, OAuth2UserInfo)
            assert userinfo.provider == "github"
            assert userinfo.provider_user_id == "123456"
            assert userinfo.email == "github@example.com"  # Uses email from user data
            assert userinfo.name == "GitHub User"
            assert userinfo.avatar_url == "https://avatars.githubusercontent.com/u/123456?v=4"

    @pytest.mark.asyncio
    async def test_gitlab_provider_authorize_url(self):
        """测试 GitLab Provider 生成授权 URL"""
        from auth.providers.gitlab import GitLabOAuth2Provider
        
        provider = GitLabOAuth2Provider(
            client_id="gitlab-client-id",
            client_secret="gitlab-client-secret"
        )
        
        url = provider.get_authorize_url(
            state="gitlab_state_789",
            redirect_uri="http://localhost:8000/oauth/gitlab/callback"
        )
        
        assert "https://gitlab.com/oauth/authorize" in url
        assert "client_id=gitlab-client-id" in url
        assert "state=gitlab_state_789" in url
        assert "scope=read_user" in url
        assert "response_type=code" in url

    @pytest.mark.asyncio
    async def test_gitlab_provider_exchange_code(self):
        """测试 GitLab Provider 交换 token"""
        from auth.providers.gitlab import GitLabOAuth2Provider, OAuth2Token
        import httpx
        
        provider = GitLabOAuth2Provider(
            client_id="gitlab-client-id",
            client_secret="gitlab-client-secret"
        )
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "glpat-abcdefghijklmnop",
            "token_type": "Bearer",
            "expires_in": 7200,
            "refresh_token": "glpat-refresh-xyz",
            "scope": "read_user"
        }
        
        with patch.object(httpx, 'AsyncClient', autospec=True) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client
            
            token = await provider.exchange_code(
                code="gitlab_auth_code",
                redirect_uri="http://localhost:8000/oauth/gitlab/callback"
            )
            
            assert isinstance(token, OAuth2Token)
            assert token.access_token == "glpat-abcdefghijklmnop"
            assert token.token_type == "Bearer"
            assert token.expires_in == 7200
            assert token.refresh_token == "glpat-refresh-xyz"

    @pytest.mark.asyncio
    async def test_gitlab_provider_get_userinfo(self):
        """测试 GitLab Provider 获取用户信息"""
        from auth.providers.gitlab import GitLabOAuth2Provider, OAuth2Token, OAuth2UserInfo
        import httpx
        
        provider = GitLabOAuth2Provider(
            client_id="gitlab-client-id",
            client_secret="gitlab-client-secret"
        )
        
        token = OAuth2Token(access_token="glpat_test", expires_in=7200)
        
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": 789012,
            "username": "gitlabuser",
            "name": "GitLab User",
            "email": "gitlab@example.com",
            "avatar_url": "https://secure.gravatar.com/avatar/abc123"
        }
        
        with patch.object(httpx, 'AsyncClient', autospec=True) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_class.return_value = mock_client
            
            userinfo = await provider.get_userinfo(token)
            
            assert isinstance(userinfo, OAuth2UserInfo)
            assert userinfo.provider == "gitlab"
            assert userinfo.provider_user_id == "789012"
            assert userinfo.email == "gitlab@example.com"
            assert userinfo.name == "GitLab User"


class TestProviderRegistry:
    """ProviderRegistry 注册表测试"""

    def test_register_and_get_provider(self):
        """测试注册和获取 provider"""
        from auth.providers.registry import ProviderRegistry
        from auth.providers.google import GoogleOAuth2Provider
        
        # Clear registry first
        ProviderRegistry._providers = {}
        ProviderRegistry._configs = {}
        
        ProviderRegistry.register("google", GoogleOAuth2Provider)
        ProviderRegistry.configure("google", client_id="test_id", client_secret="test_secret")
        
        provider = ProviderRegistry.get_provider("google")
        
        assert provider is not None
        assert isinstance(provider, GoogleOAuth2Provider)
        assert provider.client_id == "test_id"
        assert provider.client_secret == "test_secret"

    def test_get_unregistered_provider(self):
        """测试获取未注册的 provider 返回 None"""
        from auth.providers.registry import ProviderRegistry
        
        ProviderRegistry._providers = {}
        ProviderRegistry._configs = {}
        
        provider = ProviderRegistry.get_provider("nonexistent")
        
        assert provider is None

    def test_get_provider_not_configured(self):
        """测试获取未配置的 provider 返回 None"""
        from auth.providers.registry import ProviderRegistry
        from auth.providers.google import GoogleOAuth2Provider
        
        ProviderRegistry._providers = {}
        ProviderRegistry._configs = {}
        
        ProviderRegistry.register("google", GoogleOAuth2Provider)
        # Not configured
        
        provider = ProviderRegistry.get_provider("google")
        
        assert provider is None

    def test_list_available(self):
        """测试列出可用的 providers"""
        from auth.providers.registry import ProviderRegistry
        from auth.providers.google import GoogleOAuth2Provider
        from auth.providers.github import GitHubOAuth2Provider
        
        ProviderRegistry._providers = {}
        ProviderRegistry._configs = {}
        
        ProviderRegistry.register("google", GoogleOAuth2Provider)
        ProviderRegistry.register("github", GitHubOAuth2Provider)
        ProviderRegistry.configure("google", client_id="g_id", client_secret="g_secret")
        ProviderRegistry.configure("github", client_id="gh_id", client_secret="gh_secret")
        
        available = ProviderRegistry.list_available()
        
        assert isinstance(available, list)
        assert len(available) == 2
        provider_names = [p["name"] for p in available]
        assert "google" in provider_names
        assert "github" in provider_names

    def test_custom_provider_registration(self):
        """测试自定义 provider 注册"""
        from auth.providers.registry import ProviderRegistry
        from auth.providers.base import BaseOAuth2Provider, OAuth2Token, OAuth2UserInfo
        
        # Define custom provider
        class CustomProvider(BaseOAuth2Provider):
            name = "custom"
            
            def get_authorize_url(self, state: str, redirect_uri: str) -> str:
                return f"https://custom.com/oauth?state={state}"
            
            async def exchange_code(self, code: str, redirect_uri: str) -> OAuth2Token:
                return OAuth2Token(access_token="custom_token", expires_in=3600)
            
            async def get_userinfo(self, token: OAuth2Token) -> OAuth2UserInfo:
                return OAuth2UserInfo(
                    provider="custom",
                    provider_user_id="custom_123",
                    email="custom@example.com",
                    raw_data={}
                )
        
        ProviderRegistry._providers = {}
        ProviderRegistry._configs = {}
        
        ProviderRegistry.register("custom", CustomProvider)
        ProviderRegistry.configure("custom", client_id="custom_id", client_secret="custom_secret")
        
        provider = ProviderRegistry.get_provider("custom")
        
        assert provider is not None
        assert provider.name == "custom"
        assert isinstance(provider, CustomProvider)
