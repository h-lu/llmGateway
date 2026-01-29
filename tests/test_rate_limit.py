"""Tests for rate limiting middleware."""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch

from gateway.app.middleware.rate_limit import (
    InMemoryRateLimiter,
    RedisRateLimiter,
    RateLimiter,
    RateLimitMiddleware,
    RateLimitResult,
    TokenBucket,
)


class TestInMemoryRateLimiter:
    """Tests for in-memory rate limiter."""
    
    @pytest.fixture
    def limiter(self):
        return InMemoryRateLimiter(
            requests_per_minute=60,
            burst_size=10,
            window_seconds=60
        )
    
    @pytest.mark.asyncio
    async def test_sliding_window_allows_requests_under_limit(self, limiter):
        """Test that requests under limit are allowed."""
        result = await limiter.is_allowed("test_key")
        assert result.allowed is True
        assert result.remaining == 9  # burst_size - 1
        assert result.limit == 10
    
    @pytest.mark.asyncio
    async def test_sliding_window_blocks_over_limit(self, limiter):
        """Test that requests over limit are blocked."""
        # Make 10 requests (at burst limit)
        for i in range(10):
            result = await limiter.is_allowed("test_key")
        
        # 11th request should be blocked
        result = await limiter.is_allowed("test_key")
        assert result.allowed is False
        assert result.remaining == 0
    
    @pytest.mark.asyncio
    async def test_token_bucket_algorithm(self):
        """Test token bucket algorithm."""
        limiter = InMemoryRateLimiter(
            requests_per_minute=60,
            burst_size=10,
            algorithm="token_bucket"
        )
        
        # First request should be allowed
        result = await limiter.is_allowed("test_key")
        assert result.allowed is True
        assert result.remaining == 9
    
    @pytest.mark.asyncio
    async def test_different_keys_independent(self, limiter):
        """Test that different keys have independent limits."""
        # Use up limit for key1
        for i in range(10):
            await limiter.is_allowed("key1")
        
        result = await limiter.is_allowed("key1")
        assert result.allowed is False
        
        # key2 should still be allowed
        result = await limiter.is_allowed("key2")
        assert result.allowed is True


class TestTokenBucket:
    """Tests for token bucket algorithm."""
    
    @pytest.mark.asyncio
    async def test_token_bucket_refills_over_time(self):
        """Test that tokens refill over time."""
        limiter = InMemoryRateLimiter(
            requests_per_minute=60,  # 1 token per second
            burst_size=5,
            algorithm="token_bucket"
        )
        
        # Use all tokens
        for i in range(5):
            result = await limiter.is_allowed("test_key")
            assert result.allowed is True
        
        # Next request should be blocked
        result = await limiter.is_allowed("test_key")
        assert result.allowed is False
    
    @pytest.mark.asyncio
    async def test_token_bucket_partial_refill(self):
        """Test partial token refill."""
        limiter = InMemoryRateLimiter(
            requests_per_minute=600,  # 10 tokens per second
            burst_size=5,
            algorithm="token_bucket"
        )
        
        # Use all tokens
        for i in range(5):
            await limiter.is_allowed("test_key")
        
        # Should be blocked immediately
        result = await limiter.is_allowed("test_key")
        assert result.allowed is False


class TestRateLimiterBackendSelection:
    """Tests for backend selection logic."""
    
    @pytest.mark.asyncio
    async def test_uses_in_memory_by_default(self):
        """Test that in-memory backend is used by default."""
        with patch("gateway.app.middleware.rate_limit.settings") as mock_settings:
            mock_settings.redis_enabled = False
            limiter = RateLimiter()
            assert isinstance(limiter._backend, InMemoryRateLimiter)
    
    @pytest.mark.asyncio
    async def test_uses_redis_when_enabled(self):
        """Test that Redis backend is used when enabled."""
        with patch("gateway.app.middleware.rate_limit.settings") as mock_settings:
            mock_settings.redis_enabled = True
            mock_settings.redis_url = "redis://localhost:6379/0"
            
            with patch("gateway.app.middleware.rate_limit.RedisRateLimiter") as mock_redis:
                mock_redis.return_value = Mock()
                limiter = RateLimiter()
                mock_redis.assert_called_once()


class TestRateLimitResult:
    """Tests for RateLimitResult dataclass."""
    
    def test_result_creation(self):
        """Test creating a rate limit result."""
        result = RateLimitResult(
            allowed=True,
            limit=100,
            remaining=99,
            reset_time=1234567890,
            retry_after=None
        )
        assert result.allowed is True
        assert result.limit == 100
        assert result.remaining == 99


class TestRedisRateLimiter:
    """Tests for Redis rate limiter."""
    
    @pytest.mark.asyncio
    async def test_redis_limiter_allows_when_available(self):
        """Test that Redis limiter allows requests when available."""
        mock_redis = AsyncMock()
        mock_redis.pipeline.return_value = mock_redis
        mock_redis.execute.return_value = [0, 1, 1, 1]  # zrem, zcard, zadd, expire
        
        limiter = RedisRateLimiter(redis_client=mock_redis)
        result = await limiter.is_allowed("test_key")
        
        assert result.allowed is True
    
    @pytest.mark.asyncio
    async def test_redis_limiter_fail_open_on_error(self):
        """Test that Redis limiter fails open on errors."""
        mock_redis = AsyncMock()
        mock_redis.pipeline.side_effect = Exception("Redis error")
        
        limiter = RedisRateLimiter(redis_client=mock_redis)
        result = await limiter.is_allowed("test_key")
        
        # Should fail open (allow request)
        assert result.allowed is True


class TestRateLimitMiddleware:
    """Tests for rate limit middleware."""
    
    @pytest.fixture
    def app(self):
        """Create a mock FastAPI app."""
        return Mock()
    
    @pytest.fixture
    def middleware(self, app):
        """Create rate limit middleware."""
        return RateLimitMiddleware(
            app,
            requests_per_minute=60,
            burst_size=10
        )
    
    def test_get_client_key_from_api_key(self, middleware):
        """Test extracting client key from API key."""
        request = Mock()
        request.headers = {"Authorization": "Bearer test_api_key_123"}
        request.client.host = "127.0.0.1"
        
        key = middleware._get_client_key(request)
        assert key.startswith("ratelimit:apikey:")
        assert "test_api_key_123" not in key  # Should be hashed
    
    def test_get_client_key_from_ip(self, middleware):
        """Test extracting client key from IP address - IP is hashed for privacy."""
        import hashlib
        request = Mock()
        request.headers = {}
        request.client.host = "192.168.1.1"
        
        key = middleware._get_client_key(request)
        # IP should be hashed, not plaintext
        expected_hash = hashlib.sha256("192.168.1.1".encode()).hexdigest()[:16]
        assert key == f"ratelimit:ip:{expected_hash}"
        assert "192.168.1.1" not in key  # Raw IP should not appear
    
    def test_get_client_key_from_x_forwarded_for(self, middleware):
        """Test extracting client key from X-Forwarded-For header - IP is hashed for privacy."""
        import hashlib
        request = Mock()
        request.headers = {"X-Forwarded-For": "10.0.0.1, 192.168.1.1"}
        request.client.host = "127.0.0.1"
        
        key = middleware._get_client_key(request)
        # First IP from X-Forwarded-For should be hashed
        expected_hash = hashlib.sha256("10.0.0.1".encode()).hexdigest()[:16]
        assert key == f"ratelimit:ip:{expected_hash}"
        assert "10.0.0.1" not in key  # Raw IP should not appear
