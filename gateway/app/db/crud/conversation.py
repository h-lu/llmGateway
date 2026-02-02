"""Conversation CRUD operations."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.app.db.models import Conversation


async def save_conversation(
    session: AsyncSession,
    student_id: str,
    prompt: str,
    response: str,
    tokens_used: int,
    action: str,
    rule_triggered: Optional[str],
    week_number: int,
    auto_commit: bool = True
) -> Conversation:
    """Save a conversation record to the database.
    
    Args:
        session: Database session from FastAPI dependency
        student_id: The student ID
        prompt: The user's prompt text
        response: The AI response text
        tokens_used: Number of tokens used
        action: Action taken (blocked | guided | passed)
        rule_triggered: ID of the rule that was triggered, if any
        week_number: The academic week number
        auto_commit: Whether to commit the transaction. Set to False
                     if you want to control transaction boundaries manually.
        
    Returns:
        The saved Conversation object
    """
    conversation = Conversation(
        student_id=student_id,
        timestamp=datetime.now(),
        prompt_text=prompt,
        response_text=response,
        tokens_used=tokens_used,
        rule_triggered=rule_triggered,
        action_taken=action,
        week_number=week_number,
    )
    session.add(conversation)
    if auto_commit:
        await session.commit()
        await session.refresh(conversation)
    return conversation


async def save_conversation_bulk(
    session: AsyncSession,
    conversations: List[Conversation],
    auto_commit: bool = True
) -> int:
    """Save multiple conversation records to the database in bulk.
    
    This function performs an efficient bulk insert using SQLAlchemy's
    session.add_all() method, which is more performant than inserting
    records one at a time.
    
    Args:
        session: Database session from FastAPI dependency
        conversations: List of Conversation objects to save
        auto_commit: Whether to commit the transaction. Set to False
                     if you want to control transaction boundaries manually.
        
    Returns:
        Number of conversations saved
    """
    if not conversations:
        return 0
    
    session.add_all(conversations)
    if auto_commit:
        await session.commit()
    return len(conversations)


async def get_conversations_by_student(
    session: AsyncSession,
    student_id: str,
    limit: int = 100
) -> List[Conversation]:
    """Get conversations for a specific student.
    
    Args:
        session: Database session from FastAPI dependency
        student_id: The student ID
        limit: Maximum number of conversations to return
        
    Returns:
        List of conversations
    """
    result = await session.execute(
        select(Conversation)
        .where(Conversation.student_id == student_id)
        .order_by(Conversation.timestamp.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_recent_conversations(
    session: AsyncSession,
    limit: int = 100
) -> List[Conversation]:
    """Get recent conversations across all students.
    
    Args:
        session: Database session from FastAPI dependency
        limit: Maximum number of conversations to return
        
    Returns:
        List of recent conversations
    """
    result = await session.execute(
        select(Conversation)
        .order_by(Conversation.timestamp.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
