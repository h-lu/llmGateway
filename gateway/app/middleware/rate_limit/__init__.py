"""Rate limiting middleware for the gateway.

This module provides rate limiting functionality to prevent abuse
and ensure fair usage of the API. Supports both in-memory and Redis backends,
with sliding window and token bucket algorithms.
"""

from typing import Optional

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from gateway.app.core.config import settings
from gateway.app.core.logging import get_logger

# Re-export models
from gateway.app.middleware.rate_limit.models import (
    RateLimitEntry,
    RateLimitResult,
    TokenBucket,
)

# Re-export backends
from gateway.app.middleware.rate_limit.backends import (
    InMemoryRateLimiter,
    RateLimitBackend,
    RedisRateLimiter,
)

logger = get_logger(__name__)

__all__ = [
    # Models
    "RateLimitResult",
    "RateLimitEntry",
    "TokenBucket",
    # Backends
    "RateLimitBackend",
    "InMemoryRateLimiter",
    "RedisRateLimiter",
    # Main classes
    "RateLimiter",
    "RateLimitMiddleware",
]


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
