"""Tests for retry mechanism with exponential backoff."""

import asyncio
from dataclasses import dataclass
from typing import Type, Tuple
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from gateway.app.providers.retry import RetryPolicy, with_retry


class TestRetryPolicy:
    """Test RetryPolicy configuration."""
    
    def test_default_values(self):
        """Test default retry policy values."""
        policy = RetryPolicy()
        
        assert policy.max_retries == 3
        assert policy.base_delay == 0.5
        assert policy.max_delay == 10.0
        assert policy.exponential_base == 2.0
        assert policy.retryable_exceptions == (
            httpx.HTTPStatusError,
            httpx.NetworkError,
            httpx.TimeoutException,
            httpx.ConnectError,
        )
    
    def test_custom_values(self):
        """Test custom retry policy values."""
        custom_exceptions = (ValueError, TypeError)
        policy = RetryPolicy(
            max_retries=5,
            base_delay=1.0,
            max_delay=30.0,
            exponential_base=3.0,
            retryable_exceptions=custom_exceptions
        )
        
        assert policy.max_retries == 5
        assert policy.base_delay == 1.0
        assert policy.max_delay == 30.0
        assert policy.exponential_base == 3.0
        assert policy.retryable_exceptions == custom_exceptions
    
    def test_calculate_delay(self):
        """Test exponential delay calculation."""
        policy = RetryPolicy(base_delay=0.5, max_delay=10.0, exponential_base=2.0)
        
        # Attempt 0: 0.5 * 2^0 = 0.5
        assert policy.calculate_delay(0) == 0.5
        
        # Attempt 1: 0.5 * 2^1 = 1.0
        assert policy.calculate_delay(1) == 1.0
        
        # Attempt 2: 0.5 * 2^2 = 2.0
        assert policy.calculate_delay(2) == 2.0
        
        # Attempt 3: 0.5 * 2^3 = 4.0
        assert policy.calculate_delay(3) == 4.0
    
    def test_calculate_delay_capped_at_max(self):
        """Test delay is capped at max_delay."""
        policy = RetryPolicy(base_delay=1.0, max_delay=5.0, exponential_base=2.0)
        
        # Attempt 0: 1.0 * 2^0 = 1.0
        assert policy.calculate_delay(0) == 1.0
        
        # Attempt 1: 1.0 * 2^1 = 2.0
        assert policy.calculate_delay(1) == 2.0
        
        # Attempt 2: 1.0 * 2^2 = 4.0
        assert policy.calculate_delay(2) == 4.0
        
        # Attempt 3: 1.0 * 2^3 = 8.0, but capped at 5.0
        assert policy.calculate_delay(3) == 5.0
        
        # Attempt 4: Still capped at 5.0
        assert policy.calculate_delay(4) == 5.0


