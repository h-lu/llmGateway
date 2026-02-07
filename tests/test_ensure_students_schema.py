import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


@pytest.mark.asyncio
async def test_ensure_students_schema_adds_missing_columns(tmp_path):
    # Create an old-style schema missing provider_* columns.
    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")

    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                CREATE TABLE students (
                  id VARCHAR PRIMARY KEY,
                  name VARCHAR NOT NULL,
                  email VARCHAR UNIQUE NOT NULL,
                  api_key_hash VARCHAR NOT NULL,
                  created_at DATETIME NOT NULL,
                  current_week_quota INTEGER NOT NULL,
                  used_quota INTEGER NOT NULL
                );
                """
            )
        )

    from gateway.app.db.init_db import ensure_students_schema

    await ensure_students_schema(engine=engine)

    async with engine.connect() as conn:
        rows = (await conn.execute(text("PRAGMA table_info(students);"))).all()
        cols = {row[1] for row in rows}

    assert "provider_api_key_encrypted" in cols
    assert "provider_type" in cols

    await engine.dispose()
