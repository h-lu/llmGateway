"""Shared HTTP client management for connection pooling.

This module provides a singleton-like HTTP client that is initialized
on application startup and shared across all providers for optimal
connection reuse.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import httpx

from gateway.app.core.config import settings


# Shared HTTP client for connection pooling
_shared_http_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """Get the shared HTTP client instance.

    This client should be initialized during application lifespan startup
    and reused across all requests for optimal connection pooling.

    Raises:
        RuntimeError: If the HTTP client has not been initialized.
    """
    if _shared_http_client is None:
        raise RuntimeError(
            "HTTP client not initialized. Ensure lifespan context is active."
        )
    return _shared_http_client


@asynccontextmanager
async def init_http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Initialize and yield the shared HTTP client.

    This context manager should be used in the FastAPI lifespan:

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            async with init_http_client():
                yield
    """
    global _shared_http_client

    # Configure connection pool limits
    limits = httpx.Limits(
        max_connections=settings.httpx_max_connections,
        max_keepalive_connections=settings.httpx_max_keepalive_connections,
        keepalive_expiry=settings.httpx_keepalive_expiry,
    )

    # Configure granular timeouts per Context7 best practices
    # - connect: Time to establish socket connection
    # - read: Time to read response data (streaming responses need more time)
    # - write: Time to send request data
    # - pool: Time to acquire connection from pool
    timeout = httpx.Timeout(
        connect=settings.httpx_connect_timeout,
        read=settings.httpx_read_timeout,
        write=settings.httpx_write_timeout,
        pool=settings.httpx_pool_timeout,
    )

    # Initialize shared HTTP client
    _shared_http_client = httpx.AsyncClient(timeout=timeout, limits=limits)

    try:
        yield _shared_http_client
    finally:
        if _shared_http_client is not None:
            await _shared_http_client.aclose()
            _shared_http_client = None


def create_http_client(**kwargs) -> httpx.AsyncClient:
    """Create a new HTTP client with default settings.

    This is useful for creating custom clients when the shared client
    is not appropriate (e.g., for testing or special use cases).

    Note: The returned client should be closed when done:
        async with create_http_client() as client:
            # use client
            pass

    Args:
        **kwargs: Override default settings. Can include:
            - timeout: Single timeout value (overrides all granular timeouts)
            - connect_timeout: Connection timeout
            - read_timeout: Read timeout
            - write_timeout: Write timeout
            - pool_timeout: Pool acquisition timeout
            - max_connections: Maximum connections
            - max_keepalive_connections: Maximum keepalive connections
            - keepalive_expiry: Keepalive expiration time

    Returns:
        A new httpx.AsyncClient instance with granular timeout configuration.
    """
    # Use granular timeouts for consistency with init_http_client()
    # Allow single timeout override for backward compatibility
    timeout_override = kwargs.get("timeout")
    if timeout_override is not None:
        timeout = httpx.Timeout(timeout_override)
    else:
        timeout = httpx.Timeout(
            connect=kwargs.get("connect_timeout", settings.httpx_connect_timeout),
            read=kwargs.get("read_timeout", settings.httpx_read_timeout),
            write=kwargs.get("write_timeout", settings.httpx_write_timeout),
            pool=kwargs.get("pool_timeout", settings.httpx_pool_timeout),
        )

    config = {
        "timeout": timeout,
        "limits": httpx.Limits(
            max_connections=kwargs.get(
                "max_connections", settings.httpx_max_connections
            ),
            max_keepalive_connections=kwargs.get(
                "max_keepalive_connections", settings.httpx_max_keepalive_connections
            ),
            keepalive_expiry=kwargs.get(
                "keepalive_expiry", settings.httpx_keepalive_expiry
            ),
        ),
    }
    return httpx.AsyncClient(**config)
