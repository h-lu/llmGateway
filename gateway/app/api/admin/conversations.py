from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from datetime import datetime
from admin.db_utils_v2 import (
    get_conversations, 
    get_conversation_count,
    get_conversations_by_student,
    search_conversations
)

router = APIRouter()


@router.get("/student/{student_id}")
async def get_student_conversations(
    student_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
) -> dict:
    """Get all conversations for a specific student."""
    conversations = get_conversations_by_student(
        student_id=student_id,
        limit=limit,
        offset=offset
    )
    total = get_conversation_count(student_id=student_id)
    
    return {
        "items": conversations,
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.get("/search")
async def search_conversations_endpoint(
    q: str = Query(..., min_length=1, description="Search query"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0)
) -> dict:
    """Search conversations by content (prompt or response)."""
    conversations = search_conversations(
        query=q,
        limit=limit,
        offset=offset
    )
    
    return {
        "items": conversations,
        "total": len(conversations),
        "limit": limit,
        "offset": offset,
        "query": q
    }


@router.get("")
async def list_conversations(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    student_id: Optional[str] = None,
    action: Optional[str] = None,
    search: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> dict:
    """List conversations with pagination, filtering and search."""
    
    # If search query provided, use search function
    if search:
        conversations = search_conversations(
            query=search,
            limit=limit,
            offset=offset,
            student_id=student_id,
            action=action
        )
        total = len(conversations)  # Search returns all matching, count them
    else:
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
