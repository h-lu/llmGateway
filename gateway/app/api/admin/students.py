from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from admin.db_utils_v2 import (
    get_all_students,
    create_student,
    get_student_by_id,
    update_student_quota,
    reset_student_quota,
    regenerate_student_api_key,
    delete_student,
    get_student_quota_stats,
)

router = APIRouter()


class StudentCreate(BaseModel):
    name: str
    email: str
    quota: int = 10000


class StudentUpdateQuota(BaseModel):
    quota: int


class StudentResponse(BaseModel):
    id: str
    name: str
    email: str
    current_week_quota: int
    used_quota: int
    created_at: Optional[str]


@router.get("")
async def list_students() -> list[dict]:
    """List all students."""
    return get_all_students()


@router.post("")
async def create_new_student(data: StudentCreate) -> dict:
    """Create a new student."""
    student, api_key = create_student(
        name=data.name, email=data.email, quota=data.quota
    )
    return {"student": student, "api_key": api_key}


@router.get("/{student_id}")
async def get_student(student_id: str) -> dict:
    """Get student by ID."""
    student = get_student_by_id(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student


@router.put("/{student_id}/quota")
async def update_quota(student_id: str, data: StudentUpdateQuota) -> dict:
    """Update student quota."""
    success = update_student_quota(student_id, data.quota)
    if not success:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"success": True}


@router.post("/{student_id}/reset-quota")
async def reset_quota(student_id: str) -> dict:
    """Reset student used quota."""
    success = reset_student_quota(student_id)
    if not success:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"success": True}


@router.post("/{student_id}/regenerate-key")
async def regen_key(student_id: str) -> dict:
    """Regenerate API key."""
    new_key = regenerate_student_api_key(student_id)
    if not new_key:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"api_key": new_key}


@router.delete("/{student_id}")
async def remove_student(student_id: str) -> dict:
    """Delete student."""
    success = delete_student(student_id)
    if not success:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"success": True}


@router.get("/{student_id}/stats")
async def student_stats(student_id: str) -> dict:
    """Get student quota statistics."""
    stats = get_student_quota_stats(student_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Student not found")
    return stats
