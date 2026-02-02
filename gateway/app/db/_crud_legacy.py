"""Async CRUD operations for database models.

This module provides async database operations for all models,
following FastAPI best practices by accepting session as a parameter
for proper dependency injection and transaction management.
"""

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.app.db.models import Conversation, QuotaLog, Rule, Student, WeeklySystemPrompt


# =============================================================================
# Student Operations
# =============================================================================

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


async def list_students(session: AsyncSession) -> List[Student]:
    """Get all students.
    
    Args:
        session: Database session from FastAPI dependency
        
    Returns:
        List of all students
    """
    result = await session.execute(select(Student))
    return list(result.scalars().all())


# =============================================================================
# Conversation Operations
# =============================================================================

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


# =============================================================================
# Rule Operations
# =============================================================================

async def get_all_rules(
    session: AsyncSession,
    enabled_only: bool = False
) -> List[Rule]:
    """Get all rules from the database.
    
    Args:
        session: Database session from FastAPI dependency
        enabled_only: If True, return only enabled rules
        
    Returns:
        List of rules
    """
    query = select(Rule)
    if enabled_only:
        query = query.where(Rule.enabled == True)
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_rule_by_id(
    session: AsyncSession,
    rule_id: int
) -> Optional[Rule]:
    """Get a rule by ID.
    
    Args:
        session: Database session from FastAPI dependency
        rule_id: The rule ID
        
    Returns:
        Rule object if found, None otherwise
    """
    result = await session.execute(
        select(Rule).where(Rule.id == rule_id)
    )
    return result.scalar_one_or_none()


async def create_rule(
    session: AsyncSession,
    pattern: str,
    rule_type: str,
    message: str,
    active_weeks: str = "1-16",
    enabled: bool = True,
    auto_commit: bool = True
) -> Rule:
    """Create a new rule.
    
    Args:
        session: Database session from FastAPI dependency
        pattern: The regex pattern to match
        rule_type: Type of rule (block | guide)
        message: Message to return when rule matches
        active_weeks: Weeks when rule is active (e.g., "1-2" or "3-6")
        enabled: Whether the rule is enabled
        auto_commit: Whether to commit the transaction. Set to False
                     if you want to control transaction boundaries manually.
        
    Returns:
        The created Rule object
    """
    rule = Rule(
        pattern=pattern,
        rule_type=rule_type,
        message=message,
        active_weeks=active_weeks,
        enabled=enabled
    )
    session.add(rule)
    if auto_commit:
        await session.commit()
        await session.refresh(rule)
    return rule


async def update_rule(
    session: AsyncSession,
    rule_id: int, 
    auto_commit: bool = True,
    **kwargs
) -> bool:
    """Update a rule by ID.
    
    Args:
        session: Database session from FastAPI dependency
        rule_id: The rule ID to update
        auto_commit: Whether to commit the transaction. Set to False
                     if you want to control transaction boundaries manually.
        **kwargs: Fields to update
        
    Returns:
        True if updated successfully, False if rule not found
    """
    result = await session.execute(
        select(Rule).where(Rule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    
    if rule is None:
        return False
    
    for key, value in kwargs.items():
        if hasattr(rule, key):
            setattr(rule, key, value)
    
    if auto_commit:
        await session.commit()
    return True


async def delete_rule(
    session: AsyncSession,
    rule_id: int,
    auto_commit: bool = True
) -> bool:
    """Delete a rule by ID.
    
    Args:
        session: Database session from FastAPI dependency
        rule_id: The rule ID to delete
        auto_commit: Whether to commit the transaction. Set to False
                     if you want to control transaction boundaries manually.
        
    Returns:
        True if deleted successfully, False if rule not found
    """
    result = await session.execute(
        select(Rule).where(Rule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    
    if rule is None:
        return False
    
    await session.delete(rule)
    if auto_commit:
        await session.commit()
    return True


async def toggle_rule_enabled(
    session: AsyncSession,
    rule_id: int,
    auto_commit: bool = True
) -> Optional[bool]:
    """Toggle the enabled status of a rule.
    
    Args:
        session: Database session from FastAPI dependency
        rule_id: The rule ID to toggle
        auto_commit: Whether to commit the transaction. Set to False
                     if you want to control transaction boundaries manually.
        
    Returns:
        New enabled status (True/False), or None if rule not found
    """
    result = await session.execute(
        select(Rule).where(Rule.id == rule_id)
    )
    rule = result.scalar_one_or_none()
    
    if rule is None:
        return None
    
    rule.enabled = not rule.enabled
    if auto_commit:
        await session.commit()
    return rule.enabled


# =============================================================================
# QuotaLog Operations
# =============================================================================

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


# =============================================================================
# WeeklySystemPrompt Operations (re-exported from weekly_prompt_crud)
# =============================================================================

from gateway.app.db.weekly_prompt_crud import (
    get_active_prompt_for_week,
    get_all_weekly_prompts,
    create_weekly_prompt,
    update_weekly_prompt,
    delete_weekly_prompt,
)