class TestWithRetryDecorator:
    """Test with_retry decorator functionality."""
    
    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self):
        """Test function succeeds without retries."""
        mock_func = AsyncMock(return_value="success")
        
        @with_retry()
        async def test_func():
            return await mock_func()
        
        result = await test_func()
        
        assert result == "success"
        assert mock_func.call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_on_retryable_exception(self):
        """Test function retries on retryable exception."""
        mock_func = AsyncMock(side_effect=[
            httpx.NetworkError("Connection failed"),
            "success"
        ])
        
        @with_retry(RetryPolicy(base_delay=0.01))
        async def test_func():
            return await mock_func()
        
        result = await test_func()
        
        assert result == "success"
        assert mock_func.call_count == 2
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test exception is raised after max retries exceeded."""
        mock_func = AsyncMock(side_effect=httpx.NetworkError("Connection failed"))
        
        @with_retry(RetryPolicy(max_retries=2, base_delay=0.01))
        async def test_func():
            return await mock_func()
        
        with pytest.raises(httpx.NetworkError, match="Connection failed"):
            await test_func()
        
        # Initial attempt + 2 retries = 3 calls
        assert mock_func.call_count == 3
    
    @pytest.mark.asyncio
    async def test_no_retry_on_non_retryable_exception(self):
        """Test function doesn't retry on non-retryable exception."""
        mock_func = AsyncMock(side_effect=ValueError("Not retryable"))
        
        @with_retry(RetryPolicy(max_retries=3, base_delay=0.01))
        async def test_func():
            return await mock_func()
        
        with pytest.raises(ValueError, match="Not retryable"):
            await test_func()
        
        assert mock_func.call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_on_http_5xx_error(self):
        """Test retry on HTTP 5xx status error."""
        response_mock = MagicMock()
        response_mock.status_code = 503
        
        mock_func = AsyncMock(side_effect=[
            httpx.HTTPStatusError(
                "Service Unavailable",
                request=MagicMock(),
                response=response_mock
            ),
            "success"
        ])
        
        @with_retry(RetryPolicy(base_delay=0.01))
        async def test_func():
            return await mock_func()
        
        result = await test_func()
        
        assert result == "success"
        assert mock_func.call_count == 2
    
    @pytest.mark.asyncio
    async def test_no_retry_on_http_4xx_error(self):
        """Test no retry on HTTP 4xx status error."""
        response_mock = MagicMock()
        response_mock.status_code = 400
        
        mock_func = AsyncMock(side_effect=httpx.HTTPStatusError(
            "Bad Request",
            request=MagicMock(),
            response=response_mock
        ))
        
        @with_retry(RetryPolicy(max_retries=3, base_delay=0.01))
        async def test_func():
            return await mock_func()
        
        with pytest.raises(httpx.HTTPStatusError, match="Bad Request"):
            await test_func()
        
        assert mock_func.call_count == 1
    
    @pytest.mark.asyncio
    async def test_exponential_backoff_delay(self):
        """Test that delays increase exponentially."""
        sleep_calls = []
        
        async def mock_sleep(duration):
            sleep_calls.append(duration)
        
        mock_func = AsyncMock(side_effect=[
            httpx.NetworkError("Error 1"),
            httpx.NetworkError("Error 2"),
            httpx.NetworkError("Error 3"),
            "success"
        ])
        
        with patch('asyncio.sleep', mock_sleep):
            @with_retry(RetryPolicy(base_delay=0.5, exponential_base=2.0, max_delay=10.0))
            async def test_func():
                return await mock_func()
            
            await test_func()
        
        # Should sleep between retries: 0.5, 1.0, 2.0
        assert len(sleep_calls) == 3
        assert sleep_calls[0] == 0.5
        assert sleep_calls[1] == 1.0
        assert sleep_calls[2] == 2.0
    
    @pytest.mark.asyncio
    async def test_custom_retryable_exceptions(self):
        """Test custom retryable exceptions."""
        mock_func = AsyncMock(side_effect=[
            ValueError("Retryable value error"),
            "success"
        ])
        
        policy = RetryPolicy(
            base_delay=0.01,
            retryable_exceptions=(ValueError,)
        )
        
        @with_retry(policy)
        async def test_func():
            return await mock_func()
        
        result = await test_func()
        
        assert result == "success"
        assert mock_func.call_count == 2
    
    @pytest.mark.asyncio
    async def test_preserves_function_metadata(self):
        """Test decorator preserves function metadata."""
        
        @with_retry()
        async def my_test_function():
            """My docstring."""
            return "test"
        
        assert my_test_function.__name__ == "my_test_function"
        assert my_test_function.__doc__ == "My docstring."
    
    @pytest.mark.asyncio
    async def test_with_function_arguments(self):
        """Test retry works with function arguments."""
        mock_func = AsyncMock(side_effect=[
            httpx.NetworkError("Error"),
            "success"
        ])
        
        @with_retry(RetryPolicy(base_delay=0.01))
        async def test_func(arg1, arg2, kwarg1=None):
            return await mock_func(arg1, arg2, kwarg1)
        
        result = await test_func("a", "b", kwarg1="c")
        
        assert result == "success"
        mock_func.assert_called_with("a", "b", "c")
    
    @pytest.mark.asyncio
    async def test_logs_retry_attempts(self):
        """Test that retry attempts are logged."""
        mock_func = AsyncMock(side_effect=[
            httpx.NetworkError("Connection failed"),
            httpx.NetworkError("Still failed"),
            "success"
        ])
        
        with patch('gateway.app.providers.retry.logger') as mock_logger:
            @with_retry(RetryPolicy(base_delay=0.01))
            async def test_func():
                return await mock_func()
            
            await test_func()
        
        # Should log retry attempts
        assert mock_logger.warning.call_count == 2
        log_messages = [call.args[0] for call in mock_logger.warning.call_args_list]
        assert any("Retry 1/3" in msg for msg in log_messages)
        assert any("Retry 2/3" in msg for msg in log_messages)


