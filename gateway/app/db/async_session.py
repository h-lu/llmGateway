"""Async database session management for SQLAlchemy 2.0+.

This module provides async database operations, replacing the synchronous
session management for better performance in async applications.

SQLite Concurrency Optimizations:
- WAL (Write-Ahead Logging) mode for concurrent reads/writes
- StaticPool for single connection reuse
- busy_timeout for automatic lock retry
"""

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool, StaticPool
from typing_extensions import Annotated

from gateway.app.core.config import settings
from gateway.app.core.logging import get_logger

logger = get_logger(__name__)

# Global engine and session maker instances
_async_engine = None
_AsyncSessionLocal = None


def get_async_engine(database_url: str | None = None):
    """Get or create the async database engine.
    
    Args:
        database_url: Optional database URL. Uses settings if not provided.
        
    Returns:
        AsyncEngine instance
        
    Note:
        For SQLite, enables WAL mode and busy_timeout for better concurrency.
        Uses StaticPool to share a single connection across all requests.
    """
    global _async_engine
    if _async_engine is None:
        url = database_url or settings.database_url
        
        # Pool configuration
        pool_size = getattr(settings, 'db_pool_size', 10)
        max_overflow = getattr(settings, 'db_max_overflow', 20)
        pool_timeout = getattr(settings, 'db_pool_timeout', 30)
        pool_recycle = getattr(settings, 'db_pool_recycle', 3600)
        
        # Convert SQLite URL to async format if needed
        if url.startswith("sqlite+pysqlite://"):
            url = url.replace("sqlite+pysqlite://", "sqlite+aiosqlite://", 1)
        elif url.startswith("sqlite://") and not url.startswith("sqlite+aiosqlite://"):
            url = url.replace("sqlite://", "sqlite+aiosqlite://", 1)
        
        # SQLite concurrency optimizations
        if "sqlite" in url:
            _async_engine = create_async_engine(
                url,
                echo=False,
                future=True,
                poolclass=StaticPool,
                pool_pre_ping=True,  # Validate connections before use
                connect_args={
                    "check_same_thread": False,
                    "timeout": 30.0,  # Connection timeout
                },
            )
            
            # Enable WAL mode and busy_timeout for better concurrency
            @event.listens_for(_async_engine.sync_engine, "connect")
            def set_sqlite_pragma(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                # WAL mode: allows concurrent reads while writing
                cursor.execute("PRAGMA journal_mode = WAL")
                # busy_timeout: wait up to 30 seconds for locks
                cursor.execute("PRAGMA busy_timeout = 30000")
                # synchronous=NORMAL: good balance of safety/performance with WAL
                cursor.execute("PRAGMA synchronous = NORMAL")
                cursor.close()
            
            # Add slow query monitoring for performance observability
            @event.listens_for(_async_engine.sync_engine, "before_cursor_execute")
            def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
                context._query_start_time = time.time()
            
            @event.listens_for(_async_engine.sync_engine, "after_cursor_execute")
            def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
                total_time = time.time() - context._query_start_time
                if total_time > 1.0:  # Log queries taking more than 1 second
                    logger.warning(
                        "Slow query detected",
                        extra={
                            "query_time": round(total_time, 3),
                            "query": statement[:200] if len(statement) > 200 else statement,
                        }
                    )
                
        else:
            # PostgreSQL and other databases use standard connection pooling
            _async_engine = create_async_engine(
                url,
                echo=False,
                future=True,
                pool_size=pool_size,
                max_overflow=max_overflow,
                pool_timeout=pool_timeout,
                pool_recycle=pool_recycle,
                pool_pre_ping=True,  # Validate connections before use
            )
    return _async_engine


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
    """
    global _async_engine
    if _async_engine is not None:
        await _async_engine.dispose()
        _async_engine = None


async def init_async_db() -> None:
    """Initialize async database by creating all tables.
    
    This should be called during application startup.
    """
    from gateway.app.db.base import Base
    
    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


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
