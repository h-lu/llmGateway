from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request as StarletteRequest

from gateway.app.api.chat import router as chat_router
from gateway.app.api.metrics import router as metrics_router, MetricsMiddleware
from gateway.app.core.http_client import init_http_client
from gateway.app.core.logging import get_logger, setup_logging
from gateway.app.db.async_session import close_async_engine, init_async_db
from gateway.app.db import models  # noqa: F401 - import to register models
from gateway.app.core.config import settings
from gateway.app.exceptions import AuthenticationError, QuotaExceededError, RuleViolationError
from gateway.app.middleware.rate_limit import RateLimitMiddleware
from gateway.app.middleware.request_id import RequestIdMiddleware
from gateway.app.services.async_logger import get_async_logger
from gateway.app.providers.factory import get_health_checker


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application instance
    """
    # Setup logging
    setup_logging()
    logger = get_logger(__name__)
    
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[dict, None]:
        """Application lifespan context manager.
        
        Initializes shared resources (HTTP connection pool, async database,
        and health checker) on startup and gracefully cleans up on shutdown.
        """
        # Startup: Initialize shared HTTP client with connection pooling
        async with init_http_client() as http_client:
            # Initialize async database (create tables)
            await init_async_db()
            
            # Start provider health checker
            health_checker = get_health_checker()
            await health_checker.start()
            
            logger.info(
                "Application startup complete",
                extra={
                    "providers": health_checker.get_all_status(),
                    "debug_mode": settings.debug
                }
            )
            
            yield {"http_client": http_client}
        
        # Shutdown: Stop health checker, flush conversation logs, and close database
        health_checker = get_health_checker()
        await health_checker.stop()
        
        async_logger = get_async_logger()
        await async_logger.shutdown()
        
        # Close cache connections (Redis)
        from gateway.app.core.cache import get_cache
        cache = get_cache()
        if hasattr(cache, 'close'):
            await cache.close()
        
        await close_async_engine()
        
        logger.info("Application shutdown complete")
    
    app = FastAPI(
        title="TeachProxy Gateway",
        description="AI gateway with rate limiting, quota management, and rule-based content filtering",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # Add middleware (order matters: last added = first executed)
    # Request body size limit middleware (outermost - checks first)
    from gateway.app.middleware.request_size import RequestSizeLimitMiddleware
    app.add_middleware(RequestSizeLimitMiddleware, max_body_size=10 * 1024 * 1024)  # 10MB limit
    
    # Metrics middleware - collects request metrics
    app.add_middleware(MetricsMiddleware)
    
    # Rate limit middleware
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=settings.rate_limit_requests_per_minute,
        burst_size=settings.rate_limit_burst_size,
        window_seconds=settings.rate_limit_window_seconds
    )
    
    # Request ID middleware for tracing (innermost - closest to route)
    app.add_middleware(RequestIdMiddleware)
    
    # Include routers
    app.include_router(chat_router)
    app.include_router(metrics_router, prefix="")
    
    @app.get("/health")
    def health() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "ok"}
    
    @app.get("/v1/models")
    async def list_models() -> dict[str, Any]:
        """List available models (OpenAI API compatible)."""
        return {
            "object": "list",
            "data": [
                {
                    "id": "deepseek-chat",
                    "object": "model",
                    "created": 1700000000,
                    "owned_by": "deepseek"
                },
                {
                    "id": "gpt-4",
                    "object": "model",
                    "created": 1700000000,
                    "owned_by": "openai"
                },
                {
                    "id": "gpt-3.5-turbo",
                    "object": "model",
                    "created": 1700000000,
                    "owned_by": "openai"
                }
            ]
        }
    
    @app.exception_handler(QuotaExceededError)
    async def quota_exceeded_handler(request: Request, exc: QuotaExceededError) -> JSONResponse:
        """Handle QuotaExceededError and return HTTP 429 response."""
        return JSONResponse(
            status_code=429,
            content={
                "error": "quota_exceeded",
                "message": str(exc),
                "remaining_tokens": exc.remaining,
                "reset_week": exc.reset_week,
            }
        )
    
    @app.exception_handler(AuthenticationError)
    async def auth_error_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
        """Handle AuthenticationError and return HTTP 401 response."""
        return JSONResponse(
            status_code=401,
            content={"error": "authentication_failed", "message": exc.detail}
        )
    
    @app.exception_handler(RuleViolationError)
    async def rule_violation_handler(request: Request, exc: RuleViolationError) -> JSONResponse:
        """Handle RuleViolationError and return HTTP 400 response."""
        return JSONResponse(
            status_code=400,
            content={"error": "rule_violation", "message": exc.message, "rule_id": exc.rule_id}
        )
    
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Global exception handler for unhandled exceptions.
        
        Security notes:
        - Never returns raw traceback to client (even in debug mode)
        - Logs full details server-side for debugging
        - Returns generic message in production
        - Debug mode returns exception message but not stack trace
        """
        import traceback
        
        # Generate traceback for logging (never sent to client)
        tb_str = traceback.format_exc()
        request_id = getattr(request.state, 'request_id', 'unknown')
        
        # Log full exception details server-side
        logger.exception(
            f"Unhandled exception [request_id={request_id}]",
            extra={
                "request_id": request_id,
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "traceback": tb_str,
            }
        )
        
        # Debug mode: return limited diagnostic info (no traceback)
        if settings.debug:
            return JSONResponse(
                status_code=500,
                content={
                    "error": "internal_error",
                    "message": str(exc),
                    "exception_type": type(exc).__name__,
                    "request_id": request_id,
                    # Note: traceback is intentionally omitted for security
                    # Check server logs for full stack trace
                }
            )
        
        # Production: return generic error message (no details)
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "message": "Internal server error",
                "request_id": request_id,  # Include for support correlation
            }
        )
    
    return app


# Create the application instance
app = create_app()
