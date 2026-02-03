"""Tests for ProviderFactory and multi-provider support."""

import asyncio
import os
from unittest.mock import MagicMock, patch

import pytest

from gateway.app.providers.base import BaseProvider
from gateway.app.providers.deepseek import DeepSeekProvider
from gateway.app.providers.factory import (
    ProviderConfig,
    ProviderFactory,
    ProviderType,
    create_provider,
    get_primary_provider,
    get_provider_factory,
    reset_provider_factory,
)
from gateway.app.providers.openai import OpenAIProvider


# Save original environment variables (excluding pytest's own vars)
_ORIG_ENV = {k: v for k, v in os.environ.items() if k != "PYTEST_CURRENT_TEST"}


def _reset_test_env():
    """Reset environment to clean state for testing."""
    # Clear provider-specific env vars only
    for key in list(os.environ.keys()):
        if key.startswith(("DEEPSEEK_", "OPENAI_", "ANTHROPIC_")):
            del os.environ[key]
    # Also clear mock provider mode to ensure proper config loading
    os.environ.pop("TEACHPROXY_MOCK_PROVIDER", None)


@pytest.fixture(autouse=True)
def reset_env_and_factory():
    """Reset environment and factory before each test."""
    _reset_test_env()
    reset_provider_factory()
    yield
    _reset_test_env()
    reset_provider_factory()


class TestProviderType:
    """Test ProviderType enum."""
    
    def test_provider_type_values(self):
        """Test provider type enum values."""
        assert ProviderType.DEEPSEEK.value == "deepseek"
        assert ProviderType.OPENAI.value == "openai"


class TestProviderConfig:
    """Test ProviderConfig dataclass."""
    
    def test_basic_config(self):
        """Test creating a basic config."""
        config = ProviderConfig(
            provider_type=ProviderType.DEEPSEEK,
            base_url="https://api.deepseek.com/v1",
            api_key="test-key"
        )
        assert config.provider_type == ProviderType.DEEPSEEK
        assert config.base_url == "https://api.deepseek.com/v1"
        assert config.api_key == "test-key"
        assert config.timeout == 60.0
        assert config.priority == 1
        assert config.enabled is True
    
    def test_config_with_optional_fields(self):
        """Test config with all optional fields."""
        config = ProviderConfig(
            provider_type=ProviderType.OPENAI,
            base_url="https://api.openai.com/v1",
            api_key="test-key",
            organization="org-test",
            timeout=30.0,
            priority=2,
            enabled=False
        )
        assert config.organization == "org-test"
        assert config.timeout == 30.0
        assert config.priority == 2
        assert config.enabled is False
    
    @patch.dict(os.environ, {
        "DEEPSEEK_API_KEY": "env-key",
        "DEEPSEEK_BASE_URL": "https://custom.deepseek.com",
        "DEEPSEEK_TIMEOUT": "45.0",
        "DEEPSEEK_PRIORITY": "2",
        "DEEPSEEK_ENABLED": "false"
    })
    def test_from_env(self):
        """Test loading config from environment."""
        config = ProviderConfig.from_env("DEEPSEEK", ProviderType.DEEPSEEK)
        
        assert config is not None
        assert config.api_key == "env-key"
        assert config.base_url == "https://custom.deepseek.com"
        assert config.timeout == 45.0
        assert config.priority == 2
        assert config.enabled is False
    
    @patch.dict(os.environ, {}, clear=True)
    def test_from_env_missing_key(self):
        """Test loading config when API key is missing."""
        config = ProviderConfig.from_env("DEEPSEEK", ProviderType.DEEPSEEK)
        assert config is None
    
    @patch.dict(os.environ, {"DEEPSEEK_API_KEY": "key"})
    def test_from_env_defaults(self):
        """Test loading config uses defaults for optional values."""
        config = ProviderConfig.from_env("DEEPSEEK", ProviderType.DEEPSEEK)
        
        assert config.base_url == "https://api.deepseek.com/v1"
        assert config.timeout == 60.0
        assert config.priority == 1
        assert config.enabled is True


