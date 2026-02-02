"""Quota CRUD operations."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.app.db.models import QuotaLog, Student


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


async def create_quota_log(
    session: AsyncSession,
    student_id: str,
    week_number: int,
    tokens_granted: int,
    tokens_used: int,
    auto_commit: bool = True
) -> QuotaLog:
    """Create a quota log entry.
    
    Args:
        session: Database session from FastAPI dependency
        student_id: The student ID
        week_number: The academic week number
        tokens_granted: Tokens granted for the week
        tokens_used: Tokens actually used
        auto_commit: Whether to commit the transaction. Set to False
                     if you want to control transaction boundaries manually.
        
    Returns:
        The created QuotaLog object
    """
    log = QuotaLog(
        student_id=student_id,
        week_number=week_number,
        tokens_granted=tokens_granted,
        tokens_used=tokens_used,
        reset_at=datetime.now()
    )
    session.add(log)
    if auto_commit:
        await session.commit()
        await session.refresh(log)
    return log


async def get_quota_logs_by_student(
    session: AsyncSession,
    student_id: str
) -> list[QuotaLog]:
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
