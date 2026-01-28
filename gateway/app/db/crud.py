"""Async CRUD operations for database models.

This module provides async database operations for all models,
replacing the synchronous operations for better async performance.
"""

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from gateway.app.db.async_session import get_async_session
from gateway.app.db.models import Conversation, QuotaLog, Rule, Student


# =============================================================================
# Student Operations
# =============================================================================

async def lookup_student_by_hash(api_key_hash: str) -> Optional[Student]:
    """Find a student by their API key hash.
    
    Args:
        api_key_hash: The hashed API key to look up
        
    Returns:
        Student object if found, None otherwise
    """
    async with get_async_session() as session:
        result = await session.execute(
            select(Student).where(Student.api_key_hash == api_key_hash)
        )
        return result.scalar_one_or_none()


async def get_student_by_id(student_id: str) -> Optional[Student]:
    """Get a student by ID.
    
    Args:
        student_id: The student ID
        
    Returns:
        Student object if found, None otherwise
    """
    async with get_async_session() as session:
        result = await session.execute(
            select(Student).where(Student.id == student_id)
        )
        return result.scalar_one_or_none()


async def update_student_quota(student_id: str, tokens_used: int) -> bool:
    """Update student's used_quota by adding tokens_used.
    
    Uses atomic UPDATE to avoid race conditions.
    
    Args:
        student_id: The student ID
        tokens_used: Number of tokens to add to used quota
        
    Returns:
        True if updated successfully, False if student not found
    """
    async with get_async_session() as session:
        # Use atomic UPDATE to avoid race conditions
        result = await session.execute(
            update(Student)
            .where(Student.id == student_id)
            .values(used_quota=Student.used_quota + tokens_used)
        )
        await session.commit()
        return result.rowcount > 0


async def check_and_consume_quota(student_id: str, tokens_needed: int) -> tuple[bool, int, int]:
    """Atomically check if student has enough quota and consume it.
    
    This function performs an atomic check-and-set operation to prevent
    race conditions when multiple requests arrive simultaneously.
    
    Args:
        student_id: The student ID
        tokens_needed: Number of tokens needed for the request
        
    Returns:
        Tuple of (success, remaining_quota, current_used)
        - success: True if quota was sufficient and consumed
        - remaining_quota: Remaining quota after operation (can be negative if overdrawn)
        - current_used: Current used quota
    """
    async with get_async_session() as session:
        # Get current student data
        result = await session.execute(
            select(Student).where(Student.id == student_id)
        )
        student = result.scalar_one_or_none()
        
        if student is None:
            return False, 0, 0
        
        remaining = student.current_week_quota - student.used_quota
        
        if remaining <= 0:
            return False, remaining, student.used_quota
        
        # Atomically update used_quota
        await session.execute(
            update(Student)
            .where(Student.id == student_id)
            .values(used_quota=Student.used_quota + tokens_needed)
        )
        await session.commit()
        
        return True, remaining - tokens_needed, student.used_quota + tokens_needed


async def list_students() -> List[Student]:
    """Get all students.
    
    Returns:
        List of all students
    """
    async with get_async_session() as session:
        result = await session.execute(select(Student))
        return list(result.scalars().all())


# =============================================================================
# Conversation Operations
# =============================================================================

async def save_conversation(
    student_id: str,
    prompt: str,
    response: str,
    tokens_used: int,
    action: str,
    rule_triggered: Optional[str],
    week_number: int,
) -> Conversation:
    """Save a conversation record to the database.
    
    Args:
        student_id: The student ID
        prompt: The user's prompt text
        response: The AI response text
        tokens_used: Number of tokens used
        action: Action taken (blocked | guided | passed)
        rule_triggered: ID of the rule that was triggered, if any
        week_number: The academic week number
        
    Returns:
        The saved Conversation object
    """
    async with get_async_session() as session:
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
        await session.commit()
        await session.refresh(conversation)
        return conversation


async def save_conversation_bulk(conversations: List[Conversation]) -> int:
    """Save multiple conversation records to the database in bulk.
    
    This function performs an efficient bulk insert using SQLAlchemy's
    session.add_all() method, which is more performant than inserting
    records one at a time.
    
    Args:
        conversations: List of Conversation objects to save
        
    Returns:
        Number of conversations saved
    """
    if not conversations:
        return 0
    
    async with get_async_session() as session:
        session.add_all(conversations)
        await session.commit()
        return len(conversations)


async def update_student_quota_bulk(adjustments: Dict[str, int]) -> int:
    """Update quotas for multiple students in bulk.
    
    This function applies quota adjustments for multiple students.
    Each key in the adjustments dict is a student_id, and the value
    is the adjustment amount (can be positive or negative).
    
    Note: This performs individual updates for each student to ensure
    atomicity and proper handling of concurrent modifications.
    
    Args:
        adjustments: Dict mapping student_id to quota adjustment amount
        
    Returns:
        Number of students whose quotas were updated
    """
    if not adjustments:
        return 0
    
    updated_count = 0
    async with get_async_session() as session:
        for student_id, adjustment in adjustments.items():
            result = await session.execute(
                update(Student)
                .where(Student.id == student_id)
                .values(used_quota=Student.used_quota + adjustment)
            )
            if result.rowcount > 0:
                updated_count += 1
        await session.commit()
        return updated_count


