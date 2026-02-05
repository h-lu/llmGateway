"""Cache abstraction layer for the gateway application.

Provides a pluggable cache backend system with in-memory and Redis implementations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import asyncio
import time


@dataclass
class _CacheEntry:
    """Internal cache entry with TTL tracking."""

    value: bytes
    expires_at: float | None = None

    def is_expired(self) -> bool:
        """Check if the entry has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at


class CacheBackend(ABC):
    """Abstract base class for cache backends.

    All cache implementations must inherit from this class and implement
    the abstract methods.
    """

    @abstractmethod
    async def get(self, key: str) -> bytes | None:
        """Retrieve a value from the cache.

        Args:
            key: The cache key to look up.

        Returns:
            The cached value as bytes, or None if not found or expired.
        """
        pass

    @abstractmethod
    async def set(self, key: str, value: bytes, ttl: int) -> None:
        """Store a value in the cache.

        Args:
            key: The cache key.
            value: The value to store (as bytes).
            ttl: Time-to-live in seconds.
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove a value from the cache.

        Args:
            key: The cache key to remove.
        """
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if a key exists in the cache.

        Args:
            key: The cache key to check.

        Returns:
            True if the key exists and is not expired, False otherwise.
        """
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all entries from the cache."""
        pass


class InMemoryCache(CacheBackend):
    """In-memory cache implementation with TTL support.

    This is the default cache backend. It stores all data in a Python
    dictionary and automatically expires entries based on TTL.

    Note: This cache is not distributed and data is lost when the
    application restarts.
    """

    def __init__(self) -> None:
        """Initialize the in-memory cache."""
        self._data: dict[str, _CacheEntry] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> bytes | None:
        """Retrieve a value from the cache.

        Args:
            key: The cache key to look up.

        Returns:
            The cached value as bytes, or None if not found or expired.
        """
        async with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            if entry.is_expired():
                del self._data[key]
                return None
            return entry.value

    async def set(self, key: str, value: bytes, ttl: int) -> None:
        """Store a value in the cache.

        Args:
            key: The cache key.
            value: The value to store (as bytes).
            ttl: Time-to-live in seconds.
        """
        async with self._lock:
            expires_at = time.time() + ttl if ttl > 0 else None
            self._data[key] = _CacheEntry(value=value, expires_at=expires_at)

    async def delete(self, key: str) -> None:
        """Remove a value from the cache.

        Args:
            key: The cache key to remove.
        """
        async with self._lock:
            self._data.pop(key, None)

    async def exists(self, key: str) -> bool:
        """Check if a key exists in the cache.

        Args:
            key: The cache key to check.

        Returns:
            True if the key exists and is not expired, False otherwise.
        """
        async with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return False
            if entry.is_expired():
                del self._data[key]
                return False
            return True

    async def clear(self) -> None:
        """Clear all entries from the cache."""
        async with self._lock:
            self._data.clear()

    async def cleanup_expired(self) -> int:
        """Remove all expired entries from the cache.

        Returns:
            Number of entries removed.
        """
        async with self._lock:
            expired_keys = [
                key for key, entry in self._data.items() if entry.is_expired()
            ]
            for key in expired_keys:
                del self._data[key]
            return len(expired_keys)


class RedisCache(CacheBackend):
    """Redis-based cache implementation.

    This backend requires the 'redis' package to be installed.
    Falls back to InMemoryCache if Redis is not available.

    Example:
        >>> cache = RedisCache("redis://localhost:6379/0")
        >>> await cache.set("key", b"value", ttl=300)
    """

    def __init__(self, redis_url: str) -> None:
        """Initialize the Redis cache.

        Args:
            redis_url: Redis connection URL (e.g., "redis://localhost:6379/0")

        Raises:
            ImportError: If the 'redis' package is not installed.
        """
        try:
            import redis.asyncio as aioredis
        except ImportError as e:
            raise ImportError(
                "Redis cache requires 'redis' package. Install with: pip install redis"
            ) from e

        self._redis_url = redis_url
        self._redis: object | None = None
        self._client_class = aioredis.from_url

    async def _get_client(self) -> object:
        """Get or create the Redis client connection.

        Returns:
            Redis client instance.
        """
        if self._redis is None:
            self._redis = self._client_class(self._redis_url)
        return self._redis

    async def get(self, key: str) -> bytes | None:
        """Retrieve a value from the cache.

        Args:
            key: The cache key to look up.

        Returns:
            The cached value as bytes, or None if not found.
        """
        client = await self._get_client()
        value = await client.get(key)
        # Return None if value is None, otherwise return as-is (it's already bytes)
        return value if value is not None else None

    async def set(self, key: str, value: bytes, ttl: int) -> None:
        """Store a value in the cache.

        Args:
            key: The cache key.
            value: The value to store (as bytes).
            ttl: Time-to-live in seconds.
        """
        client = await self._get_client()
        await client.setex(key, ttl, value)

    async def delete(self, key: str) -> None:
        """Remove a value from the cache.

        Args:
            key: The cache key to remove.
        """
        client = await self._get_client()
        await client.delete(key)

    async def exists(self, key: str) -> bool:
        """Check if a key exists in the cache.

        Args:
            key: The cache key to check.

        Returns:
            True if the key exists, False otherwise.
        """
        client = await self._get_client()
        return await client.exists(key) > 0

    async def clear(self) -> None:
        """Clear all entries from the cache.

        WARNING: This uses FLUSHDB which clears the entire Redis database.
        Be careful when using a shared Redis instance.
        """
        client = await self._get_client()
        await client.flushdb()

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis is not None:
            # Use aclose() for proper async cleanup in redis-py 5.0+
            await self._redis.aclose()
            self._redis = None


# Global cache instance (singleton pattern)
_cache_instance: CacheBackend | None = None


def get_cache(
    backend: str | None = None,
    redis_url: str | None = None,
    force_new: bool = False,
) -> CacheBackend:
    """Get or create the global cache instance.

    This function returns an appropriate cache backend based on configuration.
    It uses a singleton pattern by default, returning the same instance on
    subsequent calls.

    Args:
        backend: Cache backend to use ('memory', 'redis', or None for auto).
            When None, checks settings.redis_enabled first.
        redis_url: Redis connection URL. If not provided, uses settings.redis_url.
        force_new: If True, create a new instance even if one exists.

    Returns:
        A CacheBackend instance (InMemoryCache or RedisCache).

    Example:
        >>> from gateway.app.core.cache import get_cache
        >>> cache = get_cache()
        >>> await cache.set("key", b"value", ttl=300)
    """
    global _cache_instance

    if _cache_instance is not None and not force_new:
        return _cache_instance

    # Import settings here to avoid circular imports
    from gateway.app.core.config import settings

    # Determine which backend to use
    use_redis = False
    if backend == "redis":
        use_redis = True
    elif backend == "memory":
        use_redis = False
    else:
        # Auto-detect based on settings
        use_redis = settings.redis_enabled

    if use_redis:
        url = redis_url or settings.redis_url
        try:
            _cache_instance = RedisCache(url)
            return _cache_instance
        except ImportError:
            # Redis not available, fall back to in-memory
            pass

    # Default to in-memory cache
    _cache_instance = InMemoryCache()
    return _cache_instance


def reset_cache() -> None:
    """Reset the global cache instance.

    This is primarily useful for testing.
    """
    global _cache_instance
    _cache_instance = None
