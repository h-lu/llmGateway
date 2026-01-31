"""
Pytest configuration for stress tests.

This conftest.py ensures environment variables are properly scoped to stress tests only,
preventing interference with other test modules.
"""

import os
from typing import Dict

import pytest


@pytest.fixture(autouse=True, scope="module")
def configure_stress_test_environment():
    """
    Configure environment for stress tests.

    This fixture is session-scoped to the stress test directory, ensuring
    environment variables are set before any stress test runs and restored
    after all stress tests complete.

    Using conftest.py in the stress/ directory ensures this fixture only
    applies to tests within this directory.
    """
    # Save original environment values
    original_values: Dict[str, str | None] = {
        "TEACHPROXY_MOCK_PROVIDER": os.environ.get("TEACHPROXY_MOCK_PROVIDER"),
        "DEEPSEEK_API_KEY": os.environ.get("DEEPSEEK_API_KEY"),
        "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
        "RATE_LIMIT_REQUESTS_PER_MINUTE": os.environ.get("RATE_LIMIT_REQUESTS_PER_MINUTE"),
        "RATE_LIMIT_BURST_SIZE": os.environ.get("RATE_LIMIT_BURST_SIZE"),
    }

    # Set stress test environment
    os.environ["TEACHPROXY_MOCK_PROVIDER"] = "true"
    os.environ.pop("DEEPSEEK_API_KEY", None)
    os.environ.pop("OPENAI_API_KEY", None)
    os.environ["RATE_LIMIT_REQUESTS_PER_MINUTE"] = "10000"
    os.environ["RATE_LIMIT_BURST_SIZE"] = "1000"

    yield

    # Restore original environment values after all stress tests
    for key, value in original_values.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
