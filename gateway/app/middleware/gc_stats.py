"""GC statistics middleware for tracking garbage collection impact on latency.

This middleware disables GC during request processing and tracks
GC-related metrics to help identify performance issues.
"""

import gc
import time
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from gateway.app.core.logging import get_logger

logger = get_logger(__name__)


class GCStatsMiddleware(BaseHTTPMiddleware):
    """Track GC impact on request latency.
    
    This middleware:
    1. Disables GC during request processing to prevent pauses
    2. Tracks object creation during the request
    3. Re-enables GC and performs young generation collection after
    4. Adds headers with GC metrics for monitoring
    
    Note: This middleware should be placed early in the middleware stack
    (added after other middleware) to ensure GC is disabled for the
    entire request duration.
    """
    
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Response]
    ) -> Response:
        """Process request with GC disabled.
        
        Args:
            request: FastAPI request object
            call_next: Next middleware/endpoint in chain
            
        Returns:
            Response with GC metrics in headers
        """
        gc_counts_before = gc.get_count()
        
        # Disable GC during request to prevent pauses
        gc_enabled_before = gc.isenabled()
        gc.disable()
        start_time = time.time()
        
        try:
            response = await call_next(request)
        finally:
            # Re-enable GC and collect young generation
            if gc_enabled_before:
                gc.enable()
            gc.collect(0)
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        gc_counts_after = gc.get_count()
        objects_created = sum(gc_counts_after) - sum(gc_counts_before)
        
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