class TestProviderFactory:
    """Test ProviderFactory."""

    @patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key"})
    def test_create_deepseek_provider(self):
        """Test creating a DeepSeek provider."""
        factory = ProviderFactory()
        provider = factory.create_provider(ProviderType.DEEPSEEK)
        
        assert isinstance(provider, DeepSeekProvider)
    
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_create_openai_provider(self):
        """Test creating an OpenAI provider."""
        factory = ProviderFactory()
        provider = factory.create_provider(ProviderType.OPENAI)
        
        assert isinstance(provider, OpenAIProvider)
    
    def test_create_provider_unsupported_type(self):
        """Test creating provider with unsupported type."""
        factory = ProviderFactory()
        
        with pytest.raises(ValueError, match="Unsupported provider type"):
            # Create a mock enum value
            class MockType:
                value = "unsupported"
            factory.create_provider(MockType())  # type: ignore
    
    def test_create_provider_no_config(self):
        """Test creating provider without configuration."""
        factory = ProviderFactory()
        
        with pytest.raises(RuntimeError, match="No configuration available"):
            factory.create_provider(ProviderType.OPENAI)
    
    @patch.dict(os.environ, {
        "DEEPSEEK_API_KEY": "deepseek-key",
        "OPENAI_API_KEY": "openai-key",
        "OPENAI_PRIORITY": "1",  # Higher priority (lower number)
        "DEEPSEEK_PRIORITY": "2"
    })
    def test_create_primary_provider(self):
        """Test creating primary provider (by priority)."""
        factory = ProviderFactory()
        provider = factory.create_primary_provider()
        
        # OpenAI has priority 1, should be primary
        assert isinstance(provider, OpenAIProvider)
    
    @patch.dict(os.environ, {"DEEPSEEK_API_KEY": "key"})
    def test_create_primary_provider_single(self):
        """Test creating primary provider when only one is configured."""
        factory = ProviderFactory()
        provider = factory.create_primary_provider()
        
        assert isinstance(provider, DeepSeekProvider)
    
    @patch("gateway.app.providers.factory_config.settings")
    def test_create_primary_provider_none(self, mock_settings):
        """Test error when no providers are configured."""
        # Ensure no providers are configured
        mock_settings.deepseek_api_key = ""
        mock_settings.deepseek_base_url = ""
        
        factory = ProviderFactory()
        factory._configs = {}  # Clear any loaded configs
        
        with pytest.raises(RuntimeError, match="No providers are configured"):
            factory.create_primary_provider()
    
    @patch.dict(os.environ, {
        "DEEPSEEK_API_KEY": "deepseek-key",
        "OPENAI_API_KEY": "openai-key",
        "DEEPSEEK_PRIORITY": "1",
        "OPENAI_PRIORITY": "2"
    })
    def test_get_fallback_providers(self):
        """Test getting fallback providers."""
        factory = ProviderFactory()
        fallbacks = factory.get_fallback_providers()
        
        # DeepSeek is primary (priority 1), OpenAI is fallback (priority 2)
        assert len(fallbacks) == 1
        assert isinstance(fallbacks[0], OpenAIProvider)
    
    @patch.dict(os.environ, {"DEEPSEEK_API_KEY": "key"})
    def test_get_fallback_providers_single(self):
        """Test getting fallbacks when only one provider."""
        factory = ProviderFactory()
        fallbacks = factory.get_fallback_providers()
        
        assert len(fallbacks) == 0
    
    @patch.dict(os.environ, {
        "DEEPSEEK_API_KEY": "key",
        "OPENAI_API_KEY": "openai-key"
    })
    def test_list_configured_providers(self):
        """Test listing configured providers."""
        factory = ProviderFactory()
        providers = factory.list_configured_providers()
        
        assert ProviderType.DEEPSEEK in providers
        assert ProviderType.OPENAI in providers
        assert len(providers) == 2
    
    @patch.dict(os.environ, {"DEEPSEEK_API_KEY": "key"})
    def test_is_provider_configured(self):
        """Test checking if provider is configured."""
        factory = ProviderFactory()
        
        assert factory.is_provider_configured(ProviderType.DEEPSEEK) is True
        assert factory.is_provider_configured(ProviderType.OPENAI) is False


class TestGlobalFunctions:
    """Test global convenience functions."""

    def test_get_provider_factory_singleton(self):
        """Test factory singleton pattern."""
        factory1 = get_provider_factory()
        factory2 = get_provider_factory()
        
        assert factory1 is factory2
    
    @patch.dict(os.environ, {"DEEPSEEK_API_KEY": "key"})
    def test_create_provider_convenience(self):
        """Test create_provider convenience function."""
        provider = create_provider(ProviderType.DEEPSEEK)
        
        assert isinstance(provider, DeepSeekProvider)
    
    @patch.dict(os.environ, {"DEEPSEEK_API_KEY": "key"})
    def test_get_primary_provider_convenience(self):
        """Test get_primary_provider convenience function."""
        provider = get_primary_provider()
        
        assert isinstance(provider, DeepSeekProvider)
    
    def test_reset_provider_factory(self):
        """Test reset_provider_factory clears singleton."""
        factory1 = get_provider_factory()
        reset_provider_factory()
        factory2 = get_provider_factory()
        
        assert factory1 is not factory2


