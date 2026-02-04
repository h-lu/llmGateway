from fastapi import APIRouter, Query
from typing import Optional
from datetime import datetime
from admin.db_utils_v2 import get_conversations, get_conversation_count

router = APIRouter()


@router.get("")
async def list_conversations(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    student_id: Optional[str] = None,
    action: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> dict:
    """List conversations with pagination and filtering."""
    conversations = get_conversations(
        limit=limit,
        offset=offset,
        student_id=student_id,
        action=action,
        start_date=start_date,
        end_date=end_date
    )
    total = get_conversation_count(student_id=student_id, action=action)

    return {
        "items": conversations,
        "total": total,
        "limit": limit,
        "offset": offset
    }
