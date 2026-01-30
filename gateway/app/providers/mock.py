"""Mock provider for testing purposes.

This provider simulates AI responses without making external API calls.
It's useful for load testing and development when real API keys are not available.

Enable by setting environment variable:
    TEACHPROXY_MOCK_PROVIDER=true
"""

import asyncio
import json
import random
import time
import uuid
from typing import Any, AsyncGenerator, Dict, Optional

from gateway.app.providers.base import BaseProvider


class MockProvider(BaseProvider):
    """Mock AI provider that returns simulated responses.
    
    This provider is designed for testing and load testing scenarios where
    making real API calls is not desirable or possible.
    
    Features:
    - Simulates realistic response delays (configurable)
    - Supports both streaming and non-streaming responses
    - Returns consistent responses based on input
    - Configurable success/failure rates for testing error handling
    """
    
    def __init__(
        self,
        base_url: str = "http://mock.provider",
        api_key: str = "mock-key",
        http_client: Optional[Any] = None,
        timeout: float = 60.0,
        min_delay: float = 0.1,
        max_delay: float = 0.5,
        failure_rate: float = 0.0,
    ):
        """Initialize the mock provider.
        
        Args:
            base_url: Not used, provided for API compatibility
            api_key: Not used, provided for API compatibility
            http_client: Not used, provided for API compatibility
            timeout: Not used, provided for API compatibility
            min_delay: Minimum response delay in seconds
            max_delay: Maximum response delay in seconds
            failure_rate: Probability of returning an error (0-1)
        """
        super().__init__(base_url, api_key, http_client, timeout)
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.failure_rate = failure_rate
    
    def _generate_response(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a mock chat completion response.
        
        Args:
            payload: The request payload
            
        Returns:
            A response matching OpenAI/DeepSeek format
        """
        model = payload.get("model", "mock-model")
        messages = payload.get("messages", [])
        
        # Generate a response based on the last user message
        last_message = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_message = msg.get("content", "")
                break
        
        # Simulate token usage
        prompt_tokens = len(last_message.split()) * 2 if last_message else 10
        completion_tokens = random.randint(20, 100)
        
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": self._generate_content(last_message)
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }
        }
    
    def _generate_content(self, user_message: str) -> str:
        """Generate response content based on user message.
        
        Args:
            user_message: The user's message
            
        Returns:
            A relevant mock response
        """
        # Simple keyword-based responses for testing
        user_lower = user_message.lower()
        
        if any(kw in user_lower for kw in ["hello", "hi", "你好"]):
            return "Hello! I'm a mock AI assistant. How can I help you today?"
        
        if any(kw in user_lower for kw in ["python", "code", "programming"]):
            return "Python is a powerful programming language. Here's a simple example:\n\n```python\nprint('Hello, World!')\n```"
        
        if any(kw in user_lower for kw in ["sort", "algorithm", "排序"]):
            return "I understand you're asking about sorting algorithms. As a learning exercise, try to think about the time complexity of different approaches like bubble sort, quick sort, and merge sort."
        
        # Default response
        defaults = [
            "This is a mock response for testing purposes.",
            "I'm a simulated AI assistant helping with load testing.",
            "Mock provider is working correctly!",
            "Here's a sample response with some content to simulate token usage.",
        ]
        return random.choice(defaults)
    
    async def chat_completion(
        self,
        payload: Dict[str, Any],
        traceparent: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send a non-streaming chat completion request.
        
        Args:
            payload: The request payload
            traceparent: Optional trace header (ignored)
            
        Returns:
            Mock response
        """
        # Simulate network delay
        delay = random.uniform(self.min_delay, self.max_delay)
        await asyncio.sleep(delay)
        
        # Simulate random failures
        if random.random() < self.failure_rate:
            raise Exception("Simulated provider failure")
        
        return self._generate_response(payload)
    
    async def stream_chat(
        self,
        payload: Dict[str, Any],
        traceparent: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Send a streaming chat completion request.
        
        Args:
            payload: The request payload
            traceparent: Optional trace header (ignored)
            
        Yields:
            SSE-formatted chunks
        """
        # Simulate network delay before starting stream
        delay = random.uniform(self.min_delay, self.max_delay)
        await asyncio.sleep(delay)
        
        # Simulate random failures
        if random.random() < self.failure_rate:
            raise Exception("Simulated provider failure")
        
        model = payload.get("model", "mock-model")
        content = self._generate_content("")
        
        # Split content into chunks
        words = content.split()
        chunk_size = max(1, len(words) // 5)  # Split into ~5 chunks
        
        for i in range(0, len(words), chunk_size):
            chunk_words = words[i:i + chunk_size]
            chunk_content = " ".join(chunk_words)
            
            data = {
                "id": f"chatcmpl-{uuid.uuid4().hex[:24]}",
                "object": "chat.completion.chunk",
                "created": int(time.time()),
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {"content": chunk_content + " "},
                    "finish_reason": None
                }]
            }
            yield f"data: {json.dumps(data, ensure_ascii=False)}"
            
            # Small delay between chunks
            await asyncio.sleep(0.05)
        
        # End of stream
        yield "data: [DONE]"
    
    async def health_check(self, timeout: float = 2.0) -> bool:
        """Check if the provider is healthy.
        
        Mock provider is always healthy unless configured otherwise.
        
        Args:
            timeout: Ignored for mock provider
            
        Returns:
            True (mock provider is always healthy)
        """
        # Simulate a quick health check
        await asyncio.sleep(0.01)
        return True
