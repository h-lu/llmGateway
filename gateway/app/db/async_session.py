"""Async database session management for SQLAlchemy 2.0+.

This module provides async database operations using PostgreSQL with asyncpg.
Uses QueuePool for efficient connection management under high concurrency.
"""

import asyncio
from contextlib import asynccontextmanager
from functools import lru_cache
from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from typing_extensions import Annotated

from gateway.app.core.config import settings
from gateway.app.core.logging import get_logger

logger = get_logger(__name__)

# Global session maker instance
_AsyncSessionLocal = None


@lru_cache(maxsize=1)
def get_async_engine(database_url: str | None = None) -> AsyncEngine:
    """Get or create the async database engine (thread-safe singleton).

    Uses PostgreSQL with optimized connection pool for high concurrency.
    Cached with lru_cache to ensure thread-safe singleton behavior.

    Optimizations:
    - pool_pre_ping disabled for performance (rely on pool_recycle)
    - asyncpg prepared statement cache enabled
    - Command timeout to prevent long-running queries

    Args:
        database_url: Optional database URL. Uses settings if not provided.

    Returns:
        AsyncEngine instance
    """
    url = database_url or settings.database_url

    # asyncpg-specific connection arguments for performance
    # Reference: https://magicstack.github.io/asyncpg/current/api/index.html
    connect_args = {
        "command_timeout": settings.db_command_timeout,
        "max_cached_statement_lifetime": 0,  # 0 means no limit
        # Note: prepared_statement_cache_size is set via server_settings in DSN or after connect
    }

    engine = create_async_engine(
        url,
        echo=False,
        future=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_recycle=settings.db_pool_recycle,
        pool_pre_ping=settings.db_pool_pre_ping,  # Configurable, default False for performance
        connect_args=connect_args,
    )
    logger.info(
        f"Created async engine (pool_size={settings.db_pool_size}, "
        f"max_overflow={settings.db_max_overflow}, "
        f"pool_timeout={settings.db_pool_timeout}s)"
    )
    return engine


async def get_pool_status() -> dict:
    """Get current connection pool status for monitoring.
    
    Returns:
        Dictionary with pool statistics
    """
    engine = get_async_engine()
    # Access the pool from the engine
    pool = engine.pool
    return {
        "size": pool.size(),
        "checked_in": pool.checkedin(),
        "checked_out": pool.checkedout(),
        "overflow": pool.overflow(),
    }


def get_async_session_maker() -> async_sessionmaker[AsyncSession]:
    """Get the async session maker.

    Returns:
        Async session maker configured with the async engine
    """
    global _AsyncSessionLocal
    if _AsyncSessionLocal is None:
        _AsyncSessionLocal = async_sessionmaker(
            bind=get_async_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _AsyncSessionLocal


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context manager for database sessions.

    Usage:
        async with get_async_session() as session:
            result = await session.execute(...)

    Yields:
        AsyncSession: Database session
    """
    session_maker = get_async_session_maker()
    async with session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


async def close_async_engine() -> None:
    """Close the async engine.

    Call this on application shutdown to release database connections.
    Handles event loop mismatches gracefully.
    """
    global _AsyncSessionLocal

    # Get cached engine and dispose it
    engine = get_async_engine()
    try:
        await engine.dispose()
        logger.debug("Async engine disposed successfully")
    except RuntimeError:
        # Event loop mismatch - connection already closed or different loop
        # This is safe to ignore in test scenarios
        logger.debug("Engine dispose encountered RuntimeError (event loop mismatch)")
        pass

    # Clear cache to allow recreation on next startup
    get_async_engine.cache_clear()
    _AsyncSessionLocal = None


async def init_async_db() -> None:
    """Initialize async database by creating all tables.

    This should be called during application startup.
    """
    from gateway.app.db.base import Base

    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def warmup_connection_pool(min_connections: int = 10) -> None:
    """Warm up the connection pool by pre-creating connections.

    This prevents connection storm during high traffic by pre-establishing
    a minimum number of connections before accepting traffic.

    Args:
        min_connections: Minimum number of connections to pre-create
    """
    engine = get_async_engine()
    logger.info(f"Warming up connection pool (target: {min_connections} connections)...")

    # Create connections concurrently
    async def ping_connection():
        try:
            async with engine.connect() as conn:
                from sqlalchemy import text
                await conn.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.warning(f"Failed to warm up connection: {e}")
            return False

    # Warm up connections in batches to avoid overwhelming the database
    batch_size = min(10, min_connections)
    successful = 0

    for i in range(0, min_connections, batch_size):
        batch_count = min(batch_size, min_connections - i)
        results = await asyncio.gather(*[ping_connection() for _ in range(batch_count)])
        successful += sum(results)
        logger.debug(f"Warmed up {successful}/{min_connections} connections...")
        # Small delay between batches
        if i + batch_size < min_connections:
            await asyncio.sleep(0.1)

    logger.info(f"Connection pool warmup complete: {successful}/{min_connections} connections ready")


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions.

    This function yields a database session that can be injected into
    route handlers and other dependencies. The session is automatically
    closed after the request is complete by the get_async_session()
    context manager.

    Transaction handling:
    - Successful requests: changes are automatically committed
    - Exceptions: changes are rolled back, exception is re-raised

    Usage:
        @app.get("/items")
        async def get_items(session: SessionDep):
            result = await session.execute(select(Item))
            return result.scalars().all()

    Yields:
        AsyncSession: Database session for the current request
    """
    async with get_async_session() as session:
        try:
            yield session
            # Commit successful transactions
            await session.commit()
        except Exception:
            # Rollback on any exception, then re-raise
            await session.rollback()
            raise
        finally:
            # Ensure session is closed
            await session.close()


# Type alias for FastAPI dependency injection
SessionDep = Annotated[AsyncSession, Depends(get_db)]
