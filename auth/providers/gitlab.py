"""GitLab OAuth2 Provider Implementation"""
from typing import Optional
from urllib.parse import urlencode
import httpx

from auth.providers.base import BaseOAuth2Provider, OAuth2Token, OAuth2UserInfo


class GitLabOAuth2Provider(BaseOAuth2Provider):
    """GitLab OAuth2 Provider"""
    
    name = "gitlab"
    
    # GitLab OAuth2 endpoints
    AUTHORIZE_URL = "https://gitlab.com/oauth/authorize"
    TOKEN_URL = "https://gitlab.com/oauth/token"
    USERINFO_URL = "https://gitlab.com/api/v4/user"
    
    # Default scopes
    DEFAULT_SCOPES = ["read_user"]
    
    def __init__(self, client_id: str, client_secret: str):
        """
        Initialize GitLab OAuth2 provider
        
        Args:
            client_id: GitLab OAuth2 client ID
            client_secret: GitLab OAuth2 client secret
        """
        super().__init__(client_id, client_secret)
    
    def get_authorize_url(self, state: str, redirect_uri: str) -> str:
        """
        Build GitLab OAuth2 authorization URL
        
        Args:
            state: CSRF protection state value
            redirect_uri: Callback URL after authorization
            
        Returns:
            GitLab authorization URL
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.DEFAULT_SCOPES),
            "state": state
        }
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"
    
    async def exchange_code(self, code: str, redirect_uri: str) -> OAuth2Token:
        """
        Exchange authorization code for GitLab access token
        
        Args:
            code: Authorization code from callback
            redirect_uri: Same redirect URI used in authorization request
            
        Returns:
            OAuth2Token with GitLab access token
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code"
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            data = response.json()
            
            return OAuth2Token(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token"),
                token_type=data.get("token_type", "Bearer"),
                expires_in=data.get("expires_in", 7200),
                scope=data.get("scope")
            )
    
    async def get_userinfo(self, token: OAuth2Token) -> OAuth2UserInfo:
        """
        Get user information from GitLab
        
        Args:
            token: GitLab access token
            
        Returns:
            OAuth2UserInfo with GitLab user profile data
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.USERINFO_URL,
                headers={"Authorization": f"{token.token_type} {token.access_token}"}
            )
            response.raise_for_status()
            data = response.json()
            
            return OAuth2UserInfo(
                provider="gitlab",
                provider_user_id=str(data.get("id")),
                email=data.get("email"),
                name=data.get("name"),
                avatar_url=data.get("avatar_url"),
                raw_data=data
            )
    
    async def refresh_token(self, refresh_token: str) -> OAuth2Token:
        """
        Refresh GitLab access token
        
        Args:
            refresh_token: Refresh token from previous token exchange
            
        Returns:
            New OAuth2Token with fresh access token
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token"
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            data = response.json()
            
            return OAuth2Token(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token", refresh_token),
                token_type=data.get("token_type", "Bearer"),
                expires_in=data.get("expires_in", 7200),
                scope=data.get("scope")
            )
