"""Request body size limit middleware.

This middleware limits the size of incoming request bodies to prevent
memory exhaustion attacks and ensure fair resource usage.
"""

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to limit request body size.
    
    Prevents large request bodies from consuming excessive memory.
    Returns HTTP 413 (Payload Too Large) if the limit is exceeded.
    
    Usage:
        app.add_middleware(RequestSizeLimitMiddleware, max_body_size=10*1024*1024)
    """
    
    def __init__(self, app, max_body_size: int = 10 * 1024 * 1024):
        """Initialize the middleware.
        
        Args:
            app: The ASGI application
            max_body_size: Maximum allowed body size in bytes (default: 10MB)
        """
        super().__init__(app)
        self.max_body_size = max_body_size
    
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request with size limit check."""
        # Check Content-Length header if present
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
                if size > self.max_body_size:
                    raise HTTPException(
                        status_code=413,
                        detail=f"Request body too large. Maximum allowed: {self.max_body_size} bytes"
                    )
            except ValueError:
                # Invalid Content-Length header, let the request through
                # and catch issues during body reading
                pass
        
        # For requests without Content-Length (e.g., chunked encoding),
        # the limit will be enforced during body reading by the route handler
        # This is a best-effort check for the common case
        
        return await call_next(request)
