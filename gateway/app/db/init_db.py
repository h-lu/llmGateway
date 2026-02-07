"""Database initialization utilities."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from gateway.app.db.async_session import get_async_engine
from gateway.app.db.base import Base


async def ensure_students_schema(engine: AsyncEngine | None = None) -> None:
    """Ensure the `students` table schema is compatible with current models.

    `create_all()` does not add columns to existing tables. Production DBs can
    drift when models evolve. This function performs minimal additive changes
    (ADD COLUMN / CREATE INDEX) to keep admin operations working.
    """
    if engine is None:
        engine = get_async_engine()

    dialect = engine.dialect.name

    async with engine.begin() as conn:
        if dialect == "postgresql":
            # Add missing columns used by Balance Architecture features.
            await conn.execute(
                text(
                    "ALTER TABLE students "
                    "ADD COLUMN IF NOT EXISTS provider_api_key_encrypted VARCHAR(500)"
                )
            )
            await conn.execute(
                text(
                    "ALTER TABLE students "
                    "ADD COLUMN IF NOT EXISTS provider_type VARCHAR(50) "
                    "NOT NULL DEFAULT 'deepseek'"
                )
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_students_provider_key "
                    "ON students(provider_api_key_encrypted)"
                )
            )
            return

        if dialect == "sqlite":
            cols = {
                row[1]
                for row in (await conn.execute(text("PRAGMA table_info(students);"))).all()
            }
            if not cols:
                return
            if "provider_api_key_encrypted" not in cols:
                await conn.execute(
                    text(
                        "ALTER TABLE students "
                        "ADD COLUMN provider_api_key_encrypted VARCHAR(500)"
                    )
                )
            if "provider_type" not in cols:
                await conn.execute(
                    text(
                        "ALTER TABLE students "
                        "ADD COLUMN provider_type VARCHAR(50) "
                        "NOT NULL DEFAULT 'deepseek'"
                    )
                )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_students_provider_key "
                    "ON students(provider_api_key_encrypted)"
                )
            )
            return

        # Unknown dialect: do nothing.


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
