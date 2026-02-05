"""Base helper functions for provider factory.

This module contains helper functions used by the provider factory
for HTTP client management and load balancer registration.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Optional

import httpx

from gateway.app.core.logging import get_logger
from gateway.app.providers.mock import MockProvider

if TYPE_CHECKING:
    from gateway.app.providers.loadbalancer import LoadBalancer
    from gateway.app.providers.factory import ProviderFactory

logger = get_logger(__name__)


def try_get_shared_http_client() -> Optional[httpx.AsyncClient]:
    """Try to get the shared HTTP client from lifespan context.

    Returns:
        The shared HTTP client if available, None otherwise (e.g., in tests
        before lifespan is started).
    """
    try:
        from gateway.app.core.http_client import get_http_client

        return get_http_client()
    except RuntimeError:
        # HTTP client not initialized (e.g., in tests)
        # Provider will create its own temporary client
        return None


def register_providers_with_load_balancer(
    load_balancer: "LoadBalancer",
    factory: "ProviderFactory",
    http_client: Optional[httpx.AsyncClient] = None,
) -> None:
    """Register all configured providers with the load balancer.

    Args:
        load_balancer: The load balancer to register providers with
        factory: The provider factory
        http_client: Optional HTTP client for creating providers

    Note:
        Uses string type annotations to avoid circular imports.
    """
    configured_types = factory.list_configured_providers()

    # If no providers configured but mock is enabled, register mock provider
    if (
        not configured_types
        and os.getenv("TEACHPROXY_MOCK_PROVIDER", "").lower() == "true"
    ):
        try:
            mock_provider = MockProvider()
            load_balancer.register_provider(mock_provider, name="mock")
            logger.info("Registered mock provider with load balancer for testing")
        except Exception as e:
            logger.warning(f"Failed to register mock provider: {e}")
        return

    for provider_type in configured_types:
        try:
            provider = factory.create_provider(provider_type)
            provider_name = provider_type.value
            load_balancer.register_provider(provider, name=provider_name)
            logger.debug(f"Registered provider '{provider_name}' with load balancer")
        except Exception as e:
            logger.warning(f"Failed to register provider '{provider_type.value}': {e}")