class TestWithRetryOnBaseProvider:
    """Test with_retry integration with BaseProvider."""
    
    @pytest.mark.asyncio
    async def test_retry_on_chat_completion(self):
        """Test retry works with chat_completion method."""
        from gateway.app.providers.base import BaseProvider
        from gateway.app.providers.retry import with_retry
        
        class TestProvider(BaseProvider):
            def __init__(self):
                super().__init__("https://api.test.com", "test-key")
                self.call_count = 0
            
            @with_retry(RetryPolicy(base_delay=0.01))
            async def chat_completion(self, payload):
                self.call_count += 1
                if self.call_count < 2:
                    raise httpx.NetworkError("Connection failed")
                return {"choices": [{"message": {"content": "success"}}]}
            
            async def stream_chat(self, payload):
                yield "test"
            
            async def health_check(self, timeout: float = 2.0) -> bool:
                return True
        
        provider = TestProvider()
        result = await provider.chat_completion({"messages": []})
        
        assert result["choices"][0]["message"]["content"] == "success"
        assert provider.call_count == 2


class TestRetryPolicyIsRetryable:
    """Test RetryPolicy.is_retryable method."""
    
    def test_is_retryable_network_error(self):
        """Test NetworkError is retryable."""
        policy = RetryPolicy()
        error = httpx.NetworkError("Connection failed")
        
        assert policy.is_retryable(error) is True
    
    def test_is_retryable_timeout(self):
        """Test TimeoutException is retryable."""
        policy = RetryPolicy()
        error = httpx.TimeoutException("Request timed out")
        
        assert policy.is_retryable(error) is True
    
    def test_is_retryable_connect_error(self):
        """Test ConnectError is retryable."""
        policy = RetryPolicy()
        error = httpx.ConnectError("Connection refused")
        
        assert policy.is_retryable(error) is True
    
    def test_is_retryable_http_5xx(self):
        """Test HTTP 5xx errors are retryable."""
        policy = RetryPolicy()
        response_mock = MagicMock()
        response_mock.status_code = 503
        error = httpx.HTTPStatusError(
            "Service Unavailable",
            request=MagicMock(),
            response=response_mock
        )
        
        assert policy.is_retryable(error) is True
    
    def test_is_not_retryable_http_4xx(self):
        """Test HTTP 4xx errors are not retryable."""
        policy = RetryPolicy()
        response_mock = MagicMock()
        response_mock.status_code = 400
        error = httpx.HTTPStatusError(
            "Bad Request",
            request=MagicMock(),
            response=response_mock
        )
        
        assert policy.is_retryable(error) is False
    
    def test_is_not_retryable_http_404(self):
        """Test HTTP 404 error is not retryable."""
        policy = RetryPolicy()
        response_mock = MagicMock()
        response_mock.status_code = 404
        error = httpx.HTTPStatusError(
            "Not Found",
            request=MagicMock(),
            response=response_mock
        )
        
        assert policy.is_retryable(error) is False
    
    def test_is_not_retryable_http_429(self):
        """Test HTTP 429 (Rate Limit) is retryable (5xx behavior)."""
        policy = RetryPolicy()
        response_mock = MagicMock()
        response_mock.status_code = 429
        error = httpx.HTTPStatusError(
            "Too Many Requests",
            request=MagicMock(),
            response=response_mock
        )
        
        # Note: Currently 4xx are not retried. For rate limiting, 
        # you might want to add special handling in the future.
        assert policy.is_retryable(error) is False
    
    def test_is_not_retryable_value_error(self):
        """Test ValueError is not retryable by default."""
        policy = RetryPolicy()
        error = ValueError("Invalid input")
        
        assert policy.is_retryable(error) is False
    
    def test_custom_retryable_exception(self):
        """Test custom exceptions can be configured as retryable."""
        policy = RetryPolicy(retryable_exceptions=(ValueError,))
        error = ValueError("Retryable error")
        
        assert policy.is_retryable(error) is True
