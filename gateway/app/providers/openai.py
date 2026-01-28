"""OpenAI API provider implementation.

Compatible with OpenAI API and other OpenAI-compatible endpoints
(e.g., Azure OpenAI, local LLMs with OpenAI-compatible API).
"""

from typing import Any, Dict, AsyncGenerator, Optional

import httpx

from gateway.app.providers.base import BaseProvider


class OpenAIProvider(BaseProvider):
    """OpenAI API provider with support for shared HTTP client connection pooling.
    
    This provider is compatible with:
    - OpenAI API (https://api.openai.com/v1)
    - Azure OpenAI (with appropriate base_url)
    - Other OpenAI-compatible endpoints
    
    If http_client is provided, it will be used for all requests (connection reuse).
    If not, a new client is created per-request (backward compatible, but not recommended).
    """
    
    def __init__(
        self, 
        base_url: str, 
        api_key: str,
        organization: Optional[str] = None,
        http_client: Optional[httpx.AsyncClient] = None,
        timeout: float = 60.0
    ):
        """Initialize OpenAI provider.
        
        Args:
            base_url: The OpenAI API base URL
            api_key: The OpenAI API key
            organization: Optional organization ID
            http_client: Optional shared HTTP client
            timeout: Request timeout in seconds
        """
        super().__init__(base_url, api_key, http_client, timeout)
        self.organization = organization
        
        # Add organization header if provided
        if organization:
            self.headers["OpenAI-Organization"] = organization
    
    async def chat_completion(
        self, 
        payload: Dict[str, Any],
        traceparent: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send a non-streaming chat completion request.
        
        Args:
            payload: The request payload (model, messages, temperature, etc.)
            traceparent: Optional W3C traceparent header for distributed tracing
            
        Returns:
            The JSON response from the API
            
        Raises:
            httpx.HTTPStatusError: If the API returns an error
        """
        url = self._get_endpoint_url("/chat/completions")
        headers = self._get_request_headers(traceparent)
        
        async with self._client_context() as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
    
    async def stream_chat(
        self, 
        payload: Dict[str, Any],
        traceparent: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Send a streaming chat completion request, yielding chunks.
        
        Args:
            payload: The request payload (model, messages, temperature, etc.)
            traceparent: Optional W3C traceparent header for distributed tracing
            
        Yields:
            Lines from the SSE stream
            
        Raises:
            httpx.HTTPStatusError: If the API returns an error
        """
        url = self._get_endpoint_url("/chat/completions")
        payload["stream"] = True
        headers = self._get_request_headers(traceparent)
        
        # For streaming, we need to handle client lifecycle carefully
        client = self._get_client()
        is_shared = self._http_client is not None
        
        try:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    yield line
        finally:
            if not is_shared:
                await client.aclose()
    
    async def health_check(self, timeout: float = 2.0) -> bool:
        """Check if the OpenAI provider is healthy.
        
        Calls the /models endpoint with a short timeout.
        
        Args:
            timeout: Request timeout in seconds (default: 2.0)
            
        Returns:
            True if the provider is healthy, False otherwise
        """
        try:
            url = self._get_endpoint_url("/models")
            async with self._client_context() as client:
                resp = await client.get(url, headers=self.headers, timeout=timeout)
                return resp.status_code == 200
        except Exception:
            return False
