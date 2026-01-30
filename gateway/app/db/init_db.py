"""Database initialization utilities."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from gateway.app.db.async_session import get_async_engine
from gateway.app.db.base import Base


async def drop_all_tables(engine: AsyncEngine | None = None) -> None:
    """Drop all database tables.

    WARNING: This will delete all data. Use only in development.
    """
    if engine is None:
        engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def create_all_tables(engine: AsyncEngine | None = None) -> None:
    """Create all database tables."""
    if engine is None:
        engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def init_database(drop_first: bool = True) -> None:
    """Initialize database with all tables.

    Args:
        drop_first: If True, drop existing tables before creating.
    """
    if drop_first:
        await drop_all_tables()
    await create_all_tables()


async def verify_connection() -> bool:
    """Verify database connection is working.

    Returns:
        True if connection successful, False otherwise.
    """
    try:
        engine = get_async_engine()
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception as e:
        print(f"Database connection failed: {e}")
        return False
