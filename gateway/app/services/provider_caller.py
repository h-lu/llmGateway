"""LLM Provider caller with failover support."""

import logging
from typing import AsyncGenerator

import httpx
from openai import AsyncOpenAI, APITimeoutError

from gateway.app.core.config import settings
from gateway.app.services.smart_router import KeyType, RoutingDecision

logger = logging.getLogger(__name__)


class ProviderCaller:
    """LLM 提供商调用器，支持故障转移。
    
    故障转移策略：
    1. 教师 DeepSeek 超时 → 切换到教师 OpenRouter
    2. OpenRouter 自动处理内部 fallback
    """
    
    async def call(
        self,
        decision: RoutingDecision,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        stream: bool = False,
    ) -> dict | AsyncGenerator:
        """调用 LLM API。
        
        Args:
            decision: 路由决策结果
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            stream: 是否流式输出
            
        Returns:
            非流式：dict 响应
            流式：AsyncGenerator
        """
        try:
            return await self._call_with_decision(
                decision, messages, temperature, max_tokens, stream
            )
        except (APITimeoutError, httpx.TimeoutException) as e:
            # DeepSeek 直接超时，尝试 OpenRouter
            if decision.key_type == KeyType.TEACHER_DEEPSEEK:
                logger.warning(f"DeepSeek timeout, falling back to OpenRouter: {e}")
                
                fallback_decision = RoutingDecision(
                    key_type=KeyType.TEACHER_OPENROUTER,
                    provider_name="openrouter",
                    api_key=settings.teacher_openrouter_api_key,
                    base_url=settings.teacher_openrouter_base_url,
                    model=f"deepseek/{decision.model}",
                    timeout=settings.openrouter_timeout,
                    fallback_models=settings.openrouter_fallback_models,
                    cost_per_1m_tokens=(0.58, 2.31),
                )
                
                return await self._call_with_decision(
                    fallback_decision, messages, temperature, max_tokens, stream
                )
            
            raise  # 其他情况直接抛出
    
    async def _call_with_decision(
        self,
        decision: RoutingDecision,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        stream: bool,
    ) -> dict | AsyncGenerator:
        """实际调用 API"""
        
        client = AsyncOpenAI(
            api_key=decision.api_key,
            base_url=decision.base_url,
            timeout=decision.timeout,
        )
        
        # 构建 extra_body（OpenRouter fallback）
        extra_body = {}
        if decision.fallback_models and decision.provider_name == "openrouter":
            extra_body["models"] = decision.fallback_models
            logger.debug(f"Using fallback models: {decision.fallback_models}")
        
        if stream:
            return self._stream_response(
                client, decision, messages, temperature, max_tokens, extra_body
            )
        else:
            return await self._call_non_stream(
                client, decision, messages, temperature, max_tokens, extra_body
            )
    
    async def _call_non_stream(
        self,
        client: AsyncOpenAI,
        decision: RoutingDecision,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        extra_body: dict,
    ) -> dict:
        """非流式调用"""
        
        logger.debug(f"Calling {decision.provider_name} with model {decision.model}")
        
        response = await client.chat.completions.create(
            model=decision.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
            extra_body=extra_body if extra_body else None,
        )
        
        # 估算成本
        total_tokens = response.usage.total_tokens if response.usage else 0
        cost_estimate = self._estimate_cost(total_tokens, decision.cost_per_1m_tokens)
        
        logger.info(
            f"Request completed: provider={decision.provider_name}, "
            f"key_type={decision.key_type.value}, "
            f"tokens={total_tokens}, cost=${cost_estimate:.6f}"
        )
        
        return {
            "id": response.id,
            "object": "chat.completion",
            "created": response.created,
            "model": response.model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response.choices[0].message.content,
                },
                "finish_reason": response.choices[0].finish_reason,
            }],
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": total_tokens,
            },
            "_meta": {
                "provider": decision.provider_name,
                "key_type": decision.key_type.value,
                "cost_estimate": cost_estimate,
                "model_used": response.model,
            }
        }
    
    async def _stream_response(
        self,
        client: AsyncOpenAI,
        decision: RoutingDecision,
        messages: list[dict],
        temperature: float,
        max_tokens: int,
        extra_body: dict,
    ) -> AsyncGenerator:
        """流式响应（生成器）"""
        
        response = await client.chat.completions.create(
            model=decision.model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            extra_body=extra_body if extra_body else None,
        )
        
        # 添加元信息到第一个 chunk
        first_chunk = True
        async for chunk in response:
            if first_chunk:
                first_chunk = False
                # 在第一个 chunk 中注入元信息
                chunk_dict = chunk.model_dump()
                chunk_dict["_meta"] = {
                    "provider": decision.provider_name,
                    "key_type": decision.key_type.value,
                }
                yield chunk_dict
            else:
                yield chunk.model_dump()
    
    def _estimate_cost(self, total_tokens: int, cost_per_1m: tuple) -> float:
        """估算成本（美元）
        
        Args:
            total_tokens: 总 token 数
            cost_per_1m: (input_cost, output_cost) per 1M tokens
            
        Returns:
            估算成本（美元）
        """
        avg_cost = (cost_per_1m[0] + cost_per_1m[1]) / 2
        return (total_tokens / 1_000_000) * avg_cost


# Global instance
_provider_caller: ProviderCaller | None = None


def get_provider_caller() -> ProviderCaller:
    """Get or create provider caller instance."""
    global _provider_caller
    if _provider_caller is None:
        _provider_caller = ProviderCaller()
    return _provider_caller
