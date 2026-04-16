"""Google OAuth2 Provider Implementation"""
from typing import Optional
from urllib.parse import urlencode, quote
import httpx

from auth.providers.base import BaseOAuth2Provider, OAuth2Token, OAuth2UserInfo


class GoogleOAuth2Provider(BaseOAuth2Provider):
    """Google OAuth2 Provider"""
    
    name = "google"
    
    # Google OAuth2 endpoints
    AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
    
    # Default scopes
    DEFAULT_SCOPES = ["openid", "email", "profile"]
    
    def __init__(self, client_id: str, client_secret: str):
        """
        Initialize Google OAuth2 provider
        
        Args:
            client_id: Google OAuth2 client ID
            client_secret: Google OAuth2 client secret
        """
        super().__init__(client_id, client_secret)
    
    def get_authorize_url(self, state: str, redirect_uri: str) -> str:
        """
        Build Google OAuth2 authorization URL
        
        Args:
            state: CSRF protection state value
            redirect_uri: Callback URL after authorization
            
        Returns:
            Google authorization URL
        """
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.DEFAULT_SCOPES),
            "state": state,
            "access_type": "offline",
            "prompt": "consent"
        }
        return f"{self.AUTHORIZE_URL}?{urlencode(params)}"
    
    async def exchange_code(self, code: str, redirect_uri: str) -> OAuth2Token:
        """
        Exchange authorization code for Google access token
        
        Args:
            code: Authorization code from callback
            redirect_uri: Same redirect URI used in authorization request
            
        Returns:
            OAuth2Token with Google access token
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
                expires_in=data.get("expires_in", 3599),
                scope=data.get("scope")
            )
    
    async def get_userinfo(self, token: OAuth2Token) -> OAuth2UserInfo:
        """
        Get user information from Google
        
        Args:
            token: Google access token
            
        Returns:
            OAuth2UserInfo with Google user profile data
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.USERINFO_URL,
                headers={"Authorization": f"{token.token_type} {token.access_token}"}
            )
            response.raise_for_status()
            data = response.json()
            
            return OAuth2UserInfo(
                provider="google",
                provider_user_id=data.get("id"),
                email=data.get("email"),
                name=data.get("name"),
                avatar_url=data.get("picture"),
                raw_data=data
            )
    
    async def refresh_token(self, refresh_token: str) -> OAuth2Token:
        """
        Refresh Google access token
        
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
                expires_in=data.get("expires_in", 3599),
                scope=data.get("scope")
            )
