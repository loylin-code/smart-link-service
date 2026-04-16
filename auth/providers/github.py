"""GitHub OAuth2 Provider Implementation"""
from typing import Optional, List, Dict, Any
from urllib.parse import urlencode, parse_qs
import httpx

from auth.providers.base import BaseOAuth2Provider, OAuth2Token, OAuth2UserInfo


class GitHubOAuth2Provider(BaseOAuth2Provider):
    """GitHub OAuth2 Provider"""
    
    name = "github"
    
    # GitHub OAuth2 endpoints
    AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
    TOKEN_URL = "https://github.com/login/oauth/access_token"
    USERINFO_URL = "https://api.github.com/user"
    EMAILS_URL = "https://api.github.com/user/emails"
    
    # Default scopes
    DEFAULT_SCOPES = ["user:email"]
    
    def __init__(self, client_id: str, client_secret: str):
        """
        Initialize GitHub OAuth2 provider
        
        Args:
            client_id: GitHub OAuth2 client ID
            client_secret: GitHub OAuth2 client secret
        """
        super().__init__(client_id, client_secret)
    
    def get_authorize_url(self, state: str, redirect_uri: str) -> str:
        """
        Build GitHub OAuth2 authorization URL
        
        Args:
            state: CSRF protection state value
            redirect_uri: Callback URL after authorization
            
        Returns:
            GitHub authorization URL
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(self.DEFAULT_SCOPES),
            "state": state
        }
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"
    
    async def exchange_code(self, code: str, redirect_uri: str) -> OAuth2Token:
        """
        Exchange authorization code for GitHub access token
        
        Args:
            code: Authorization code from callback
            redirect_uri: Same redirect URI used in authorization request
            
        Returns:
            OAuth2Token with GitHub access token
        """
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.TOKEN_URL,
                json={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri
                },
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                }
            )
            response.raise_for_status()
            data = response.json()
            
            # GitHub tokens don't expire (expires_in = 0)
            return OAuth2Token(
                access_token=data["access_token"],
                refresh_token=None,  # GitHub doesn't provide refresh tokens
                token_type=data.get("token_type", "Bearer"),
                expires_in=0,  # GitHub tokens don't expire
                scope=data.get("scope")
            )
    
    async def get_userinfo(self, token: OAuth2Token) -> OAuth2UserInfo:
        """
        Get user information from GitHub
        
        Args:
            token: GitHub access token
            
        Returns:
            OAuth2UserInfo with GitHub user profile data
        """
        async with httpx.AsyncClient() as client:
            # Get user info
            user_response = await client.get(
                self.USERINFO_URL,
                headers={
                    "Authorization": f"{token.token_type} {token.access_token}",
                    "Accept": "application/vnd.github.v3+json"
                }
            )
            user_response.raise_for_status()
            user_data = user_response.json()
            
            # Get primary email (use user email if available, otherwise fetch from emails endpoint)
            email = user_data.get("email")
            if not email:
                email = await self._get_primary_email(client, token)
            
            return OAuth2UserInfo(
                provider="github",
                provider_user_id=str(user_data.get("id")),
                email=email or "",
                name=user_data.get("name"),
                avatar_url=user_data.get("avatar_url"),
                raw_data=user_data
            )
    
    async def _get_primary_email(self, client: httpx.AsyncClient, token: OAuth2Token) -> Optional[str]:
        """
        Get user's primary email from GitHub
        
        Args:
            client: HTTP client
            token: GitHub access token
            
        Returns:
            Primary email address or None
        """
        response = await client.get(
            self.EMAILS_URL,
            headers={
                "Authorization": f"{token.token_type} {token.access_token}",
                "Accept": "application/vnd.github.v3+json"
            }
        )
        response.raise_for_status()
        emails = response.json()
        
        # Find primary verified email
        for email_entry in emails:
            if email_entry.get("primary") and email_entry.get("verified"):
                return email_entry.get("email")
        
        # Fallback to first verified email
        for email_entry in emails:
            if email_entry.get("verified"):
                return email_entry.get("email")
        
        return None