class TestProviderWithHttpClient:
    """Test provider factory with shared HTTP client."""

    @patch.dict(os.environ, {"DEEPSEEK_API_KEY": "key"})
    def test_http_client_passed_to_provider(self):
        """Test that HTTP client is passed to created providers."""
        mock_client = MagicMock()
        factory = ProviderFactory(http_client=mock_client)
        
        provider = factory.create_provider(ProviderType.DEEPSEEK)
        
        assert provider.http_client is mock_client
    
    @patch.dict(os.environ, {
        "DEEPSEEK_API_KEY": "key",
        "OPENAI_API_KEY": "openai-key"
    })
    def test_http_client_shared_across_providers(self):
        """Test that HTTP client is shared across all created providers."""
        mock_client = MagicMock()
        factory = ProviderFactory(http_client=mock_client)
        
        deepseek = factory.create_provider(ProviderType.DEEPSEEK)
        openai = factory.create_provider(ProviderType.OPENAI)
        
        assert deepseek.http_client is mock_client
        assert openai.http_client is mock_client



class TestBaseProviderHealthCheck:
    """Test BaseProvider health_check method."""
    
    @pytest.mark.asyncio
    async def test_health_check_success(self, respx_mock):
        """Test health check returns True on success."""
        import httpx
        
        provider = OpenAIProvider(
            base_url="https://api.openai.com/v1",
            api_key="test-key"
        )
        
        # Mock the /models endpoint with proper httpx.Response
        respx_mock.get("https://api.openai.com/v1/models").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        
        result = await provider.health_check()
        assert result is True
    
    @pytest.mark.asyncio
    async def test_health_check_failure_status_code(self, respx_mock):
        """Test health check returns False on non-200 status."""
        import httpx
        
        provider = OpenAIProvider(
            base_url="https://api.openai.com/v1",
            api_key="test-key"
        )
        
        # Mock the /models endpoint with 500 error
        respx_mock.get("https://api.openai.com/v1/models").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        
        result = await provider.health_check()
        assert result is False
    
    @pytest.mark.asyncio
    async def test_health_check_exception(self, respx_mock):
        """Test health check returns False on exception."""
        provider = OpenAIProvider(
            base_url="https://api.openai.com/v1",
            api_key="test-key"
        )
        
        # Mock the /models endpoint to raise exception
        respx_mock.get("https://api.openai.com/v1/models").mock(side_effect=Exception("Connection error"))
        
        result = await provider.health_check()
        assert result is False
    
    @pytest.mark.asyncio
    async def test_health_check_timeout_parameter(self, respx_mock):
        """Test health check uses custom timeout."""
        import httpx
        
        provider = OpenAIProvider(
            base_url="https://api.openai.com/v1",
            api_key="test-key"
        )
        
        # Mock the /models endpoint with proper httpx.Response
        respx_mock.get("https://api.openai.com/v1/models").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        
        # The base implementation uses a 2.0s default timeout
        result = await provider.health_check(timeout=5.0)
        # We verify the method completes without error
        assert result is True


