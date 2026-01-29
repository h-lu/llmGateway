"""Database dependencies for FastAPI dependency injection.

This module provides FastAPI dependencies for database session management,
following the FastAPI best practices for dependency injection.

Usage:
    from fastapi import Depends
    from gateway.app.db.dependencies import SessionDep
    
    @app.get("/items")
    async def get_items(session: SessionDep):
        result = await session.execute(select(Item))
        return result.scalars().all()
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.app.db.async_session import get_db

# Type alias for FastAPI dependency injection
# Usage: async def handler(session: SessionDep)
SessionDep = Annotated[AsyncSession, Depends(get_db)]

__all__ = ["SessionDep"]
