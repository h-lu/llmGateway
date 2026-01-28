"""Request ID middleware for distributed tracing.

This middleware adds a unique request ID to each incoming request,
enabling request tracking across logs and responses.

It also supports W3C Trace Context for distributed tracing:
https://www.w3.org/TR/trace-context/
"""

import uuid
from typing import Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from gateway.app.core.tracing import (
    TraceContext,
    set_current_trace_context,
)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Middleware to add request ID and W3C Trace Context to all requests.
    
    The request ID is:
    1. Extracted from X-Request-ID header if present
    2. Generated as UUID if not present
    3. Added to request.state for access in endpoints
    4. Returned in X-Request-ID response header
    
    W3C Trace Context (traceparent):
    1. Extracted from traceparent header if present
    2. Generated if not present
    3. Stored in async context variable for propagation
    4. Returned in traceparent response header
    """
    
    def __init__(
        self, 
        app, 
        header_name: str = "X-Request-ID",
        traceparent_header: str = "traceparent"
    ):
        super().__init__(app)
        self.header_name = header_name
        self.traceparent_header = traceparent_header
    
    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request and add request ID and trace context."""
        # Get or generate request ID
        request_id = request.headers.get(self.header_name)
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # Store in request state for access in endpoints
        request.state.request_id = request_id
        
        # Handle W3C Trace Context
        traceparent = request.headers.get(self.traceparent_header)
        trace_context: Optional[TraceContext] = None
        
        if traceparent:
            # Try to parse incoming traceparent
            trace_context = TraceContext.from_traceparent(traceparent)
        
        if trace_context is None:
            # Generate new trace context
            trace_context = TraceContext.generate_new()
        
        # Create child context for this service
        trace_context = trace_context.create_child()
        
        # Store in request state and context variable
        request.state.trace_context = trace_context
        set_current_trace_context(trace_context)
        
        # Process request
        response = await call_next(request)
        
        # Add request ID to response headers
        response.headers[self.header_name] = request_id
        
        # Add traceparent to response headers
        response.headers[self.traceparent_header] = trace_context.to_traceparent()
        
        return response


def get_request_id(request: Request) -> str:
    """Get request ID from request state.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Request ID string
    """
    return getattr(request.state, "request_id", "unknown")


def get_trace_context(request: Request) -> Optional[TraceContext]:
    """Get trace context from request state.
    
    Args:
        request: FastAPI request object
        
    Returns:
        TraceContext or None if not available
    """
    return getattr(request.state, "trace_context", None)


def get_trace_id(request: Request) -> Optional[str]:
    """Get trace ID from request state.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Trace ID string or None if not available
    """
    context = get_trace_context(request)
    return context.trace_id if context else None


def get_traceparent(request: Request) -> Optional[str]:
    """Get traceparent header value from request state.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Traceparent string or None if not available
    """
    context = get_trace_context(request)
    return context.to_traceparent() if context else None