class TestProviderHealthChecker:
    """Test ProviderHealthChecker class."""
    
    @pytest.mark.asyncio
    async def test_register_provider(self):
        """Test registering providers."""
        from gateway.app.providers.health import ProviderHealthChecker
        
        checker = ProviderHealthChecker()
        provider = OpenAIProvider(
            base_url="https://api.openai.com/v1",
            api_key="test-key"
        )
        
        checker.register_provider("openai", provider)
        
        assert "openai" in checker.get_all_status()
        assert checker.is_healthy("openai") is True  # Initially healthy
    
    @pytest.mark.asyncio
    async def test_unregister_provider(self):
        """Test unregistering providers."""
        from gateway.app.providers.health import ProviderHealthChecker
        
        checker = ProviderHealthChecker()
        provider = OpenAIProvider(
            base_url="https://api.openai.com/v1",
            api_key="test-key"
        )
        
        checker.register_provider("openai", provider)
        checker.unregister_provider("openai")
        
        assert "openai" not in checker.get_all_status()
        assert checker.is_healthy("openai") is False  # Not registered = unhealthy
    
    @pytest.mark.asyncio
    async def test_is_healthy_unregistered(self):
        """Test is_healthy returns False for unregistered provider."""
        from gateway.app.providers.health import ProviderHealthChecker
        
        checker = ProviderHealthChecker()
        
        assert checker.is_healthy("unknown") is False
    
    @pytest.mark.asyncio
    async def test_check_all_healthy(self):
        """Test check_all updates health status."""
        from gateway.app.providers.health import ProviderHealthChecker
        
        checker = ProviderHealthChecker()
        provider = OpenAIProvider(
            base_url="https://api.openai.com/v1",
            api_key="test-key"
        )
        
        checker.register_provider("openai", provider)
        
        # Mock the provider's health_check
        with patch.object(provider, 'health_check', return_value=True):
            result = await checker.check_all()
            
        assert result["openai"] is True
        assert checker.is_healthy("openai") is True
    
    @pytest.mark.asyncio
    async def test_check_all_unhealthy(self):
        """Test check_all handles unhealthy providers."""
        from gateway.app.providers.health import ProviderHealthChecker
        
        checker = ProviderHealthChecker()
        provider = OpenAIProvider(
            base_url="https://api.openai.com/v1",
            api_key="test-key"
        )
        
        checker.register_provider("openai", provider)
        
        # Mock the provider's health_check to fail
        with patch.object(provider, 'health_check', return_value=False):
            result = await checker.check_all()
            
        assert result["openai"] is False
        assert checker.is_healthy("openai") is False
    
    @pytest.mark.asyncio
    async def test_check_all_exception(self):
        """Test check_all handles exceptions gracefully."""
        from gateway.app.providers.health import ProviderHealthChecker
        
        checker = ProviderHealthChecker()
        provider = OpenAIProvider(
            base_url="https://api.openai.com/v1",
            api_key="test-key"
        )
        
        checker.register_provider("openai", provider)
        
        # Mock the provider's health_check to raise exception
        with patch.object(provider, 'health_check', side_effect=Exception("Failed")):
            result = await checker.check_all()
            
        assert result["openai"] is False
        assert checker.is_healthy("openai") is False
    
    @pytest.mark.asyncio
    async def test_check_all_multiple_providers(self):
        """Test check_all with multiple providers."""
        from gateway.app.providers.health import ProviderHealthChecker
        
        checker = ProviderHealthChecker()
        openai = OpenAIProvider(
            base_url="https://api.openai.com/v1",
            api_key="test-key"
        )
        deepseek = DeepSeekProvider(
            base_url="https://api.deepseek.com/v1",
            api_key="test-key"
        )
        
        checker.register_provider("openai", openai)
        checker.register_provider("deepseek", deepseek)
        
        with patch.object(openai, 'health_check', return_value=True), \
             patch.object(deepseek, 'health_check', return_value=False):
            result = await checker.check_all()
        
        assert result["openai"] is True
        assert result["deepseek"] is False
    
    @pytest.mark.asyncio
    async def test_start_stop(self):
        """Test starting and stopping the background task."""
        from gateway.app.providers.health import ProviderHealthChecker
        
        checker = ProviderHealthChecker(check_interval=0.1)
        provider = OpenAIProvider(
            base_url="https://api.openai.com/v1",
            api_key="test-key"
        )
        
        checker.register_provider("openai", provider)
        
        # Mock health_check
        with patch.object(provider, 'health_check', return_value=True):
            await checker.start()
            assert checker._task is not None
            
            # Let it run for a bit
            await asyncio.sleep(0.15)
            
            await checker.stop()
            assert checker._task is None
    
    @pytest.mark.asyncio
    async def test_stop_no_start(self):
        """Test stopping when not started is safe."""
        from gateway.app.providers.health import ProviderHealthChecker
        
        checker = ProviderHealthChecker()
        
        # Should not raise
        await checker.stop()
        assert checker._task is None
    
    @pytest.mark.asyncio
    async def test_start_already_running(self):
        """Test starting when already running doesn't create duplicate task."""
        from gateway.app.providers.health import ProviderHealthChecker
        
        checker = ProviderHealthChecker(check_interval=60.0)
        provider = OpenAIProvider(
            base_url="https://api.openai.com/v1",
            api_key="test-key"
        )
        
        checker.register_provider("openai", provider)
        
        with patch.object(provider, 'health_check', return_value=True):
            await checker.start()
            task1 = checker._task
            
            # Try to start again
            await checker.start()
            task2 = checker._task
            
            assert task1 is task2
            
            await checker.stop()
    
    @pytest.mark.asyncio
    async def test_get_all_status_isolation(self):
        """Test get_all_status returns a copy."""
        from gateway.app.providers.health import ProviderHealthChecker
        
        checker = ProviderHealthChecker()
        provider = OpenAIProvider(
            base_url="https://api.openai.com/v1",
            api_key="test-key"
        )
        
        checker.register_provider("openai", provider)
        
        status1 = checker.get_all_status()
        status1["openai"] = False  # Modify the copy
        
        # Original should be unchanged
        status2 = checker.get_all_status()
        assert status2["openai"] is True
