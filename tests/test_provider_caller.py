"""Tests for provider caller."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gateway.app.services.provider_caller import ProviderCaller
from gateway.app.services.smart_router import KeyType, RoutingDecision


class TestProviderCaller:
    """Test provider calling functionality."""
    
    @pytest.fixture
    def caller(self):
        """Create provider caller instance."""
        return ProviderCaller()
    
    @pytest.fixture
    def mock_openai_response(self):
        """Create mock OpenAI response."""
        response = MagicMock()
        response.id = "test-response-id"
        response.created = 1234567890
        response.model = "deepseek-chat"
        response.choices = [MagicMock()]
        response.choices[0].message.content = "Test response"
        response.choices[0].finish_reason = "stop"
        response.usage = MagicMock()
        response.usage.prompt_tokens = 10
        response.usage.completion_tokens = 20
        response.usage.total_tokens = 30
        return response
    
    @pytest.fixture
    def teacher_deepseek_decision(self):
        """Create teacher DeepSeek routing decision."""
        return RoutingDecision(
            key_type=KeyType.TEACHER_DEEPSEEK,
            provider_name="deepseek",
            api_key="sk-teacher-key",
            base_url="https://api.deepseek.com/v1",
            model="deepseek-chat",
            timeout=15.0,
            cost_per_1m_tokens=(0.55, 2.19),
        )
    
    def test_estimate_cost(self, caller):
        """Test cost estimation."""
        cost = caller._estimate_cost(1_000_000, (0.55, 2.19))
        assert cost == pytest.approx(1.37, 0.01)  # Average of 0.55 and 2.19
        
        cost = caller._estimate_cost(500_000, (0.55, 2.19))
        assert cost == pytest.approx(0.685, 0.01)
    
    @pytest.mark.asyncio
    async def test_call_non_stream(self, caller, teacher_deepseek_decision, mock_openai_response):
        """Test non-streaming call."""
        with patch('gateway.app.services.provider_caller.AsyncOpenAI') as mock_client_class:
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
            mock_client_class.return_value = mock_client
            
            result = await caller.call(
                decision=teacher_deepseek_decision,
                messages=[{"role": "user", "content": "Hello"}],
                temperature=0.7,
                max_tokens=2048,
                stream=False,
            )
        
        assert result["id"] == "test-response-id"
        assert result["_meta"]["provider"] == "deepseek"
        assert result["_meta"]["key_type"] == "teacher_deepseek"
        assert "cost_estimate" in result["_meta"]
    
    @pytest.mark.asyncio
    async def test_call_with_openrouter_fallback(self, caller):
        """Test that OpenRouter gets fallback models."""
        decision = RoutingDecision(
            key_type=KeyType.TEACHER_OPENROUTER,
            provider_name="openrouter",
            api_key="sk-or-key",
            base_url="https://openrouter.ai/api/v1",
            model="deepseek/deepseek-chat",
            timeout=30.0,
            fallback_models=["openai/gpt-4o-mini"],
            cost_per_1m_tokens=(0.58, 2.31),
        )
        
        mock_response = MagicMock()
        mock_response.id = "test-id"
        mock_response.created = 1234567890
        mock_response.model = "deepseek/deepseek-chat"
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_response.choices[0].finish_reason = "stop"
        mock_response.usage = MagicMock()
        mock_response.usage.total_tokens = 100
        
        with patch('gateway.app.services.provider_caller.AsyncOpenAI') as mock_client_class:
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client
            
            await caller.call(
                decision=decision,
                messages=[{"role": "user", "content": "Hello"}],
                temperature=0.7,
                max_tokens=2048,
                stream=False,
            )
        
        # Verify extra_body contains fallback models
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        assert call_kwargs["extra_body"] == {"models": ["openai/gpt-4o-mini"]}
