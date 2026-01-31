"""Rate limiting middleware for the gateway.

This module provides rate limiting functionality to prevent abuse
and ensure fair usage of the API. Supports both in-memory and Redis backends,
with sliding window and token bucket algorithms.
"""

import asyncio
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, Any

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from gateway.app.core.config import settings
from gateway.app.core.logging import get_logger

logger = get_logger(__name__)

# Try to import redis exceptions for error handling
try:
    import redis
    REDIS_EXCEPTIONS = (
        redis.ConnectionError,
        redis.TimeoutError,
        redis.RedisError,
    )
except ImportError:
    # Redis not installed, define dummy exceptions
    class _DummyRedisError(Exception):
        pass
    REDIS_EXCEPTIONS = (_DummyRedisError,)


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""
    allowed: bool
    limit: int
    remaining: int
    reset_time: int
    retry_after: Optional[int] = None


class RateLimitBackend(ABC):
    """Abstract base class for rate limit backends."""
    
    @abstractmethod
    async def is_allowed(self, key: str, tokens: int = 1) -> RateLimitResult:
        """Check if request is allowed for the given key.
        
        Args:
            key: Rate limit key
            tokens: Number of tokens to consume
            
        Returns:
            RateLimitResult with allowed status and metadata
        """
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up expired entries."""
        pass


@dataclass
class RateLimitEntry:
    """Entry for tracking rate limit state (sliding window)."""
    requests: int = 0
    window_start: float = field(default_factory=time.time)


@dataclass
class TokenBucket:
    """Token bucket state for token bucket algorithm."""
    tokens: float = field(default_factory=float)
    last_update: float = field(default_factory=time.time)


class InMemoryRateLimiter(RateLimitBackend):
    """In-memory rate limiter with configurable algorithm.
    
    Supports sliding window and token bucket algorithms.
    Suitable for single-instance deployments.
    
    Memory optimization:
    - Uses OrderedDict for LRU cache behavior
    - Limits max entries to prevent unbounded memory growth
    - Automatic cleanup of old entries when limit exceeded
    """
    
    DEFAULT_MAX_ENTRIES = 10000
    
    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_size: int = 10,
        window_seconds: int = 60,
        algorithm: str = "sliding_window",
        max_entries: int = DEFAULT_MAX_ENTRIES
    ):
        """Initialize rate limiter.
        
        Args:
            requests_per_minute: Maximum requests per minute
            burst_size: Maximum burst requests allowed
            window_seconds: Time window in seconds
            algorithm: Rate limiting algorithm (sliding_window or token_bucket)
            max_entries: Maximum number of entries to store (LRU eviction)
        """
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.window_seconds = window_seconds
        self.algorithm = algorithm
        self._max_entries = max_entries
        
        # Storage for sliding window (OrderedDict for LRU)
        self._window_storage: OrderedDict[str, RateLimitEntry] = OrderedDict()
        
        # Storage for token bucket (OrderedDict for LRU)
        self._bucket_storage: OrderedDict[str, TokenBucket] = OrderedDict()
        
        self._lock = asyncio.Lock()
    
    async def is_allowed(self, key: str, tokens: int = 1) -> RateLimitResult:
        """Check if request is allowed."""
        if self.algorithm == "token_bucket":
            return await self._check_token_bucket(key, tokens)
        else:
            return await self._check_sliding_window(key)
    
    def _enforce_lru_limit(self) -> None:
        """Enforce max entries limit using LRU eviction."""
        if len(self._window_storage) > self._max_entries:
            # Remove oldest 20% of entries
            remove_count = int(self._max_entries * 0.2)
            for _ in range(remove_count):
                self._window_storage.popitem(last=False)
        if len(self._bucket_storage) > self._max_entries:
            remove_count = int(self._max_entries * 0.2)
            for _ in range(remove_count):
                self._bucket_storage.popitem(last=False)
    
    async def _check_sliding_window(self, key: str) -> RateLimitResult:
        """Check using sliding window algorithm."""
        async with self._lock:
            now = time.time()
            
            # Enforce LRU limit before adding new entry
            self._enforce_lru_limit()
            
            # Move key to end (most recently used)
            if key in self._window_storage:
                self._window_storage.move_to_end(key)
            
            entry = self._window_storage.get(key)
            
            # Reset window if expired
            if entry is None or now - entry.window_start > self.window_seconds:
                entry = RateLimitEntry(requests=0, window_start=now)
                self._window_storage[key] = entry
            
            # Calculate limits
            max_requests = min(self.requests_per_minute, self.burst_size)
            remaining = max(0, max_requests - entry.requests - 1)
            reset_time = int(entry.window_start + self.window_seconds)
            
            # Check if allowed
            if entry.requests >= max_requests:
                return RateLimitResult(
                    allowed=False,
                    limit=max_requests,
                    remaining=0,
                    reset_time=reset_time,
                    retry_after=int(self.window_seconds - (now - entry.window_start))
                )
            
            # Increment counter
            entry.requests += 1
            
            return RateLimitResult(
                allowed=True,
                limit=max_requests,
                remaining=remaining,
                reset_time=reset_time
            )
    
    async def _check_token_bucket(self, key: str, tokens: int = 1) -> RateLimitResult:
        """Check using token bucket algorithm."""
        async with self._lock:
            now = time.time()
            
            # Enforce LRU limit before adding new entry
            self._enforce_lru_limit()
            
            # Move key to end (most recently used)
            if key in self._bucket_storage:
                self._bucket_storage.move_to_end(key)
            
            bucket = self._bucket_storage.get(key)
            
            if bucket is None:
                bucket = TokenBucket(tokens=float(self.burst_size), last_update=now)
                self._bucket_storage[key] = bucket
            
            # Calculate tokens to add based on time elapsed
            time_elapsed = now - bucket.last_update
            tokens_to_add = time_elapsed * (self.requests_per_minute / self.window_seconds)
            bucket.tokens = min(self.burst_size, bucket.tokens + tokens_to_add)
            bucket.last_update = now
            
            # Check if enough tokens
            if bucket.tokens >= tokens:
                bucket.tokens -= tokens
                return RateLimitResult(
                    allowed=True,
                    limit=self.burst_size,
                    remaining=int(bucket.tokens),
                    reset_time=int(now + ((tokens - bucket.tokens) / (self.requests_per_minute / self.window_seconds)))
                )
            else:
                # Calculate retry after
                tokens_needed = tokens - bucket.tokens
                retry_after = int(tokens_needed / (self.requests_per_minute / self.window_seconds))
                return RateLimitResult(
                    allowed=False,
                    limit=self.burst_size,
                    remaining=0,
                    reset_time=int(now + retry_after),
                    retry_after=retry_after
                )
    
    async def cleanup(self) -> None:
        """Clean up expired entries."""
        async with self._lock:
            now = time.time()
            
            # Clean sliding window entries
            expired_windows = [
                key for key, entry in self._window_storage.items()
                if now - entry.window_start > self.window_seconds
            ]
            for key in expired_windows:
                del self._window_storage[key]
            
            # Clean token bucket entries (inactive for more than 2x window)
            expired_buckets = [
                key for key, bucket in self._bucket_storage.items()
                if now - bucket.last_update > self.window_seconds * 2
            ]
            for key in expired_buckets:
                del self._bucket_storage[key]


class RedisRateLimiter(RateLimitBackend):
    """Redis-based distributed rate limiter.
    
    Uses Redis for distributed rate limiting across multiple instances.
    Implements sliding window algorithm using Redis sorted sets.
    """
    
    def __init__(
        self,
        redis_client: Optional[Any] = None,
        redis_url: Optional[str] = None,
        requests_per_minute: int = 60,
        burst_size: int = 10,
        window_seconds: int = 60
    ):
        """Initialize Redis rate limiter.
        
        Args:
            redis_client: Optional Redis client instance
            redis_url: Redis connection URL
            requests_per_minute: Maximum requests per minute
            burst_size: Maximum burst requests allowed
            window_seconds: Time window in seconds
        """
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.window_seconds = window_seconds
        self._redis_url = redis_url or settings.redis_url
        self._redis = redis_client
    
    async def _get_redis(self) -> Any:
        """Get or create Redis connection."""
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(self._redis_url)
            except ImportError:
                raise RuntimeError("Redis package not installed. Install with: pip install redis")
        return self._redis
    
    async def is_allowed(self, key: str, tokens: int = 1) -> RateLimitResult:
        """Check if request is allowed using Redis sliding window.
        
        Uses Redis sorted set to track request timestamps.
        """
        try:
            redis_client = await self._get_redis()
            now = time.time()
            window_start = now - self.window_seconds
            
            # Use pipeline for atomic operations
            pipe = redis_client.pipeline()
            
            # Remove old entries outside the window
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current entries in window
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {str(now): now})
            
            # Set expiry on the key
            pipe.expire(key, self.window_seconds)
            
            results = await pipe.execute()
            current_count = results[1]  # Result of zcard
            
            max_requests = min(self.requests_per_minute, self.burst_size)
            
            # Check if allowed (subtract 1 because we just added)
            if current_count > max_requests:
                # Remove the request we just added
                await redis_client.zrem(key, str(now))
                return RateLimitResult(
                    allowed=False,
                    limit=max_requests,
                    remaining=0,
                    reset_time=int(now + self.window_seconds),
                    retry_after=self.window_seconds
                )
            
            remaining = max(0, max_requests - current_count)
            return RateLimitResult(
                allowed=True,
                limit=max_requests,
                remaining=remaining,
                reset_time=int(now + self.window_seconds)
            )
            
        except redis.ConnectionError as e:
            # Redis 连接失败 - 可能是服务不可用或网络问题
            logger.error(f"Redis connection failed: {e}")
            return self._handle_redis_failure("connection_error")
        except redis.TimeoutError as e:
            # Redis 超时 - 服务可能过载
            logger.warning(f"Redis timeout: {e}")
            return self._handle_redis_failure("timeout")
        except redis.RedisError as e:
            # 其他 Redis 错误
            logger.error(f"Redis error: {e}")
            return self._handle_redis_failure("redis_error")
        except Exception as e:
            # 意外错误 - 记录详细日志并采取保守策略
            logger.exception(f"Unexpected rate limit error: {e}")
            return self._handle_redis_failure("unexpected")

    def _handle_redis_failure(self, error_type: str) -> RateLimitResult:
        """Handle Redis failure with configurable fail-open/fail-closed policy.

        Args:
            error_type: Type of error for logging purposes

        Returns:
            RateLimitResult based on fail_closed configuration
        """
        fail_closed = getattr(settings, 'rate_limit_fail_closed', False)

        if fail_closed:
            # 安全敏感环境：Redis 失败时拒绝请求
            logger.warning(
                f"Rate limiting fail-closed triggered due to {error_type}. "
                "Request denied."
            )
            return RateLimitResult(
                allowed=False,
                limit=self.burst_size,
                remaining=0,
                reset_time=int(time.time() + self.window_seconds),
                retry_after=self.window_seconds
            )

        # 默认：fail-open，允许请求通过但记录警告
        logger.warning(
            f"Rate limiting fail-open triggered due to {error_type}. "
            "Request allowed without rate limit check."
        )
        return RateLimitResult(
            allowed=True,
            limit=self.burst_size,
            remaining=1,
            reset_time=int(time.time() + self.window_seconds)
        )
    
    async def cleanup(self) -> None:
        """No-op for Redis (keys expire automatically)."""
        pass


class RateLimiter:
    """Main rate limiter that selects appropriate backend.
    
    Automatically selects Redis backend if Redis is enabled in settings,
    otherwise uses in-memory backend.
    """
    
    def __init__(
        self,
        requests_per_minute: int = 60,
        burst_size: int = 10,
        window_seconds: int = 60,
        algorithm: str = "sliding_window",
        use_redis: Optional[bool] = None
    ):
        """Initialize rate limiter with appropriate backend.
        
        Args:
            requests_per_minute: Maximum requests per minute
            burst_size: Maximum burst requests allowed
            window_seconds: Time window in seconds
            algorithm: Rate limiting algorithm (sliding_window or token_bucket)
            use_redis: Force Redis usage (None = auto-detect from settings)
        """
        # Determine if we should use Redis
        should_use_redis = use_redis if use_redis is not None else settings.redis_enabled
        
        if should_use_redis:
            try:
                self._backend: RateLimitBackend = RedisRateLimiter(
                    requests_per_minute=requests_per_minute,
                    burst_size=burst_size,
                    window_seconds=window_seconds
                )
                logger.info("Using Redis rate limiter backend")
            except Exception as e:
                logger.warning(f"Failed to initialize Redis rate limiter: {e}. Using in-memory.")
                self._backend = InMemoryRateLimiter(
                    requests_per_minute=requests_per_minute,
                    burst_size=burst_size,
                    window_seconds=window_seconds,
                    algorithm=algorithm
                )
        else:
            self._backend = InMemoryRateLimiter(
                requests_per_minute=requests_per_minute,
                burst_size=burst_size,
                window_seconds=window_seconds,
                algorithm=algorithm
            )
            logger.debug("Using in-memory rate limiter backend")
    
    async def is_allowed(self, key: str, tokens: int = 1) -> RateLimitResult:
        """Check if request is allowed."""
        return await self._backend.is_allowed(key, tokens)
    
    async def cleanup(self) -> None:
        """Clean up expired entries."""
        await self._backend.cleanup()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce rate limits on requests.
    
    Rate limits are applied per API key if available, otherwise per IP.
    Supports both sliding window and token bucket algorithms.
    """
    
    def __init__(
        self,
        app,
        requests_per_minute: int = 60,
        burst_size: int = 10,
        window_seconds: int = 60,
        algorithm: str = "sliding_window",
        use_redis: Optional[bool] = None
    ):
        super().__init__(app)
        self.limiter = RateLimiter(
            requests_per_minute=requests_per_minute,
            burst_size=burst_size,
            window_seconds=window_seconds,
            algorithm=algorithm,
            use_redis=use_redis
        )
    
    def _get_client_key(self, request: Request) -> str:
        """Get rate limit key for the request.
        
        Uses API key if available, otherwise falls back to IP address.
        API keys are hashed using SHA-256 to prevent storing or exposing raw keys.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Rate limit key string (hashed, no sensitive data exposed)
        """
        import hashlib
        
        # Try to get API key from Authorization header
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            api_key = auth[7:].strip()
            # Validate API key length to prevent DoS via extremely long keys
            if len(api_key) > 512:
                from fastapi import HTTPException
                raise HTTPException(status_code=400, detail="API key too long (max 512 characters)")
            # Use hash of API key to avoid storing raw keys in memory or cache
            # Use 32 hex chars (128 bits) for collision resistance
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:32]
            return f"ratelimit:apikey:{key_hash}"
        
        # Fall back to IP address (also hash IP for privacy)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(',')[0].strip()
        else:
            client_ip = request.client.host if request.client else 'unknown'
        
        # Hash IP address for privacy compliance (GDPR, etc.)
        # Use 32 hex chars (128 bits) for collision resistance
        ip_hash = hashlib.sha256(client_ip.encode()).hexdigest()[:32]
        return f"ratelimit:ip:{ip_hash}"
    
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request with rate limiting."""
        key = self._get_client_key(request)
        result = await self.limiter.is_allowed(key)
        
        if not result.allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "rate_limit_exceeded",
                    "message": "Rate limit exceeded. Please try again later.",
                    "retry_after": result.retry_after
                },
                headers={
                    "X-RateLimit-Limit": str(result.limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(result.reset_time),
                    "Retry-After": str(result.retry_after or 60)
                }
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(result.limit)
        response.headers["X-RateLimit-Remaining"] = str(result.remaining)
        response.headers["X-RateLimit-Reset"] = str(result.reset_time)
        
        return response