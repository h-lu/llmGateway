from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI

from gateway.app.api.chat import router as chat_router
from gateway.app.api.metrics import router as metrics_router
from gateway.app.core.http_client import init_http_client
from gateway.app.core.logging import setup_logging
from gateway.app.db.async_session import close_async_engine, init_async_db
from gateway.app.db import models  # noqa: F401 - import to register models
from gateway.app.middleware.rate_limit import RateLimitMiddleware
from gateway.app.middleware.request_id import RequestIdMiddleware
from gateway.app.services.async_logger import get_async_logger


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application instance
    """
    # Setup logging
    setup_logging()
    
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[dict, None]:
        """Application lifespan context manager.
        
        Initializes shared resources (HTTP connection pool and async database)
        on startup and gracefully cleans up on shutdown.
        """
        # Startup: Initialize shared HTTP client with connection pooling
        async with init_http_client() as http_client:
            # Initialize async database (create tables)
            await init_async_db()
            
            yield {"http_client": http_client}
        
        # Shutdown: Flush conversation logs and close database
        async_logger = get_async_logger()
        await async_logger.shutdown()
        await close_async_engine()
    
    app = FastAPI(
        title="TeachProxy Gateway",
        description="AI gateway with rate limiting, quota management, and rule-based content filtering",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # Add middleware (order matters: last added = first executed)
    # Rate limit middleware
    app.add_middleware(
        RateLimitMiddleware,
        requests_per_minute=60,
        burst_size=10,
        window_seconds=60
    )
    
    # Request ID middleware for tracing
    app.add_middleware(RequestIdMiddleware)
    
    # Include routers
    app.include_router(chat_router)
    app.include_router(metrics_router, prefix="")
    
    @app.get("/health")
    def health():
        """Health check endpoint."""
        return {"status": "ok"}
    
    @app.get("/v1/models")
    async def list_models():
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
    
    return app


# Create the application instance
app = create_app()
