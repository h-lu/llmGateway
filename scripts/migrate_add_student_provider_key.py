#!/usr/bin/env python3
"""Database migration: Add student provider key fields."""

import asyncio
import sys

from sqlalchemy import text

sys.path.insert(0, ".")

from gateway.app.db.session import engine


async def migrate():
    """Add provider_api_key_encrypted and provider_type columns."""
    async with engine.begin() as conn:
        # Check if columns exist
        result = await conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'students' AND column_name = 'provider_api_key_encrypted'
        """))
        
        if result.fetchone():
            print("Column provider_api_key_encrypted already exists, skipping...")
        else:
            await conn.execute(text("""
                ALTER TABLE students 
                ADD COLUMN provider_api_key_encrypted VARCHAR(500),
                ADD COLUMN provider_type VARCHAR(50) DEFAULT 'deepseek'
            """))
            print("Added provider_api_key_encrypted and provider_type columns")
        
        # Create index
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_students_provider_key 
            ON students(provider_api_key_encrypted)
        """))
        print("Created index idx_students_provider_key")
        
    print("Migration completed successfully!")


async def rollback():
    """Remove the added columns."""
    async with engine.begin() as conn:
        await conn.execute(text("""
            DROP INDEX IF EXISTS idx_students_provider_key
        """))
        await conn.execute(text("""
            ALTER TABLE students 
            DROP COLUMN IF EXISTS provider_api_key_encrypted,
            DROP COLUMN IF EXISTS provider_type
        """))
    print("Rollback completed!")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--rollback":
        asyncio.run(rollback())
    else:
        asyncio.run(migrate())
