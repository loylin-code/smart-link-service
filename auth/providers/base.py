"""OAuth2 Provider Base Classes"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from pydantic import BaseModel


class OAuth2Token(BaseModel):
    """OAuth2 Token response"""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_in: int
    scope: Optional[str] = None


class OAuth2UserInfo(BaseModel):
    """OAuth2 user information"""
    provider: str              # Provider identifier (google, github, gitlab)
    provider_user_id: str      # Provider's internal user ID
    email: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    raw_data: Dict[str, Any]   # Provider's raw response


class BaseOAuth2Provider(ABC):
    """OAuth2 Provider abstract base class"""
    
    name: str  # Provider identifier (must be set by subclass)
    
    def __init__(self, client_id: str, client_secret: str):
        """
        Initialize OAuth2 provider
        
        Args:
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret
        """
        self.client_id = client_id
        self.client_secret = client_secret
    
    @abstractmethod
    def get_authorize_url(self, state: str, redirect_uri: str) -> str:
        """
        Build authorization URL
        
        Args:
            state: CSRF protection state value
            redirect_uri: Callback URL after authorization
            
        Returns:
            Authorization URL to redirect user to
        """
        pass
    
    @abstractmethod
    async def exchange_code(self, code: str, redirect_uri: str) -> OAuth2Token:
        """
        Exchange authorization code for access token
        
        Args:
            code: Authorization code from callback
            redirect_uri: Same redirect URI used in authorization request
            
        Returns:
            OAuth2Token with access token and related info
        """
        pass
    
    @abstractmethod
    async def get_userinfo(self, token: OAuth2Token) -> OAuth2UserInfo:
        """
        Get user information from provider
        
        Args:
            token: Access token from exchange_code
            
        Returns:
            OAuth2UserInfo with user profile data
        """
        pass
    
    async def refresh_token(self, refresh_token: str) -> OAuth2Token:
        """
        Refresh access token (optional, not all providers support it)
        
        Args:
            refresh_token: Refresh token from previous token exchange
            
        Returns:
            New OAuth2Token with fresh access token
            
        Raises:
            NotImplementedError: If provider does not support token refresh
        """
        raise NotImplementedError("Provider does not support refresh")
