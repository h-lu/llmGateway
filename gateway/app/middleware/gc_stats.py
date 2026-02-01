"""GC statistics middleware for tracking garbage collection impact on latency.

This middleware tracks GC-related metrics to help identify performance issues.
Unlike the original implementation, it does NOT disable/enable GC per request
(which causes contention under high concurrency), but instead:
1. Tracks object creation during the request
2. Performs periodic young generation collection (not per-request)
3. Adds headers with GC metrics for monitoring
"""

import gc
import time
import asyncio
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from gateway.app.core.logging import get_logger

logger = get_logger(__name__)

# Request counter for periodic GC collection
_request_counter = 0
_counter_lock = asyncio.Lock()

# Collect GC every N requests (not per-request to avoid contention)
GC_COLLECTION_INTERVAL = 100


class GCStatsMiddleware(BaseHTTPMiddleware):
    """Track GC impact on request latency without per-request GC manipulation.
    
    This middleware:
    1. Tracks object creation during the request
    2. Performs periodic (not per-request) young generation collection
    3. Adds headers with GC metrics for monitoring
    
    Note: This version does NOT disable GC during requests to avoid
    contention issues under high concurrency.
    """
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Response]
    ) -> Response:
        """Process request with GC metrics tracking.
        
        Args:
            request: FastAPI request object
            call_next: Next middleware/endpoint in chain
            
        Returns:
            Response with GC metrics in headers
        """
        gc_counts_before = gc.get_count()
        start_time = time.time()
        
        # Process request (GC remains enabled to avoid contention)
        response = await call_next(request)
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        gc_counts_after = gc.get_count()
        objects_created = sum(gc_counts_after) - sum(gc_counts_before)
        
        # Periodic GC collection (not per-request)
        global _request_counter
        should_collect = False
        async with _counter_lock:
            _request_counter += 1
            if _request_counter >= GC_COLLECTION_INTERVAL:
                _request_counter = 0
                should_collect = True
        
        if should_collect:
            # Only collect young generation periodically
            # Use run_in_executor to avoid blocking the event loop
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, gc.collect, 0)
        
        # Add GC metrics to response headers
        response.headers["X-GC-Objects-Created"] = str(objects_created)
        response.headers["X-Request-Duration-Ms"] = f"{elapsed_ms:.2f}"
        
        # Log slow requests for analysis
        if elapsed_ms > 100:
            logger.warning(
                "Slow request detected",
                extra={
                    "path": request.url.path,
                    "duration_ms": elapsed_ms,
                    "objects_created": objects_created,
                }
            )
        
        return response
