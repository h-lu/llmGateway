"""Provider factory for creating AI provider instances.

This module provides a factory pattern for creating provider instances
based on configuration, with support for multiple providers and fallback.
"""

from enum import Enum
from typing import Dict, List, Optional, Type
import os

import httpx

from gateway.app.core.config import settings
from gateway.app.core.logging import get_logger
from gateway.app.providers.base import BaseProvider
from gateway.app.providers.deepseek import DeepSeekProvider
from gateway.app.providers.openai import OpenAIProvider
from gateway.app.providers.loadbalancer import LoadBalancer
from gateway.app.providers.health import ProviderHealthChecker

logger = get_logger(__name__)


class ProviderType(str, Enum):
    """Supported provider types."""
    DEEPSEEK = "deepseek"
    OPENAI = "openai"


# Provider registry mapping types to classes
_PROVIDER_REGISTRY: Dict[ProviderType, Type[BaseProvider]] = {
    ProviderType.DEEPSEEK: DeepSeekProvider,
    ProviderType.OPENAI: OpenAIProvider,
}


class ProviderConfig:
    """Configuration for a single provider.
    
    Attributes:
        provider_type: The type of provider (deepseek, openai, etc.)
        base_url: The API base URL
        api_key: The API key
        timeout: Request timeout in seconds
        priority: Priority for fallback (lower number = higher priority)
        enabled: Whether this provider is enabled
    """
    
    def __init__(
        self,
        provider_type: ProviderType,
        base_url: str,
        api_key: str,
        organization: Optional[str] = None,
        timeout: float = 60.0,
        priority: int = 1,
        enabled: bool = True
    ):
        self.provider_type = provider_type
        self.base_url = base_url
        self.api_key = api_key
        self.organization = organization
        self.timeout = timeout
        self.priority = priority
        self.enabled = enabled
    
    @classmethod
    def from_env(cls, prefix: str, provider_type: ProviderType) -> Optional["ProviderConfig"]:
        """Create a ProviderConfig from environment variables.
        
        Args:
            prefix: Environment variable prefix (e.g., "DEEPSEEK", "OPENAI")
            provider_type: The type of provider
            
        Returns:
            ProviderConfig if API key is set, None otherwise
        """
        api_key = os.getenv(f"{prefix}_API_KEY", "")
        if not api_key:
            return None
        
        # Get base URL with defaults
        default_urls = {
            ProviderType.DEEPSEEK: "https://api.deepseek.com/v1",
            ProviderType.OPENAI: "https://api.openai.com/v1",
        }
        base_url = os.getenv(f"{prefix}_BASE_URL", default_urls.get(provider_type, ""))
        
        # Get optional settings
        organization = os.getenv(f"{prefix}_ORGANIZATION") if provider_type == ProviderType.OPENAI else None
        timeout = float(os.getenv(f"{prefix}_TIMEOUT", "60.0"))
        priority = int(os.getenv(f"{prefix}_PRIORITY", "1"))
        enabled = os.getenv(f"{prefix}_ENABLED", "true").lower() == "true"
        
        return cls(
            provider_type=provider_type,
            base_url=base_url,
            api_key=api_key,
            organization=organization,
            timeout=timeout,
            priority=priority,
            enabled=enabled
        )


