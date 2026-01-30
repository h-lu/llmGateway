"""Tests for LoadBalancer and load balancing strategies."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from gateway.app.providers.base import BaseProvider
from gateway.app.providers.loadbalancer import LoadBalancer, LoadBalanceStrategy


class MockProvider(BaseProvider):
    """Mock provider for testing."""
    
    def __init__(self, name: str):
        # Initialize with minimal required params
        super().__init__(
            base_url="https://api.test.com/v1",
            api_key="test-key"
        )
        self._name = name
    
    async def chat_completion(self, payload):
        return {"choices": [{"message": {"content": "test"}}]}
    
    async def stream_chat(self, payload):
        yield "data: test"
    
    async def health_check(self, timeout: float = 2.0) -> bool:
        return True
    
    def __repr__(self):
        return f"MockProvider({self._name})"


class TestLoadBalanceStrategy:
    """Test LoadBalanceStrategy enum."""
    
    def test_strategy_values(self):
        """Test strategy enum values."""
        assert LoadBalanceStrategy.ROUND_ROBIN.value == "round_robin"
        assert LoadBalanceStrategy.WEIGHTED.value == "weighted"
        assert LoadBalanceStrategy.HEALTH_FIRST.value == "health_first"


class TestLoadBalancerInit:
    """Test LoadBalancer initialization."""
    
    def test_default_strategy(self):
        """Test default strategy is round_robin."""
        factory = MagicMock()
        health_checker = MagicMock()
        
        lb = LoadBalancer(factory, health_checker)
        
        assert lb.strategy == LoadBalanceStrategy.ROUND_ROBIN
        assert lb.provider_count == 0
    
    def test_weighted_strategy(self):
        """Test weighted strategy initialization."""
        factory = MagicMock()
        health_checker = MagicMock()
        
        lb = LoadBalancer(factory, health_checker, strategy="weighted")
        
        assert lb.strategy == LoadBalanceStrategy.WEIGHTED
    
    def test_health_first_strategy(self):
        """Test health_first strategy initialization."""
        factory = MagicMock()
        health_checker = MagicMock()
        
        lb = LoadBalancer(factory, health_checker, strategy="health_first")
        
        assert lb.strategy == LoadBalanceStrategy.HEALTH_FIRST


class TestLoadBalancerRegister:
    """Test provider registration."""
    
    def test_register_single_provider(self):
        """Test registering a single provider."""
        factory = MagicMock()
        health_checker = MagicMock()
        lb = LoadBalancer(factory, health_checker)
        
        provider = MockProvider("test")
        lb.register_provider(provider)
        
        assert lb.provider_count == 1
        assert len(lb.get_all_providers()) == 1
        health_checker.register_provider.assert_called_once()
    
    def test_register_multiple_providers(self):
        """Test registering multiple providers."""
        factory = MagicMock()
        health_checker = MagicMock()
        lb = LoadBalancer(factory, health_checker)
        
        provider1 = MockProvider("p1")
        provider2 = MockProvider("p2")
        lb.register_provider(provider1)
        lb.register_provider(provider2)
        
        assert lb.provider_count == 2
        assert len(lb.get_all_providers()) == 2
        assert health_checker.register_provider.call_count == 2
    
    def test_register_with_weight(self):
        """Test registering provider with weight."""
        factory = MagicMock()
        health_checker = MagicMock()
        lb = LoadBalancer(factory, health_checker, strategy="weighted")
        
        provider = MockProvider("test")
        lb.register_provider(provider, weight=5)
        
        # Weight should be stored (accessible through internal dict)
        provider_name = list(lb._weights.keys())[0]
        assert lb._weights[provider_name] == 5
    
    def test_register_with_zero_weight(self):
        """Test registering provider with zero weight defaults to 1."""
        factory = MagicMock()
        health_checker = MagicMock()
        lb = LoadBalancer(factory, health_checker, strategy="weighted")
        
        provider = MockProvider("test")
        lb.register_provider(provider, weight=0)
        
        provider_name = list(lb._weights.keys())[0]
        assert lb._weights[provider_name] == 1


class TestLoadBalancerUnregister:
    """Test provider unregistration."""
    
    def test_unregister_provider(self):
        """Test unregistering a provider."""
        factory = MagicMock()
        health_checker = MagicMock()
        health_checker.is_healthy.return_value = True
        lb = LoadBalancer(factory, health_checker)
        
        provider = MockProvider("test")
        lb.register_provider(provider)
        
        # Get the auto-generated provider name
        provider_name = list(lb._providers.keys())[0]
        
        lb.unregister_provider(provider_name)
        
        assert lb.provider_count == 0
        health_checker.unregister_provider.assert_called_once_with(provider_name)
    
    def test_unregister_nonexistent(self):
        """Test unregistering non-existent provider is safe."""
        factory = MagicMock()
        health_checker = MagicMock()
        lb = LoadBalancer(factory, health_checker)
        
        # Should not raise
        lb.unregister_provider("nonexistent")
        
        assert lb.provider_count == 0


class TestRoundRobinStrategy:
    """Test round-robin load balancing strategy."""
    
    @pytest.mark.asyncio
    async def test_round_robin_single_provider(self):
        """Test round-robin with single provider."""
        factory = MagicMock()
        health_checker = MagicMock()
        health_checker.is_healthy.return_value = True
        lb = LoadBalancer(factory, health_checker, strategy="round_robin")
        
        provider = MockProvider("test")
        lb.register_provider(provider)
        
        # Should always return the same provider
        assert await lb.get_provider() is provider
        assert await lb.get_provider() is provider
    
    @pytest.mark.asyncio
    async def test_round_robin_multiple_providers(self):
        """Test round-robin cycles through providers."""
        factory = MagicMock()
        health_checker = MagicMock()
        health_checker.is_healthy.return_value = True
        lb = LoadBalancer(factory, health_checker, strategy="round_robin")
        
        provider1 = MockProvider("p1")
        provider2 = MockProvider("p2")
        lb.register_provider(provider1, name="p1")
        lb.register_provider(provider2, name="p2")
        
        # Should cycle through providers
        results = [await lb.get_provider() for _ in range(4)]
        assert results[0] is provider1
        assert results[1] is provider2
        assert results[2] is provider1  # Cycles back
        assert results[3] is provider2
    
    @pytest.mark.asyncio
    async def test_round_robin_skips_unhealthy(self):
        """Test round-robin skips unhealthy providers."""
        factory = MagicMock()
        health_checker = MagicMock()
        # First provider unhealthy, second healthy
        health_checker.is_healthy.side_effect = lambda name: name == "p2"
        lb = LoadBalancer(factory, health_checker, strategy="round_robin")
        
        provider1 = MockProvider("p1")
        provider2 = MockProvider("p2")
        lb.register_provider(provider1, name="p1")
        lb.register_provider(provider2, name="p2")
        
        # Should only return the healthy provider
        for _ in range(5):
            assert await lb.get_provider() is provider2
    
    @pytest.mark.asyncio
    async def test_round_robin_fallback_when_all_unhealthy(self):
        """Test round-robin falls back to all providers when none are healthy."""
        factory = MagicMock()
        health_checker = MagicMock()
        health_checker.is_healthy.return_value = False
        lb = LoadBalancer(factory, health_checker, strategy="round_robin")
        
        provider1 = MockProvider("p1")
        provider2 = MockProvider("p2")
        lb.register_provider(provider1, name="p1")
        lb.register_provider(provider2, name="p2")
        
        # Should cycle through all providers when none are healthy
        results = [await lb.get_provider() for _ in range(4)]
        assert results[0] is provider1
        assert results[1] is provider2
        assert results[2] is provider1
        assert results[3] is provider2


class TestWeightedStrategy:
    """Test weighted load balancing strategy."""
    
    @pytest.mark.asyncio
    async def test_weighted_selection(self):
        """Test weighted selection favors higher weights."""
        factory = MagicMock()
        health_checker = MagicMock()
        health_checker.is_healthy.return_value = True
        lb = LoadBalancer(factory, health_checker, strategy="weighted")
        
        provider1 = MockProvider("heavy")
        provider2 = MockProvider("light")
        lb.register_provider(provider1, weight=3)
        lb.register_provider(provider2, weight=1)
        
        # Collect many samples to verify distribution
        results = {provider1: 0, provider2: 0}
        for _ in range(1000):
            p = await lb.get_provider()
            results[p] += 1
        
        # Heavy provider should be selected ~75% of the time (3:1 ratio)
        heavy_ratio = results[provider1] / sum(results.values())
        assert 0.65 < heavy_ratio < 0.85, f"Heavy provider ratio was {heavy_ratio}"
    
    @pytest.mark.asyncio
    async def test_weighted_skips_unhealthy(self):
        """Test weighted skips unhealthy providers."""
        factory = MagicMock()
        health_checker = MagicMock()
        health_checker.is_healthy.side_effect = lambda name: name == "healthy"
        lb = LoadBalancer(factory, health_checker, strategy="weighted")
        
        provider1 = MockProvider("unhealthy")
        provider2 = MockProvider("healthy")
        lb.register_provider(provider1, name="unhealthy", weight=10)  # High weight, but unhealthy
        lb.register_provider(provider2, name="healthy", weight=1)
        
        # Should always return the healthy provider
        for _ in range(10):
            assert await lb.get_provider() is provider2
    
    @pytest.mark.asyncio
    async def test_weighted_fallback_when_all_unhealthy(self):
        """Test weighted falls back to all providers when none are healthy."""
        factory = MagicMock()
        health_checker = MagicMock()
        health_checker.is_healthy.return_value = False
        lb = LoadBalancer(factory, health_checker, strategy="weighted")
        
        provider1 = MockProvider("p1")
        provider2 = MockProvider("p2")
        lb.register_provider(provider1, name="p1", weight=3)
        lb.register_provider(provider2, name="p2", weight=1)
        
        # Should still return providers even when all are unhealthy
        results = set()
        for _ in range(20):
            results.add(await lb.get_provider())
        
        assert provider1 in results
        assert provider2 in results


class TestHealthFirstStrategy:
    """Test health-first load balancing strategy."""
    
    @pytest.mark.asyncio
    async def test_health_first_round_robin(self):
        """Test health-first uses round-robin among healthy providers."""
        factory = MagicMock()
        health_checker = MagicMock()
        health_checker.is_healthy.return_value = True
        lb = LoadBalancer(factory, health_checker, strategy="health_first")
        
        provider1 = MockProvider("p1")
        provider2 = MockProvider("p2")
        lb.register_provider(provider1, name="p1")
        lb.register_provider(provider2, name="p2")
        
        # Should cycle through healthy providers
        results = [await lb.get_provider() for _ in range(4)]
        assert results[0] is provider1
        assert results[1] is provider2
        assert results[2] is provider1
        assert results[3] is provider2
    
    @pytest.mark.asyncio
    async def test_health_first_skips_unhealthy(self):
        """Test health-first skips unhealthy providers."""
        factory = MagicMock()
        health_checker = MagicMock()
        health_checker.is_healthy.side_effect = lambda name: name == "healthy"
        lb = LoadBalancer(factory, health_checker, strategy="health_first")
        
        provider1 = MockProvider("unhealthy")
        provider2 = MockProvider("healthy")
        lb.register_provider(provider1, name="unhealthy")
        lb.register_provider(provider2, name="healthy")
        
        # Should only return healthy providers
        for _ in range(5):
            assert await lb.get_provider() is provider2
    
    @pytest.mark.asyncio
    async def test_health_first_error_when_no_healthy(self):
        """Test health-first raises error when no healthy providers."""
        factory = MagicMock()
        health_checker = MagicMock()
        health_checker.is_healthy.return_value = False
        lb = LoadBalancer(factory, health_checker, strategy="health_first")
        
        provider = MockProvider("unhealthy")
        lb.register_provider(provider)
        
        with pytest.raises(RuntimeError, match="No healthy providers available"):
            await lb.get_provider()


class TestGetProviderErrors:
    """Test error handling in get_provider."""
    
    @pytest.mark.asyncio
    async def test_get_provider_no_providers(self):
        """Test get_provider raises error when no providers registered."""
        factory = MagicMock()
        health_checker = MagicMock()
        lb = LoadBalancer(factory, health_checker)
        
        with pytest.raises(RuntimeError, match="No providers registered"):
            await lb.get_provider()


class TestGetAllProviders:
    """Test get_all_providers method."""
    
    def test_get_all_providers_empty(self):
        """Test get_all_providers returns empty list when no providers."""
        factory = MagicMock()
        health_checker = MagicMock()
        lb = LoadBalancer(factory, health_checker)
        
        assert lb.get_all_providers() == []
    
    def test_get_all_providers_returns_all(self):
        """Test get_all_providers returns all registered providers."""
        factory = MagicMock()
        health_checker = MagicMock()
        lb = LoadBalancer(factory, health_checker)
        
        provider1 = MockProvider("p1")
        provider2 = MockProvider("p2")
        lb.register_provider(provider1)
        lb.register_provider(provider2)
        
        providers = lb.get_all_providers()
        assert len(providers) == 2
        assert provider1 in providers
        assert provider2 in providers


class TestGetAvailableProviders:
    """Test get_available_providers method."""
    
    def test_get_available_providers_empty(self):
        """Test get_available_providers returns empty list when no providers."""
        factory = MagicMock()
        health_checker = MagicMock()
        lb = LoadBalancer(factory, health_checker)
        
        assert lb.get_available_providers() == []
    
    def test_get_available_providers_only_healthy(self):
        """Test get_available_providers returns only healthy providers."""
        factory = MagicMock()
        health_checker = MagicMock()
        health_checker.is_healthy.side_effect = lambda name: name == "healthy"
        lb = LoadBalancer(factory, health_checker)
        
        provider1 = MockProvider("unhealthy")
        provider2 = MockProvider("healthy")
        lb.register_provider(provider1, name="unhealthy")
        lb.register_provider(provider2, name="healthy")
        
        available = lb.get_available_providers()
        assert len(available) == 1
        assert provider2 in available


class TestStrategyProperty:
    """Test strategy property getter and setter."""
    
    def test_strategy_getter(self):
        """Test strategy property getter."""
        factory = MagicMock()
        health_checker = MagicMock()
        lb = LoadBalancer(factory, health_checker, strategy="weighted")
        
        assert lb.strategy == LoadBalanceStrategy.WEIGHTED
    
    def test_strategy_setter(self):
        """Test strategy property setter."""
        factory = MagicMock()
        health_checker = MagicMock()
        lb = LoadBalancer(factory, health_checker, strategy="round_robin")
        
        lb.strategy = "health_first"
        
        assert lb.strategy == LoadBalanceStrategy.HEALTH_FIRST


class TestProviderCount:
    """Test provider_count property."""
    
    def test_provider_count_empty(self):
        """Test provider_count is 0 when no providers."""
        factory = MagicMock()
        health_checker = MagicMock()
        lb = LoadBalancer(factory, health_checker)
        
        assert lb.provider_count == 0
    
    def test_provider_count_with_providers(self):
        """Test provider_count reflects registered providers."""
        factory = MagicMock()
        health_checker = MagicMock()
        lb = LoadBalancer(factory, health_checker)
        
        lb.register_provider(MockProvider("p1"))
        assert lb.provider_count == 1
        
        lb.register_provider(MockProvider("p2"))
        assert lb.provider_count == 2


class TestHealthyCount:
    """Test healthy_count property."""
    
    def test_healthy_count_all_healthy(self):
        """Test healthy_count when all providers are healthy."""
        factory = MagicMock()
        health_checker = MagicMock()
        health_checker.is_healthy.return_value = True
        lb = LoadBalancer(factory, health_checker)
        
        lb.register_provider(MockProvider("p1"))
        lb.register_provider(MockProvider("p2"))
        
        assert lb.healthy_count == 2
    
    def test_healthy_count_some_healthy(self):
        """Test healthy_count with mixed health status."""
        factory = MagicMock()
        health_checker = MagicMock()
        health_checker.is_healthy.side_effect = lambda name: name == "p1"
        lb = LoadBalancer(factory, health_checker)
        
        lb.register_provider(MockProvider("p1"), name="p1")
        lb.register_provider(MockProvider("p2"), name="p2")
        
        assert lb.healthy_count == 1
    
    def test_healthy_count_none_healthy(self):
        """Test healthy_count when no providers are healthy."""
        factory = MagicMock()
        health_checker = MagicMock()
        health_checker.is_healthy.return_value = False
        lb = LoadBalancer(factory, health_checker)
        
        lb.register_provider(MockProvider("p1"))
        
        assert lb.healthy_count == 0


class TestAsyncConcurrency:
    """Test async concurrency safety of load balancer."""
    
    @pytest.mark.asyncio
    async def test_round_robin_async_concurrency(self):
        """Test round-robin is safe with concurrent async access."""
        factory = MagicMock()
        health_checker = MagicMock()
        health_checker.is_healthy.return_value = True
        lb = LoadBalancer(factory, health_checker, strategy="round_robin")
        
        provider1 = MockProvider("p1")
        provider2 = MockProvider("p2")
        lb.register_provider(provider1)
        lb.register_provider(provider2)
        
        results = []
        
        async def get_providers():
            for _ in range(100):
                results.append(await lb.get_provider())
        
        # Run multiple concurrent tasks
        tasks = [get_providers() for _ in range(5)]
        await asyncio.gather(*tasks)
        
        # Should have collected all results without errors
        assert len(results) == 500
        # Both providers should have been selected
        assert provider1 in results
        assert provider2 in results


class TestProviderNameGeneration:
    """Test provider name generation."""
    
    def test_provider_name_unique(self):
        """Test generated provider names are unique."""
        factory = MagicMock()
        health_checker = MagicMock()
        lb = LoadBalancer(factory, health_checker)
        
        provider1 = MockProvider("same")
        provider2 = MockProvider("same")  # Same name, different instance
        lb.register_provider(provider1)
        lb.register_provider(provider2)
        
        names = list(lb._providers.keys())
        assert len(names) == 2
        assert names[0] != names[1]  # Names should be unique
