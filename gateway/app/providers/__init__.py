"""AI providers package for TeachProxy Gateway.

This package provides:
- Base provider interface (BaseProvider)
- Provider implementations (DeepSeekProvider, OpenAIProvider)
- Provider factory for creating instances (ProviderFactory, ProviderType)
- Health checking (ProviderHealthChecker)
- Load balancing (LoadBalancer, LoadBalanceStrategy)
- Retry mechanism (RetryPolicy, with_retry)
"""

from gateway.app.providers.base import BaseProvider
from gateway.app.providers.deepseek import DeepSeekProvider
from gateway.app.providers.factory import (
    ProviderConfig,
    ProviderFactory,
    ProviderType,
    create_provider,
    get_health_checker,
    get_load_balancer,
    get_primary_provider,
    get_provider_factory,
    reset_load_balancer,
    reset_provider_factory,
)
from gateway.app.providers.health import ProviderHealthChecker
from gateway.app.providers.loadbalancer import LoadBalancer, LoadBalanceStrategy
from gateway.app.providers.openai import OpenAIProvider
from gateway.app.providers.retry import RetryPolicy, with_retry

__all__ = [
    # Base
    "BaseProvider",
    # Providers
    "DeepSeekProvider",
    "OpenAIProvider",
    # Factory
    "ProviderConfig",
    "ProviderFactory",
    "ProviderType",
    "create_provider",
    "get_health_checker",
    "get_load_balancer",
    "get_primary_provider",
    "get_provider_factory",
    "reset_load_balancer",
    "reset_provider_factory",
    # Health
    "ProviderHealthChecker",
    # Load Balancer
    "LoadBalancer",
    "LoadBalanceStrategy",
    # Retry
    "RetryPolicy",
    "with_retry",
]