class ProviderFactory:
    """Factory for creating provider instances.
    
    This factory supports:
    - Creating providers by type
    - Multiple provider configurations
    - Automatic fallback selection
    - Shared HTTP client for connection pooling
    
    Usage:
        factory = ProviderFactory()
        provider = factory.create_primary_provider()
        
        # Or with specific type
        provider = factory.create_provider(ProviderType.OPENAI)
    """
    
    def __init__(self, http_client: Optional[httpx.AsyncClient] = None):
        """Initialize the provider factory.
        
        Args:
            http_client: Optional shared HTTP client for connection pooling
        """
        self._http_client = http_client
        self._configs: Dict[ProviderType, ProviderConfig] = {}
        self._load_configs()
    
    def _load_configs(self) -> None:
        """Load provider configurations from environment."""
        # Load DeepSeek config
        deepseek_config = ProviderConfig.from_env("DEEPSEEK", ProviderType.DEEPSEEK)
        if deepseek_config:
            self._configs[ProviderType.DEEPSEEK] = deepseek_config
        elif settings.deepseek_api_key:
            # Fallback to settings
            self._configs[ProviderType.DEEPSEEK] = ProviderConfig(
                provider_type=ProviderType.DEEPSEEK,
                base_url=settings.deepseek_base_url,
                api_key=settings.deepseek_api_key
            )
        
        # Load OpenAI config
        openai_config = ProviderConfig.from_env("OPENAI", ProviderType.OPENAI)
        if openai_config:
            self._configs[ProviderType.OPENAI] = openai_config
    
    def create_provider(
        self, 
        provider_type: ProviderType,
        config: Optional[ProviderConfig] = None
    ) -> BaseProvider:
        """Create a provider instance by type.
        
        Args:
            provider_type: The type of provider to create
            config: Optional custom configuration. If not provided, uses loaded config.
            
        Returns:
            Provider instance
            
        Raises:
            ValueError: If provider type is not supported
            RuntimeError: If no configuration is available for the provider
        """
        if provider_type not in _PROVIDER_REGISTRY:
            raise ValueError(f"Unsupported provider type: {provider_type}")
        
        provider_class = _PROVIDER_REGISTRY[provider_type]
        
        # Use provided config or load from environment
        if config is None:
            if provider_type not in self._configs:
                raise RuntimeError(f"No configuration available for provider: {provider_type}")
            config = self._configs[provider_type]
        
        # Create provider instance based on type
        if provider_type == ProviderType.DEEPSEEK:
            return provider_class(
                base_url=config.base_url,
                api_key=config.api_key,
                http_client=self._http_client,
                timeout=config.timeout
            )
        elif provider_type == ProviderType.OPENAI:
            return provider_class(
                base_url=config.base_url,
                api_key=config.api_key,
                organization=config.organization,
                http_client=self._http_client,
                timeout=config.timeout
            )
        else:
            raise ValueError(f"Unknown provider type: {provider_type}")
    
    def create_primary_provider(self) -> BaseProvider:
        """Create the primary provider (highest priority enabled provider).
        
        Returns:
            The primary provider instance
            
        Raises:
            RuntimeError: If no providers are configured or enabled
        """
        # Sort by priority and filter enabled
        enabled_configs = [
            (ptype, config) for ptype, config in self._configs.items()
            if config.enabled
        ]
        
        if not enabled_configs:
            raise RuntimeError("No providers are configured or enabled")
        
        # Sort by priority (lower number = higher priority)
        enabled_configs.sort(key=lambda x: x[1].priority)
        
        primary_type, primary_config = enabled_configs[0]
        return self.create_provider(primary_type, primary_config)
    
    def get_fallback_providers(self) -> List[BaseProvider]:
        """Get a list of fallback providers (excluding primary).
        
        Returns:
            List of fallback provider instances, sorted by priority
        """
        # Sort by priority and filter enabled
        enabled_configs = [
            (ptype, config) for ptype, config in self._configs.items()
            if config.enabled
        ]
        
        if len(enabled_configs) <= 1:
            return []
        
        # Sort by priority (lower number = higher priority)
        enabled_configs.sort(key=lambda x: x[1].priority)
        
        # Skip the primary (first) provider
        fallback_providers = []
        for provider_type, config in enabled_configs[1:]:
            try:
                provider = self.create_provider(provider_type, config)
                fallback_providers.append(provider)
            except Exception:
                # Skip providers that fail to create
                continue
        
        return fallback_providers
    
    def list_configured_providers(self) -> List[ProviderType]:
        """Get a list of configured provider types.
        
        Returns:
            List of configured provider types
        """
        return list(self._configs.keys())
    
    def is_provider_configured(self, provider_type: ProviderType) -> bool:
        """Check if a provider type is configured.
        
        Args:
            provider_type: The provider type to check
            
        Returns:
            True if configured, False otherwise
        """
        return provider_type in self._configs


# Global factory instance
_factory: Optional[ProviderFactory] = None

