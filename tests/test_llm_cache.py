"""Tests for LLM cache service."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from gateway.app.services.content_classifier import CachePolicy
from gateway.app.services.llm_cache import LLMCacheService

pytestmark = pytest.mark.asyncio


class TestLLMCacheService:
    """Test LLM cache functionality."""
    
    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = MagicMock()
        redis.get = AsyncMock()
        redis.setex = AsyncMock()
        redis.keys = AsyncMock(return_value=[])
        redis.delete = AsyncMock()
        return redis
    
    @pytest.fixture
    def cache_service(self, mock_redis):
        """Create cache service with mock Redis."""
        service = LLMCacheService(mock_redis)
        service.enabled = True
        return service
    
    async def test_get_cache_hit(self, cache_service, mock_redis):
        """Test cache hit."""
        cached_data = {
            "id": "test-123",
            "choices": [{"message": {"content": "Hello"}}],
            "_cached_at": "2024-01-01T00:00:00",
        }
        mock_redis.get.return_value = json.dumps(cached_data)
        
        messages = [{"role": "user", "content": "What is Python?"}]
        result = await cache_service.get(messages, "deepseek-chat")
        
        assert result is not None
        assert result["_cache_hit"] is True
        assert result["id"] == "test-123"
    
    async def test_get_cache_miss(self, cache_service, mock_redis):
        """Test cache miss."""
        mock_redis.get.return_value = None
        
        messages = [{"role": "user", "content": "What is Python?"}]
        result = await cache_service.get(messages, "deepseek-chat")
        
        assert result is None
    
    async def test_no_cache_for_code(self, cache_service, mock_redis):
        """Code content should not be cached."""
        messages = [{"role": "user", "content": "```python\ndef hello():\n    pass\n```"}]
        result = await cache_service.get(messages, "deepseek-chat")
        
        assert result is None
        mock_redis.get.assert_not_called()
    
    async def test_set_cache(self, cache_service, mock_redis):
        """Test setting cache."""
        messages = [{"role": "user", "content": "What is Python?"}]
        response = {"id": "test-123", "choices": []}
        
        await cache_service.set(messages, response, "deepseek-chat")
        
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][1] > 0  # TTL should be positive
    
    async def test_no_set_for_code(self, cache_service, mock_redis):
        """Code content should not be stored."""
        messages = [{"role": "user", "content": "def hello(): pass"}]
        response = {"id": "test-123", "choices": []}
        
        await cache_service.set(messages, response, "deepseek-chat")
        
        mock_redis.setex.assert_not_called()
    
    async def test_determine_ttl_concept(self, cache_service):
        """Concept questions should have longer TTL."""
        concept_ttl = cache_service._determine_ttl("什么是递归？")
        general_ttl = cache_service._determine_ttl("今天天气怎么样？")
        
        assert concept_ttl > general_ttl
