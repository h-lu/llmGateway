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
        raise RuntimeError("HTTP client not initialized. Ensure lifespan context is active.")
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
        keepalive_expiry=settings.httpx_keepalive_expiry
    )
    
    # Initialize shared HTTP client
    _shared_http_client = httpx.AsyncClient(
        timeout=settings.httpx_timeout,
        limits=limits
    )
    
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
    
    Args:
        **kwargs: Override default settings.
        
    Returns:
        A new httpx.AsyncClient instance.
    """
    config = {
        "timeout": kwargs.get("timeout", settings.httpx_timeout),
        "limits": httpx.Limits(
            max_connections=kwargs.get("max_connections", settings.httpx_max_connections),
            max_keepalive_connections=kwargs.get(
                "max_keepalive_connections", settings.httpx_max_keepalive_connections
            ),
            keepalive_expiry=kwargs.get("keepalive_expiry", settings.httpx_keepalive_expiry)
        )
    }
    return httpx.AsyncClient(**config)
