"""Request router with streaming vs non-streaming separation.

This module provides intelligent request routing that prioritizes
fast (non-streaming) requests over streaming ones to improve P50 latency.
"""

import asyncio
from enum import Enum
from typing import Optional


class RequestPriority(Enum):
    """Priority levels for different request types."""
    HIGH = 1
    NORMAL = 2
    STREAMING = 3
    BACKGROUND = 4


class RequestRouter:
    """Smart request router with separate limits for streaming vs normal.
    
    This router separates streaming and non-streaming requests into
    different concurrency pools to ensure fast non-streaming requests
    are not blocked by long-running streaming connections.
    
    Design:
    - Streaming: Limited to 50 concurrent connections (long-lived)
    - Normal: Allows 200 concurrent requests (fast, high priority)
    - Timeouts prevent indefinite blocking
    
    Usage:
        router = RequestRouter()
        
        # For streaming requests
        if await router.acquire_streaming_slot():
            try:
                # Process streaming request
                pass
            finally:
                router.release_streaming_slot()
        
        # For normal requests
        if await router.acquire_normal_slot():
            try:
                # Process normal request
                pass
            finally:
                router.release_normal_slot()
    """
    
    # Default limits
    DEFAULT_STREAMING_LIMIT = 50
    DEFAULT_NORMAL_LIMIT = 200
    DEFAULT_TIMEOUT = 5.0
    
    def __init__(
        self,
        streaming_limit: int = DEFAULT_STREAMING_LIMIT,
        normal_limit: int = DEFAULT_NORMAL_LIMIT,
        timeout: float = DEFAULT_TIMEOUT
    ):
        """Initialize the request router.
        
        Args:
            streaming_limit: Maximum concurrent streaming requests
            normal_limit: Maximum concurrent normal requests
            timeout: Timeout in seconds for slot acquisition
        """
        self.streaming_limit = streaming_limit
        self.normal_limit = normal_limit
        self.timeout = timeout
        
        self._streaming_semaphore = asyncio.Semaphore(streaming_limit)
        self._normal_semaphore = asyncio.Semaphore(normal_limit)
        self._lock = asyncio.Lock()
        
        # Counters for monitoring
        self._streaming_active = 0
        self._normal_active = 0
        self._streaming_total = 0
        self._normal_total = 0
        self._streaming_rejected = 0
        self._normal_rejected = 0
    
    async def acquire_streaming_slot(self) -> bool:
        """Acquire a slot for streaming request.
        
        Returns:
            True if slot acquired, False if timeout
        """
        try:
            await asyncio.wait_for(
                self._streaming_semaphore.acquire(),
                timeout=self.timeout
            )
            async with self._lock:
                self._streaming_active += 1
                self._streaming_total += 1
            return True
        except asyncio.TimeoutError:
            async with self._lock:
                self._streaming_rejected += 1
            return False
    
    def release_streaming_slot(self) -> None:
        """Release a streaming request slot."""
        self._streaming_semaphore.release()
        asyncio.create_task(self._decrement_streaming())
    
    async def _decrement_streaming(self) -> None:
        """Safely decrement streaming counter."""
        async with self._lock:
            self._streaming_active = max(0, self._streaming_active - 1)
    
    async def acquire_normal_slot(self) -> bool:
        """Acquire a slot for normal (non-streaming) request.
        
        Returns:
            True if slot acquired, False if timeout
        """
        try:
            await asyncio.wait_for(
                self._normal_semaphore.acquire(),
                timeout=self.timeout
            )
            async with self._lock:
                self._normal_active += 1
                self._normal_total += 1
            return True
        except asyncio.TimeoutError:
            async with self._lock:
                self._normal_rejected += 1
            return False
    
    def release_normal_slot(self) -> None:
        """Release a normal request slot."""
        self._normal_semaphore.release()
        asyncio.create_task(self._decrement_normal())
    
    async def _decrement_normal(self) -> None:
        """Safely decrement normal counter."""
        async with self._lock:
            self._normal_active = max(0, self._normal_active - 1)
    
    def get_stats(self) -> dict:
        """Get current router statistics.
        
        Returns:
            Dictionary with current stats
        """
        return {
            "streaming": {
                "active": self._streaming_active,
                "limit": self.streaming_limit,
                "available": self.streaming_limit - self._streaming_active,
                "utilization": round(self._streaming_active / self.streaming_limit, 4) if self.streaming_limit > 0 else 0,
                "total_processed": self._streaming_total,
                "total_rejected": self._streaming_rejected,
            },
            "normal": {
                "active": self._normal_active,
                "limit": self.normal_limit,
                "available": self.normal_limit - self._normal_active,
                "utilization": round(self._normal_active / self.normal_limit, 4) if self.normal_limit > 0 else 0,
                "total_processed": self._normal_total,
                "total_rejected": self._normal_rejected,
            },
            "capacity": {
                "total_active": self._streaming_active + self._normal_active,
                "total_limit": self.streaming_limit + self.normal_limit,
                "total_utilization": round(
                    (self._streaming_active + self._normal_active) / 
                    (self.streaming_limit + self.normal_limit), 4
                ) if (self.streaming_limit + self.normal_limit) > 0 else 0,
            }
        }
    
    async def reset_stats(self) -> None:
        """Reset statistics counters (useful for testing)."""
        async with self._lock:
            self._streaming_total = 0
            self._normal_total = 0
            self._streaming_rejected = 0
            self._normal_rejected = 0


# Global instance
_request_router: Optional[RequestRouter] = None


def get_request_router() -> RequestRouter:
    """Get the global request router instance.
    
    Returns:
        RequestRouter singleton instance
    """
    global _request_router
    if _request_router is None:
        _request_router = RequestRouter()
    return _request_router


def reset_request_router() -> None:
    """Reset the global request router (useful for testing)."""
    global _request_router
    _request_router = None
