"""Provider configuration parsing utilities.

This module provides configuration parsing logic for provider setup,
separated from the main factory to keep module size manageable.
"""

from __future__ import annotations

import os
from enum import Enum
from typing import TYPE_CHECKING, Dict, Optional

from gateway.app.core.config import settings
from gateway.app.core.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class ProviderType(str, Enum):
    """Supported provider types."""

    DEEPSEEK = "deepseek"
    OPENAI = "openai"
    MOCK = "mock"


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
        enabled: bool = True,
    ):
        self.provider_type = provider_type
        self.base_url = base_url
        self.api_key = api_key
        self.organization = organization
        self.timeout = timeout
        self.priority = priority
        self.enabled = enabled

    @classmethod
    def from_env(
        cls, prefix: str, provider_type: ProviderType
    ) -> Optional["ProviderConfig"]:
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
        organization = (
            os.getenv(f"{prefix}_ORGANIZATION")
            if provider_type == ProviderType.OPENAI
            else None
        )
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
            enabled=enabled,
        )


def is_mock_mode() -> bool:
    """Check if mock provider mode is enabled.

    Returns:
        True if TEACHPROXY_MOCK_PROVIDER is set to "true"
    """
    return os.getenv("TEACHPROXY_MOCK_PROVIDER", "").lower() == "true"


def load_deepseek_config() -> Optional[ProviderConfig]:
    """Load DeepSeek provider configuration.

    Returns:
        ProviderConfig if configured, None otherwise
    """
    # Try environment variables first
    config = ProviderConfig.from_env("DEEPSEEK", ProviderType.DEEPSEEK)
    if config:
        return config

    # Fallback to settings
    if settings.deepseek_api_key:
        return ProviderConfig(
            provider_type=ProviderType.DEEPSEEK,
            base_url=settings.deepseek_base_url,
            api_key=settings.deepseek_api_key,
        )

    return None


def load_openai_config() -> Optional[ProviderConfig]:
    """Load OpenAI provider configuration.

    Returns:
        ProviderConfig if configured, None otherwise
    """
    return ProviderConfig.from_env("OPENAI", ProviderType.OPENAI)


def load_all_provider_configs() -> Dict[ProviderType, ProviderConfig]:
    """Load all provider configurations.

    Returns:
        Dictionary mapping provider types to their configurations
    """
    configs: Dict[ProviderType, ProviderConfig] = {}

    # Check if mock provider is forced (for testing)
    if is_mock_mode():
        logger.info("Mock provider mode enabled, skipping real provider configuration")
        return configs

    # Load DeepSeek config
    deepseek_config = load_deepseek_config()
    if deepseek_config:
        configs[ProviderType.DEEPSEEK] = deepseek_config

    # Load OpenAI config
    openai_config = load_openai_config()
    if openai_config:
        configs[ProviderType.OPENAI] = openai_config

    return configs
