"""Request body size limit middleware.

This middleware limits the size of incoming request bodies to prevent
memory exhaustion attacks and ensure fair resource usage.

Enforces size limits for both Content-Length and chunked transfer encoding.
"""

from starlette.types import Receive, Scope, Send


class SizeLimitedStream:
    """A stream wrapper that enforces size limits during reading.

    This prevents chunked transfer encoding bypass by counting bytes
    as they are read from the stream.
    """

    # Custom exception for size limit violations
    class SizeExceededError(Exception):
        """Raised when request body exceeds size limit."""

        pass

    def __init__(self, receive: Receive, max_size: int):
        """Initialize the size-limited stream.

        Args:
            receive: The ASGI receive callable
            max_size: Maximum number of bytes allowed
        """
        self._receive = receive
        self._max_size = max_size
        self._bytes_read = 0
        self._buffer = b""
        self._body_complete = False

    async def receive(self) -> dict:
        """Receive and enforce size limit.

        Returns:
            ASGI message dictionary

        Raises:
            SizeExceededError: If body size exceeds max_size
        """
        if self._body_complete:
            # Body already complete, return empty message
            return {"type": "http.request", "body": b"", "more_body": False}

        message = await self._receive()

        if message["type"] == "http.request":
            body = message.get("body", b"")
            more_body = message.get("more_body", False)

            # Track bytes read
            self._bytes_read += len(body)

            # Check size limit
            if self._bytes_read > self._max_size:
                raise self.SizeExceededError(
                    f"Request body too large. Maximum allowed: {self._max_size} bytes"
                )

            # Update completion status
            if not more_body:
                self._body_complete = True

            return message

        return message


class RequestSizeLimitMiddleware:
    """ASGI middleware to limit request body size.

    Prevents large request bodies from consuming excessive memory.
    Returns HTTP 413 (Payload Too Large) if the limit is exceeded.

    Works for both Content-Length header and chunked transfer encoding.
    This implementation uses raw ASGI middleware to properly intercept
    the receive callable before Starlette's Request is constructed.

    Usage:
        app.add_middleware(RequestSizeLimitMiddleware, max_body_size=10*1024*1024)
    """

    def __init__(self, app, max_body_size: int = 10 * 1024 * 1024):
        """Initialize the middleware.

        Args:
            app: The ASGI application
            max_body_size: Maximum allowed body size in bytes (default: 10MB)
        """
        self.app = app
        self.max_body_size = max_body_size

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Process the ASGI request with size limit enforcement."""
        if scope["type"] != "http":
            # Only intercept HTTP requests
            await self.app(scope, receive, send)
            return

        # Check Content-Length header first (fast path for most requests)
        content_length = None
        for name, value in scope.get("headers", []):
            if name.lower() == b"content-length":
                content_length = value.decode()
                break

        if content_length:
            try:
                size = int(content_length)
                if size > self.max_body_size:
                    # Reject immediately without reading body
                    await self._send_413_response(send)
                    return
            except ValueError:
                # Invalid Content-Length, continue to stream check
                pass

        # Wrap the receive callable to enforce size limit during streaming
        # This properly handles chunked transfer encoding
        size_limited_receive = SizeLimitedStream(receive, self.max_body_size).receive

        try:
            await self.app(scope, size_limited_receive, send)
        except SizeLimitedStream.SizeExceededError as exc:
            # Catch size limit violations and send 413 response
            await self._send_413_response(send, detail=str(exc))
        except Exception:
            # For other unexpected exceptions, still send 413 as safety measure
            await self._send_413_response(send)
            raise

    async def _send_413_response(self, send: Send, detail: str = None) -> None:
        """Send a 413 Payload Too Large response.

        Args:
            send: The ASGI send callable
            detail: Optional detail message
        """
        if detail is None:
            detail = (
                f"Request body too large. Maximum allowed: {self.max_body_size} bytes"
            )

        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    [b"content-type", b"application/json"],
                    [b"content-length", str(len(detail)).encode()],
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": detail.encode(),
            }
        )