# Global load balancer instance
_load_balancer: Optional[LoadBalancer] = None

# Global health checker instance
_health_checker: Optional[ProviderHealthChecker] = None


def get_provider_factory(http_client: Optional[httpx.AsyncClient] = None) -> ProviderFactory:
    """Get the global ProviderFactory instance (singleton pattern).
    
    Args:
        http_client: Optional HTTP client to use. Only used on first call.
        
    Returns:
        The global ProviderFactory instance
    """
    global _factory
    if _factory is None:
        _factory = ProviderFactory(http_client)
    return _factory


def reset_provider_factory() -> None:
    """Reset the global factory instance.
    
    This is useful for testing or when configuration changes.
    """
    global _factory
    _factory = None


def create_provider(provider_type: ProviderType) -> BaseProvider:
    """Convenience function to create a provider.
    
    Args:
        provider_type: The type of provider to create
        
    Returns:
        Provider instance
    """
    factory = get_provider_factory()
    return factory.create_provider(provider_type)


def get_primary_provider() -> BaseProvider:
    """Convenience function to get the primary provider.
    
    Returns:
        The primary provider instance
    """
    factory = get_provider_factory()
    return factory.create_primary_provider()


def get_health_checker(check_interval: float = 30.0) -> ProviderHealthChecker:
    """Get the global ProviderHealthChecker instance (singleton pattern).
    
    Args:
        check_interval: Time between health checks in seconds
        
    Returns:
        The global ProviderHealthChecker instance
    """
    global _health_checker
    if _health_checker is None:
        _health_checker = ProviderHealthChecker(check_interval=check_interval)
    return _health_checker


def get_load_balancer(
    http_client: Optional[httpx.AsyncClient] = None,
    strategy: str = "round_robin"
) -> LoadBalancer:
    """Get the global LoadBalancer instance (singleton pattern).
    
    This function initializes the load balancer with all configured providers.
    
    Args:
        http_client: Optional HTTP client for connection pooling. If None,
                     creates a new HTTP client for testing purposes.
        strategy: Load balancing strategy (round_robin, weighted, health_first)
        
    Returns:
        The global LoadBalancer instance with providers registered
    """
    global _load_balancer
    if _load_balancer is None:
        # For testing, create a new HTTP client if none provided
        # This handles cases where the lifespan context hasn't been started
        client = http_client
        if client is None:
            try:
                from gateway.app.core.http_client import get_http_client
                client = get_http_client()
            except RuntimeError:
                # HTTP client not initialized (e.g., in tests)
                # Create a temporary client for load balancer initialization
                client = None
        
        factory = get_provider_factory(client)
        health_checker = get_health_checker()
        
        _load_balancer = LoadBalancer(
            factory=factory,
            health_checker=health_checker,
            strategy=strategy
        )
        
        # Register all configured providers
        _register_providers_with_load_balancer(_load_balancer, factory, client)
        
        logger.info(
            f"Load balancer initialized with strategy '{strategy}' "
            f"and {_load_balancer.provider_count} providers"
        )
    
    return _load_balancer


def _register_providers_with_load_balancer(
    load_balancer: LoadBalancer,
    factory: ProviderFactory,
    http_client: Optional[httpx.AsyncClient] = None
) -> None:
    """Register all configured providers with the load balancer.
    
    Args:
        load_balancer: The load balancer to register providers with
        factory: The provider factory
        http_client: Optional HTTP client for creating providers
    """
    configured_types = factory.list_configured_providers()
    
    for provider_type in configured_types:
        try:
            provider = factory.create_provider(provider_type)
            provider_name = provider_type.value
            load_balancer.register_provider(provider, name=provider_name)
            logger.debug(f"Registered provider '{provider_name}' with load balancer")
        except Exception as e:
            logger.warning(f"Failed to register provider '{provider_type.value}': {e}")


def reset_load_balancer() -> None:
    """Reset the global load balancer and health checker instances.
    
    This is useful for testing or when configuration changes.
    """
    global _load_balancer, _health_checker
    _load_balancer = None
    _health_checker = None
    logger.debug("Load balancer and health checker reset")
