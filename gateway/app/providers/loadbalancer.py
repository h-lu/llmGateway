"""Load balancer for AI providers.

This module provides load balancing functionality for distributing requests
across multiple AI providers using different strategies.
"""

import asyncio
import random
from enum import Enum
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from gateway.app.providers.base import BaseProvider
    from gateway.app.providers.factory import ProviderFactory
    from gateway.app.providers.health import ProviderHealthChecker


class LoadBalanceStrategy(str, Enum):
    """Supported load balancing strategies."""

    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"
    HEALTH_FIRST = "health_first"


class LoadBalancer:
    """Load balancer for distributing requests across multiple providers.

    This class provides:
    - Multiple load balancing strategies (round_robin, weighted, health_first)
    - Provider registration/unregistration
    - Health status integration for intelligent routing
    - Thread-safe operations

    Usage:
        # Create with factory and health checker
        factory = ProviderFactory()
        health_checker = ProviderHealthChecker()
        lb = LoadBalancer(factory, health_checker, strategy="round_robin")

        # Register providers
        lb.register_provider(openai_provider, weight=2)
        lb.register_provider(deepseek_provider, weight=1)

        # Get provider for request
        provider = lb.get_provider()

        # Start health checking in background
        await health_checker.start()
    """

    def __init__(
        self,
        factory: "ProviderFactory",
        health_checker: "ProviderHealthChecker",
        strategy: str = "round_robin",
    ):
        """Initialize the load balancer.

        Args:
            factory: ProviderFactory for creating providers
            health_checker: ProviderHealthChecker for health status
            strategy: Load balancing strategy (round_robin, weighted, health_first)
        """
        self._factory = factory
        self._health_checker = health_checker
        self._strategy = LoadBalanceStrategy(strategy)

        # Provider storage
        self._providers: Dict[str, "BaseProvider"] = {}
        self._weights: Dict[str, int] = {}

        # Round-robin state
        self._rr_index = 0
        self._rr_lock = asyncio.Lock()

    def register_provider(
        self, provider: "BaseProvider", name: Optional[str] = None, weight: int = 1
    ) -> str:
        """Register a provider for load balancing.

        Args:
            provider: The provider instance to register
            name: Optional custom name for the provider. If not provided,
                  a unique name is generated based on class and id.
            weight: Weight for weighted strategy (higher = more likely)

        Returns:
            The name assigned to the provider
        """
        # Get provider name from the provider instance or use provided name
        if name is None:
            provider_name = self._get_provider_name(provider)
        else:
            provider_name = name

        self._providers[provider_name] = provider
        self._weights[provider_name] = max(1, weight)  # Ensure weight >= 1

        # Register with health checker
        self._health_checker.register_provider(provider_name, provider)

        return provider_name

    def unregister_provider(self, provider_name: str) -> None:
        """Unregister a provider from load balancing.

        Args:
            provider_name: The name of the provider to remove
        """
        self._providers.pop(provider_name, None)
        self._weights.pop(provider_name, None)

        # Unregister from health checker
        self._health_checker.unregister_provider(provider_name)

    async def get_provider(self) -> "BaseProvider":
        """Get the next provider based on the load balancing strategy.

        Returns:
            The selected provider instance

        Raises:
            RuntimeError: If no providers are registered
        """
        if not self._providers:
            raise RuntimeError("No providers registered")

        # Get available providers based on strategy
        if self._strategy == LoadBalanceStrategy.HEALTH_FIRST:
            return await self._get_health_first_provider()
        elif self._strategy == LoadBalanceStrategy.WEIGHTED:
            return self._get_weighted_provider()
        else:  # round_robin
            return await self._get_round_robin_provider()

    def get_all_providers(self) -> List["BaseProvider"]:
        """Get all registered providers.

        Returns:
            List of all registered provider instances
        """
        return list(self._providers.values())

    def get_available_providers(self) -> List["BaseProvider"]:
        """Get all healthy providers.

        Returns:
            List of providers that are currently healthy
        """
        available = []
        for name, provider in self._providers.items():
            if self._health_checker.is_healthy(name):
                available.append(provider)
        return available

    def _get_provider_name(self, provider: "BaseProvider") -> str:
        """Generate a unique name for a provider instance.

        Args:
            provider: The provider instance

        Returns:
            A unique name for the provider
        """
        # Use class name and id for uniqueness
        return f"{provider.__class__.__name__.lower()}_{id(provider)}"

    def _get_healthy_providers(self) -> List[tuple]:
        """Get list of healthy providers with their names.

        Returns:
            List of (name, provider) tuples that are healthy
        """
        healthy = []
        for name, provider in self._providers.items():
            if self._health_checker.is_healthy(name):
                healthy.append((name, provider))
        return healthy

    async def _get_round_robin_provider(self) -> "BaseProvider":
        """Get provider using round-robin strategy.

        Skips unhealthy providers if possible. Uses atomic index update
        within lock to prevent race conditions.

        Returns:
            The selected provider instance
        """
        # Try to get healthy providers first
        healthy = self._get_healthy_providers()

        if healthy:
            # Use round-robin on healthy providers
            # Atomic read-and-increment within lock to prevent race conditions
            async with self._rr_lock:
                index = self._rr_index % len(healthy)
                self._rr_index = (self._rr_index + 1) % max(1, len(healthy))
            return healthy[index][1]

        # Fall back to all providers if no healthy ones
        providers_list = list(self._providers.items())
        if not providers_list:
            raise RuntimeError("No providers registered")

        async with self._rr_lock:
            index = self._rr_index % len(providers_list)
            self._rr_index = (self._rr_index + 1) % len(providers_list)
        return providers_list[index][1]

    def _get_weighted_provider(self) -> "BaseProvider":
        """Get provider using weighted random selection.

        Only considers healthy providers. Falls back to all if no healthy ones.

        Returns:
            The selected provider instance
        """
        # Filter to healthy providers if possible
        candidates = self._get_healthy_providers()
        if not candidates:
            candidates = list(self._providers.items())

        # Get weights for candidates
        weights = [self._weights.get(name, 1) for name, _ in candidates]

        # Weighted random selection
        total_weight = sum(weights)
        if total_weight == 0:
            # Fallback to uniform if all weights are 0
            return random.choice([p for _, p in candidates])

        r = random.uniform(0, total_weight)
        cumulative = 0
        for i, weight in enumerate(weights):
            cumulative += weight
            if r <= cumulative:
                return candidates[i][1]

        # Fallback to last candidate (shouldn't reach here)
        return candidates[-1][1]

    async def _get_health_first_provider(self) -> "BaseProvider":
        """Get provider prioritizing healthy ones.

        Uses round-robin among healthy providers. Raises error if no healthy providers.

        Returns:
            The selected provider instance

        Raises:
            RuntimeError: If no healthy providers are available
        """
        healthy = self._get_healthy_providers()

        if not healthy:
            raise RuntimeError("No healthy providers available")

        # Round-robin among healthy providers
        async with self._rr_lock:
            index = self._rr_index % len(healthy)
            self._rr_index = (self._rr_index + 1) % len(healthy)

        return healthy[index][1]

    @property
    def strategy(self) -> LoadBalanceStrategy:
        """Get the current load balancing strategy."""
        return self._strategy

    @strategy.setter
    def strategy(self, value: str) -> None:
        """Set the load balancing strategy.

        Args:
            value: Strategy name (round_robin, weighted, health_first)
        """
        self._strategy = LoadBalanceStrategy(value)

    @property
    def provider_count(self) -> int:
        """Get the number of registered providers."""
        return len(self._providers)

    @property
    def healthy_count(self) -> int:
        """Get the number of healthy providers."""
        return sum(
            1 for name in self._providers if self._health_checker.is_healthy(name)
        )
