"""OAuth2 Provider Registry"""
from typing import Optional, Dict, Type, List, Any
from auth.providers.base import BaseOAuth2Provider


class ProviderRegistry:
    """
    Provider registry - supports dynamic registration of custom providers
    
    This class manages OAuth2 provider classes and their configurations,
    allowing for both built-in and custom provider implementations.
    """
    
    # Class-level storage for provider classes and configurations
    _providers: Dict[str, Type[BaseOAuth2Provider]] = {}
    _configs: Dict[str, Dict[str, Any]] = {}
    
    @classmethod
    def register(cls, name: str, provider_class: Type[BaseOAuth2Provider]) -> None:
        """
        Register a provider class
        
        Args:
            name: Provider identifier (e.g., "google", "github")
            provider_class: Provider class that extends BaseOAuth2Provider
        """
        cls._providers[name] = provider_class
    
    @classmethod
    def configure(cls, name: str, client_id: str, client_secret: str) -> None:
        """
        Configure provider instance parameters
        
        Args:
            name: Provider identifier
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret
        """
        cls._configs[name] = {
            "client_id": client_id,
            "client_secret": client_secret
        }
    
    @classmethod
    def get_provider(cls, name: str) -> Optional[BaseOAuth2Provider]:
        """
        Get configured provider instance
        
        Args:
            name: Provider identifier
            
        Returns:
            Configured provider instance, or None if not registered/configured
        """
        if name not in cls._providers or name not in cls._configs:
            return None
        
        provider_class = cls._providers[name]
        config = cls._configs[name]
        return provider_class(**config)
    
    @classmethod
    def list_available(cls) -> List[Dict[str, Any]]:
        """
        List all available and configured providers
        
        Returns:
            List of provider info dictionaries with name and configuration status
        """
        available = []
        for name in cls._providers:
            if name in cls._configs:
                available.append({
                    "name": name,
                    "configured": True,
                    "client_id": cls._configs[name].get("client_id")
                })
        return available
    
    @classmethod
    def is_configured(cls, name: str) -> bool:
        """
        Check if a provider is configured
        
        Args:
            name: Provider identifier
            
        Returns:
            True if provider is registered and configured
        """
        return name in cls._providers and name in cls._configs
    
    @classmethod
    def clear(cls) -> None:
        """
        Clear all registered providers and configurations
        
        Useful for testing purposes.
        """
        cls._providers = {}
        cls._configs = {}


# Register built-in providers
from auth.providers.google import GoogleOAuth2Provider
from auth.providers.github import GitHubOAuth2Provider
from auth.providers.gitlab import GitLabOAuth2Provider

ProviderRegistry.register("google", GoogleOAuth2Provider)
ProviderRegistry.register("github", GitHubOAuth2Provider)
ProviderRegistry.register("gitlab", GitLabOAuth2Provider)
