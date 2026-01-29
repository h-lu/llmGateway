"""CRUD operations for WeeklySystemPrompt model."""

from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.app.db.models import WeeklySystemPrompt


async def get_active_prompt_for_week(
    session: AsyncSession, 
    week_number: int
) -> Optional[WeeklySystemPrompt]:
    """Get the active system prompt for a specific week.
    
    If multiple prompts cover this week, returns the one with the narrowest range
    (most specific match first).
    
    Args:
        session: Database session
        week_number: Current week number
        
    Returns:
        WeeklySystemPrompt if found, None otherwise
    """
    stmt = (
        select(WeeklySystemPrompt)
        .where(WeeklySystemPrompt.is_active == True)
        .where(WeeklySystemPrompt.week_start <= week_number)
        .where(WeeklySystemPrompt.week_end >= week_number)
        .order_by(
            # Prefer narrower ranges (more specific matches)
            (WeeklySystemPrompt.week_end - WeeklySystemPrompt.week_start).asc(),
            WeeklySystemPrompt.updated_at.desc()
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_all_weekly_prompts(
    session: AsyncSession,
    active_only: bool = False
) -> List[WeeklySystemPrompt]:
    """Get all weekly system prompts.
    
    Args:
        session: Database session
        active_only: If True, only return active prompts
        
    Returns:
        List of WeeklySystemPrompt objects
    """
    stmt = select(WeeklySystemPrompt)
    if active_only:
        stmt = stmt.where(WeeklySystemPrompt.is_active == True)
    stmt = stmt.order_by(WeeklySystemPrompt.week_start.asc())
    
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def create_weekly_prompt(
    session: AsyncSession,
    week_start: int,
    week_end: int,
    system_prompt: str,
    description: Optional[str] = None,
    auto_commit: bool = True
) -> WeeklySystemPrompt:
    """Create a new weekly system prompt.
    
    Args:
        session: Database session
        week_start: Start week number (inclusive)
        week_end: End week number (inclusive)
        system_prompt: The system prompt content
        description: Optional description
        auto_commit: Whether to commit the transaction
        
    Returns:
        Created WeeklySystemPrompt object
    """
    prompt = WeeklySystemPrompt(
        week_start=week_start,
        week_end=week_end,
        system_prompt=system_prompt,
        description=description,
        is_active=True,
    )
    session.add(prompt)
    if auto_commit:
        await session.commit()
        await session.refresh(prompt)
    return prompt


async def update_weekly_prompt(
    session: AsyncSession,
    prompt_id: int,
    auto_commit: bool = True,
    **kwargs
) -> Optional[WeeklySystemPrompt]:
    """Update a weekly system prompt.
    
    Args:
        session: Database session
        prompt_id: ID of the prompt to update
        auto_commit: Whether to commit the transaction
        **kwargs: Fields to update
        
    Returns:
        Updated WeeklySystemPrompt if found, None otherwise
    """
    stmt = select(WeeklySystemPrompt).where(WeeklySystemPrompt.id == prompt_id)
    result = await session.execute(stmt)
    prompt = result.scalar_one_or_none()
    
    if prompt is None:
        return None
    
    for key, value in kwargs.items():
        if hasattr(prompt, key):
            setattr(prompt, key, value)
    
    if auto_commit:
        await session.commit()
        await session.refresh(prompt)
    return prompt


async def delete_weekly_prompt(
    session: AsyncSession,
    prompt_id: int,
    auto_commit: bool = True
) -> bool:
    """Delete (soft delete by deactivating) a weekly system prompt.
    
    Args:
        session: Database session
        prompt_id: ID of the prompt to delete
        auto_commit: Whether to commit the transaction
        
    Returns:
        True if deleted, False if not found
    """
    stmt = select(WeeklySystemPrompt).where(WeeklySystemPrompt.id == prompt_id)
    result = await session.execute(stmt)
    prompt = result.scalar_one_or_none()
    
    if prompt is None:
        return False
    
    prompt.is_active = False
    if auto_commit:
        await session.commit()
    return True
