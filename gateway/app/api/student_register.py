"""Public student self-registration endpoint.

This is designed to remove the need for teachers to manually create and
distribute per-student API keys. Instead, teachers share a single course
registration code (STUDENT_REGISTRATION_CODE), and students self-register
to receive their own API key.
"""

from __future__ import annotations

import hmac
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError

from gateway.app.core.config import settings
from gateway.app.core.security import generate_api_key, hash_api_key
from gateway.app.db.dependencies import SessionDep
from gateway.app.db.models import Student

router = APIRouter(prefix="/v1/student", tags=["student"])


class StudentRegisterRequest(BaseModel):
    registration_code: str = Field(..., min_length=1, max_length=256)
    name: str = Field(..., min_length=1, max_length=200)
    email: str = Field(..., min_length=3, max_length=320)

    @field_validator("registration_code")
    @classmethod
    def normalize_registration_code(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("registration_code cannot be empty")
        return v

    @field_validator("name")
    @classmethod
    def normalize_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name cannot be empty")
        return v

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        v = v.strip().lower()
        # Lightweight validation without adding extra dependencies.
        if "@" not in v or v.startswith("@") or v.endswith("@"):
            raise ValueError("invalid email")
        return v


class StudentPublic(BaseModel):
    id: str
    name: str
    email: str
    created_at: datetime
    current_week_quota: int
    used_quota: int
    provider_type: str


class StudentRegisterResponse(BaseModel):
    student: StudentPublic
    api_key: str


@router.post(
    "/register",
    response_model=StudentRegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_student(
    data: StudentRegisterRequest,
    session: SessionDep,
) -> StudentRegisterResponse:
    """Self-register a student and return a new API key.

    Security:
    - Disabled by default unless STUDENT_REGISTRATION_CODE is set.
    - Does not allow re-issuing keys for existing emails (prevents hijacking).
    """
    expected_code = settings.student_registration_code
    if not expected_code:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student self-registration is disabled",
        )

    if not hmac.compare_digest(data.registration_code, expected_code):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid registration code",
        )

    api_key = generate_api_key()
    api_key_hash = hash_api_key(api_key)

    student = Student(
        id=str(uuid.uuid4()),
        name=data.name,
        email=data.email,
        api_key_hash=api_key_hash,
        created_at=datetime.now(timezone.utc),
        current_week_quota=settings.student_self_register_default_quota,
        used_quota=0,
        provider_type="deepseek",
    )

    session.add(student)
    try:
        # Flush to surface unique/email conflicts before returning the API key.
        await session.flush()
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered. Please contact the teacher to reset your key.",
        )

    return StudentRegisterResponse(
        student=StudentPublic(
            id=student.id,
            name=student.name,
            email=student.email,
            created_at=student.created_at,
            current_week_quota=student.current_week_quota,
            used_quota=student.used_quota,
            provider_type=student.provider_type,
        ),
        api_key=api_key,
    )
