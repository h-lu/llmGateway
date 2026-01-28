from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import Any, Dict, AsyncGenerator, Optional
import httpx


class BaseProvider(ABC):
    """Base class for AI providers.
    
    Subclasses can accept an external httpx.AsyncClient for connection pooling,
    or create their own if not provided.
    
    This base class provides common HTTP client management logic that can be
    shared across all provider implementations.
    """
    
    def __init__(
        self, 
        base_url: str, 
        api_key: str,
        http_client: Optional[httpx.AsyncClient] = None,
        timeout: float = 60.0
    ):
        """Initialize the provider.
        
        Args:
            base_url: The API base URL
            api_key: The API key for authentication
            http_client: Optional shared HTTP client for connection pooling
            timeout: Request timeout in seconds
        """
        self._http_client = http_client
        self.base_url = base_url.rstrip('/')  # Remove trailing slash
        self.api_key = api_key
        self.timeout = timeout
        self.headers = self._build_headers()
    
    @property
    def http_client(self) -> Optional[httpx.AsyncClient]:
        """Get the HTTP client, if one was provided."""
        return self._http_client
    
    def _build_headers(self) -> Dict[str, str]:
        """Build the HTTP headers for API requests.
        
        Returns:
            Dictionary of HTTP headers
        """
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def _get_client(self) -> httpx.AsyncClient:
        """Get the HTTP client to use for requests.
        
        Returns:
            httpx.AsyncClient instance
        """
        if self._http_client is not None:
            return self._http_client
        # Fallback: create a new client (not recommended for production)
        return httpx.AsyncClient(timeout=self.timeout)
    
    @asynccontextmanager
    async def _client_context(self):
        """Context manager for HTTP client lifecycle.
        
        If using shared client, just yield it.
        If using per-request client, manage its lifecycle.
        
        Yields:
            httpx.AsyncClient: HTTP client to use
        """
        client = self._get_client()
        is_shared = self._http_client is not None
        try:
            yield client
        finally:
            if not is_shared:
                await client.aclose()
    
    def _get_endpoint_url(self, endpoint: str) -> str:
        """Build full URL for an API endpoint.
        
        Args:
            endpoint: API endpoint path (e.g., "/chat/completions")
            
        Returns:
            Full URL
        """
        return f"{self.base_url}{endpoint}"
    
    @abstractmethod
    async def chat_completion(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Send a non-streaming chat completion request.
        
        Args:
            payload: The request payload containing model, messages, etc.
            
        Returns:
            The JSON response from the API
        """
        pass
    
    @abstractmethod
    async def stream_chat(self, payload: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Send a streaming chat completion request, yielding chunks.
        
        Args:
            payload: The request payload containing model, messages, etc.
            
        Yields:
            Lines from the SSE stream
        """
        pass
    
    @abstractmethod
    async def health_check(self, timeout: float = 2.0) -> bool:
        """Check if the provider is healthy.
        
        Subclasses must implement this method to provide provider-specific
        health checks. A typical implementation calls a lightweight endpoint
        like /models with a short timeout.
        
        Args:
            timeout: Request timeout in seconds (default: 2.0)
            
        Returns:
            True if the provider is healthy, False otherwise
        """
        pass
