"""OAuth Provider Implementations"""
from auth.providers.base import BaseOAuth2Provider, OAuth2Token, OAuth2UserInfo
from auth.providers.google import GoogleOAuth2Provider
from auth.providers.github import GitHubOAuth2Provider
from auth.providers.gitlab import GitLabOAuth2Provider
from auth.providers.registry import ProviderRegistry

__all__ = [
    "BaseOAuth2Provider",
    "OAuth2Token",
    "OAuth2UserInfo",
    "GoogleOAuth2Provider",
    "GitHubOAuth2Provider",
    "GitLabOAuth2Provider",
    "ProviderRegistry",
]
