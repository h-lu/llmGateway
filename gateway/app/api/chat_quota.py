"""Quota checking and reservation utilities for chat API."""

from gateway.app.db.models import Student
from gateway.app.exceptions import QuotaExceededError
from gateway.app.services.quota_cache import get_quota_cache_service


# Backward compatibility: old function name (sync version for tests)
def check_student_quota(student: Student, week_number: int) -> int:
    """Check if student has remaining quota (backward compatibility).
    
    Args:
        student: The student to check
        week_number: Current week number
        
    Returns:
        Remaining token quota
        
    Raises:
        QuotaExceededError: If student has no remaining quota
    """
    remaining = student.current_week_quota - student.used_quota
    
    if remaining <= 0:
        raise QuotaExceededError(
            remaining=remaining,
            reset_week=week_number + 1,
            detail=f"Weekly token quota exceeded. "
                   f"Quota: {student.current_week_quota}, "
                   f"Used: {student.used_quota}, "
                   f"Remaining: {remaining}"
        )
    
    return remaining


async def check_and_reserve_quota(
    student: Student, 
    week_number: int, 
    estimated_tokens: int = 1000,
    session = None,
) -> int:
    """Check if student has remaining quota and reserve estimated tokens.
    
    First checks cache for quota state, falls back to database on miss
    or insufficient quota. Uses optimistic locking for cache updates.
    
    Args:
        student: The student to check
        week_number: Current week number
        estimated_tokens: Estimated tokens to reserve
        session: Database session for transaction consistency (optional)
        
    Returns:
        Remaining token quota after reservation
        
    Raises:
        QuotaExceededError: If student has no remaining quota
    """
    quota_service = get_quota_cache_service()
    success, remaining, used = await quota_service.check_and_reserve_quota(
        student_id=student.id,
        week_number=week_number,
        current_week_quota=student.current_week_quota,
        tokens_needed=estimated_tokens,
        session=session,
    )
    
    if not success:
        raise QuotaExceededError(
            remaining=remaining,
            reset_week=week_number + 1,
            detail=f"Weekly token quota exceeded. "
                   f"Quota: {student.current_week_quota}, "
                   f"Used: {used}, "
                   f"Remaining: {remaining}"
        )
    
    return remaining