async def get_conversations_by_student(
    student_id: str,
    limit: int = 100
) -> List[Conversation]:
    """Get conversations for a specific student.
    
    Args:
        student_id: The student ID
        limit: Maximum number of conversations to return
        
    Returns:
        List of conversations
    """
    async with get_async_session() as session:
        result = await session.execute(
            select(Conversation)
            .where(Conversation.student_id == student_id)
            .order_by(Conversation.timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


async def get_recent_conversations(limit: int = 100) -> List[Conversation]:
    """Get recent conversations across all students.
    
    Args:
        limit: Maximum number of conversations to return
        
    Returns:
        List of recent conversations
    """
    async with get_async_session() as session:
        result = await session.execute(
            select(Conversation)
            .order_by(Conversation.timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


# =============================================================================
# Rule Operations
# =============================================================================

async def get_all_rules(enabled_only: bool = False) -> List[Rule]:
    """Get all rules from the database.
    
    Args:
        enabled_only: If True, return only enabled rules
        
    Returns:
        List of rules
    """
    async with get_async_session() as session:
        query = select(Rule)
        if enabled_only:
            query = query.where(Rule.enabled == True)
        result = await session.execute(query)
        return list(result.scalars().all())


async def get_rule_by_id(rule_id: int) -> Optional[Rule]:
    """Get a rule by ID.
    
    Args:
        rule_id: The rule ID
        
    Returns:
        Rule object if found, None otherwise
    """
    async with get_async_session() as session:
        result = await session.execute(
            select(Rule).where(Rule.id == rule_id)
        )
        return result.scalar_one_or_none()


async def create_rule(
    pattern: str,
    rule_type: str,
    message: str,
    active_weeks: str = "1-16",
    enabled: bool = True
) -> Rule:
    """Create a new rule.
    
    Args:
        pattern: The regex pattern to match
        rule_type: Type of rule (block | guide)
        message: Message to return when rule matches
        active_weeks: Weeks when rule is active (e.g., "1-2" or "3-6")
        enabled: Whether the rule is enabled
        
    Returns:
        The created Rule object
    """
    async with get_async_session() as session:
        rule = Rule(
            pattern=pattern,
            rule_type=rule_type,
            message=message,
            active_weeks=active_weeks,
            enabled=enabled
        )
        session.add(rule)
        await session.commit()
        await session.refresh(rule)
        return rule


async def update_rule(rule_id: int, **kwargs) -> bool:
    """Update a rule by ID.
    
    Args:
        rule_id: The rule ID to update
        **kwargs: Fields to update
        
    Returns:
        True if updated successfully, False if rule not found
    """
    async with get_async_session() as session:
        result = await session.execute(
            select(Rule).where(Rule.id == rule_id)
        )
        rule = result.scalar_one_or_none()
        
        if rule is None:
            return False
        
        for key, value in kwargs.items():
            if hasattr(rule, key):
                setattr(rule, key, value)
        
        await session.commit()
        return True


async def delete_rule(rule_id: int) -> bool:
    """Delete a rule by ID.
    
    Args:
        rule_id: The rule ID to delete
        
    Returns:
        True if deleted successfully, False if rule not found
    """
    async with get_async_session() as session:
        result = await session.execute(
            select(Rule).where(Rule.id == rule_id)
        )
        rule = result.scalar_one_or_none()
        
        if rule is None:
            return False
        
        await session.delete(rule)
        await session.commit()
        return True


async def toggle_rule_enabled(rule_id: int) -> Optional[bool]:
    """Toggle the enabled status of a rule.
    
    Args:
        rule_id: The rule ID to toggle
        
    Returns:
        New enabled status (True/False), or None if rule not found
    """
    async with get_async_session() as session:
        result = await session.execute(
            select(Rule).where(Rule.id == rule_id)
        )
        rule = result.scalar_one_or_none()
        
        if rule is None:
            return None
        
        rule.enabled = not rule.enabled
        await session.commit()
        return rule.enabled


# =============================================================================
# QuotaLog Operations
# =============================================================================

async def create_quota_log(
    student_id: str,
    week_number: int,
    tokens_granted: int,
    tokens_used: int
) -> QuotaLog:
    """Create a quota log entry.
    
    Args:
        student_id: The student ID
        week_number: The academic week number
        tokens_granted: Tokens granted for the week
        tokens_used: Tokens actually used
        
    Returns:
        The created QuotaLog object
    """
    async with get_async_session() as session:
        log = QuotaLog(
            student_id=student_id,
            week_number=week_number,
            tokens_granted=tokens_granted,
            tokens_used=tokens_used,
            reset_at=datetime.now()
        )
        session.add(log)
        await session.commit()
        await session.refresh(log)
        return log


async def get_quota_logs_by_student(student_id: str) -> List[QuotaLog]:
    """Get quota logs for a specific student.
    
    Args:
        student_id: The student ID
        
    Returns:
        List of quota logs
    """
    async with get_async_session() as session:
        result = await session.execute(
            select(QuotaLog)
            .where(QuotaLog.student_id == student_id)
            .order_by(QuotaLog.week_number.desc())
        )
        return list(result.scalars().all())
