"""Student CRUD operations."""
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.app.db.models import Conversation, QuotaLog, Student


async def lookup_student_by_hash(
    session: AsyncSession,
    api_key_hash: str
) -> Optional[Student]:
    """Find a student by their API key hash.
    
    Args:
        session: Database session from FastAPI dependency
        api_key_hash: The hashed API key to look up
        
    Returns:
        Student object if found, None otherwise
    """
    result = await session.execute(
        select(Student).where(Student.api_key_hash == api_key_hash)
    )
    return result.scalar_one_or_none()


async def get_student_by_id(
    session: AsyncSession,
    student_id: str
) -> Optional[Student]:
    """Get a student by ID.
    
    Args:
        session: Database session from FastAPI dependency
        student_id: The student ID
        
    Returns:
        Student object if found, None otherwise
    """
    result = await session.execute(
        select(Student).where(Student.id == student_id)
    )
    return result.scalar_one_or_none()


async def list_students(session: AsyncSession) -> List[Student]:
    """Get all students.
    
    Args:
        session: Database session from FastAPI dependency
        
    Returns:
        List of all students
    """
    result = await session.execute(select(Student))
    return list(result.scalars().all())


async def update_student_quota(
    session: AsyncSession,
    student_id: str,
    tokens_used: int,
    auto_commit: bool = True
) -> tuple[bool, int, int]:
    """Update student's used_quota by adding tokens_used.
    
    Uses atomic UPDATE with RETURNING to avoid race conditions and
    return the actual updated values.
    
    Args:
        session: Database session from FastAPI dependency
        student_id: The student ID
        tokens_used: Number of tokens to add to used quota
        auto_commit: Whether to commit the transaction. Set to False
                     if you want to control transaction boundaries manually.
        
    Returns:
        Tuple of (success, remaining_quota, current_used)
        - success: True if updated successfully
        - remaining_quota: Remaining quota after update
        - current_used: Current used quota after update
    """
    # Use atomic UPDATE with RETURNING to avoid race conditions
    result = await session.execute(
        update(Student)
        .where(Student.id == student_id)
        .values(used_quota=Student.used_quota + tokens_used)
        .returning(Student.used_quota, Student.current_week_quota)
    )
    
    row = result.fetchone()
    
    if row is None:
        return False, 0, 0
    
    current_used, current_quota = row
    remaining = current_quota - current_used
    
    if auto_commit:
        await session.commit()
    
    return True, remaining, current_used


async def check_and_consume_quota(
    session: AsyncSession,
    student_id: str,
    tokens_needed: int,
    auto_commit: bool = True
) -> tuple[bool, int, int]:
    """Atomically check if student has enough quota and consume it.
    
    This function performs a truly atomic check-and-set operation using a
    single conditional UPDATE with RETURNING to prevent race conditions
    and get the actual updated values from the database.
    
    Args:
        session: Database session from FastAPI dependency
        student_id: The student ID
        tokens_needed: Number of tokens needed for the request
        auto_commit: Whether to commit the transaction. Set to False
                     if you want to control transaction boundaries manually.
        
    Returns:
        Tuple of (success, remaining_quota, current_used)
        - success: True if quota was sufficient and consumed
        - remaining_quota: Remaining quota after operation
        - current_used: Current used quota after operation (actual DB value)
    """
    # Perform atomic conditional UPDATE with RETURNING
    # This ensures we get the actual values after the update, preventing race conditions
    result = await session.execute(
        update(Student)
        .where(
            Student.id == student_id,
            Student.used_quota + tokens_needed <= Student.current_week_quota
        )
        .values(used_quota=Student.used_quota + tokens_needed)
        .returning(Student.used_quota, Student.current_week_quota)
    )
    
    row = result.fetchone()
    
    if row is None:
        # Update failed - either student doesn't exist or quota insufficient
        # Fetch current values to return accurate information
        result = await session.execute(
            select(Student.used_quota, Student.current_week_quota).where(Student.id == student_id)
        )
        row = result.fetchone()
        
        if row is None:
            # Student not found
            return False, 0, 0
        
        current_used, current_quota = row
        remaining = current_quota - current_used
        return False, remaining, current_used
    
    # Success - get actual values from RETURNING clause
    current_used, current_quota = row
    remaining = current_quota - current_used
    
    if auto_commit:
        await session.commit()
    
    return True, remaining, current_used


async def update_student_quota_bulk(
    session: AsyncSession,
    adjustments: Dict[str, int],
    auto_commit: bool = True
) -> int:
    """Update quotas for multiple students in bulk.
    
    This function applies quota adjustments for multiple students.
    Each key in the adjustments dict is a student_id, and the value
    is the adjustment amount (can be positive or negative).
    
    Note: This performs individual updates for each student to ensure
    atomicity and proper handling of concurrent modifications.
    
    Args:
        session: Database session from FastAPI dependency
        adjustments: Dict mapping student_id to quota adjustment amount
        auto_commit: Whether to commit the transaction. Set to False
                     if you want to control transaction boundaries manually.
        
    Returns:
        Number of students whose quotas were updated
    """
    if not adjustments:
        return 0
    
    updated_count = 0
    for student_id, adjustment in adjustments.items():
        result = await session.execute(
            update(Student)
            .where(Student.id == student_id)
            .values(used_quota=Student.used_quota + adjustment)
        )
        if result.rowcount > 0:
            updated_count += 1
    if auto_commit:
        await session.commit()
    return updated_count


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


async def get_quota_logs_by_student(
    session: AsyncSession,
    student_id: str
) -> List[QuotaLog]:
    """Get quota logs for a specific student.
    
    Args:
        session: Database session from FastAPI dependency
        student_id: The student ID
        
    Returns:
        List of quota logs
    """
    result = await session.execute(
        select(QuotaLog)
        .where(QuotaLog.student_id == student_id)
        .order_by(QuotaLog.week_number.desc())
    )
    return list(result.scalars().all())
