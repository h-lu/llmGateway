"""LLM response caching service."""

import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Optional

import redis.asyncio as redis

from gateway.app.core.config import settings
from gateway.app.services.content_classifier import CachePolicy, ContentClassifier

logger = logging.getLogger(__name__)


class LLMCacheService:
    """LLM 响应缓存服务。

    设计原则：
    - 全局共享缓存（不含 student_id）
    - 内容过滤决定是否可以缓存
    - 概念性问题缓存更久
    """

    def __init__(self, redis_client: Optional[redis.Redis] = None):
        self.redis = redis_client
        self.enabled = settings.llm_cache_enabled and settings.redis_enabled
        self.prefix = settings.llm_cache_prefix

    def _generate_key(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        """生成缓存键（全局共享，不包含 student_id）"""
        # 标准化 messages
        normalized = json.dumps(messages, sort_keys=True, ensure_ascii=False)

        # 生成 hash
        key_content = f"{model}:{normalized}:{temperature}:{max_tokens}"
        key_hash = hashlib.sha256(key_content.encode()).hexdigest()

        return f"{self.prefix}:cache:{key_hash}"

    async def get(
        self,
        messages: list[dict[str, Any]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Optional[dict[str, Any]]:
        """获取缓存响应。"""
        if not self.enabled or not self.redis:
            return None

        # 检查内容是否可缓存
        prompt_text = self._extract_prompt_text(messages)
        policy = ContentClassifier.classify(prompt_text)

        if policy == CachePolicy.NO_CACHE:
            return None

        cache_key = self._generate_key(messages, model, temperature, max_tokens)

        try:
            cached = await self.redis.get(cache_key)
            if cached:
                data = json.loads(cached)
                data["_cache_hit"] = True
                data["_cached_at"] = data.get("_cached_at")
                logger.debug(f"Cache hit for key: {cache_key[:16]}...")
                return data
        except Exception as e:
            logger.warning(f"Cache get failed: {e}")

        return None

    async def set(
        self,
        messages: list[dict[str, Any]],
        response: dict[str, Any],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> None:
        """设置缓存。"""
        if not self.enabled or not self.redis:
            return

        # 检查内容是否可缓存
        prompt_text = self._extract_prompt_text(messages)
        policy = ContentClassifier.classify(prompt_text)

        if policy == CachePolicy.NO_CACHE:
            return

        # 检查响应大小
        response_size = len(json.dumps(response))
        if response_size > settings.llm_cache_max_size:
            logger.debug(f"Response too large to cache: {response_size} bytes")
            return

        cache_key = self._generate_key(messages, model, temperature, max_tokens)

        # 确定 TTL
        ttl = self._determine_ttl(prompt_text)

        try:
            response_to_cache = {
                **response,
                "_cached_at": datetime.now().isoformat(),
                "_cache_policy": policy.value,
            }

            await self.redis.setex(
                cache_key, ttl, json.dumps(response_to_cache, ensure_ascii=False)
            )
            logger.debug(f"Cached response with TTL {ttl}s: {cache_key[:16]}...")
        except Exception as e:
            logger.warning(f"Cache set failed: {e}")

    def _determine_ttl(self, prompt: str) -> int:
        """根据内容类型确定 TTL"""
        # 概念性问题缓存更久
        if ContentClassifier.is_concept_question(prompt):
            return settings.llm_cache_ttl_concept

        return settings.llm_cache_ttl_general

    def _extract_prompt_text(self, messages: list[dict[str, Any]]) -> str:
        """从 messages 中提取用户提示文本"""
        # 取最后一条用户消息
        for msg in reversed(messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return ""

    async def invalidate(self, pattern: str = "*") -> int:
        """按模式清除缓存（主要用于管理操作）"""
        if not self.enabled or not self.redis:
            return 0

        try:
            keys = await self.redis.keys(f"{self.prefix}:cache:{pattern}")
            if keys:
                await self.redis.delete(*keys)
            return len(keys)
        except Exception as e:
            logger.warning(f"Cache invalidation failed: {e}")
            return 0


# Global instance (initialized with Redis client on startup)
_llm_cache_service: Optional[LLMCacheService] = None


def get_llm_cache_service(
    redis_client: Optional[redis.Redis] = None,
) -> LLMCacheService:
    """Get or create LLM cache service instance."""
    global _llm_cache_service
    if _llm_cache_service is None:
        _llm_cache_service = LLMCacheService(redis_client)
    return _llm_cache_service
