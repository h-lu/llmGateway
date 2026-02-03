"""Provider factory for creating AI provider instances.

This module provides a factory pattern for creating provider instances
based on configuration, with support for multiple providers and fallback.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Optional, Type

import httpx

from gateway.app.core.logging import get_logger
from gateway.app.providers.base import BaseProvider
from gateway.app.providers.deepseek import DeepSeekProvider
from gateway.app.providers.openai import OpenAIProvider
from gateway.app.providers.mock import MockProvider
from gateway.app.providers.factory_base import (
    register_providers_with_load_balancer,
    try_get_shared_http_client,
)
from gateway.app.providers.factory_config import (
    ProviderType,
    ProviderConfig,
    is_mock_mode,
    load_all_provider_configs,
)

if TYPE_CHECKING:
    # Avoid circular imports at runtime
    from gateway.app.providers.loadbalancer import LoadBalancer
    from gateway.app.providers.health import ProviderHealthChecker

logger = get_logger(__name__)


# Provider registry mapping types to classes
_PROVIDER_REGISTRY: Dict[ProviderType, Type[BaseProvider]] = {
    ProviderType.DEEPSEEK: DeepSeekProvider,
    ProviderType.OPENAI: OpenAIProvider,
    ProviderType.MOCK: MockProvider,
}


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
        self._configs = load_all_provider_configs()
    
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
            # Check if we should use mock provider
            if is_mock_mode():
                logger.info("No providers configured, using mock provider for testing")
                return MockProvider()
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
        
    Note:
        This function imports ProviderHealthChecker lazily to avoid circular imports.
    """
    global _health_checker
    if _health_checker is None:
        from gateway.app.providers.health import ProviderHealthChecker
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
                     attempts to get the shared HTTP client from lifespan context.
        strategy: Load balancing strategy (round_robin, weighted, health_first)
        
    Returns:
        The global LoadBalancer instance with providers registered
        
    Note:
        This function imports LoadBalancer lazily to avoid circular imports.
        The http_client should typically be provided from the lifespan context.
    """
    global _load_balancer
    if _load_balancer is None:
        # Import here to avoid circular imports at module level
        from gateway.app.providers.loadbalancer import LoadBalancer
        from gateway.app.providers.health import ProviderHealthChecker
        
        # Use provided client or attempt to get from lifespan context
        client = http_client
        if client is None:
            client = try_get_shared_http_client()
        
        factory = get_provider_factory(client)
        health_checker = get_health_checker()
        
        _load_balancer = LoadBalancer(
            factory=factory,
            health_checker=health_checker,
            strategy=strategy
        )
        
        # Register all configured providers
        register_providers_with_load_balancer(_load_balancer, factory, client)
        
        logger.info(
            f"Load balancer initialized with strategy '{strategy}' "
            f"and {_load_balancer.provider_count} providers"
        )
    
    return _load_balancer


def reset_load_balancer() -> None:
    """Reset the global load balancer and health checker instances.
    
    This is useful for testing or when configuration changes.
    """
    global _load_balancer, _health_checker
    _load_balancer = None
    _health_checker = None
    logger.debug("Load balancer and health checker reset")
