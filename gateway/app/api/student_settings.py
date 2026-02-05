"""Student settings API for provider key configuration."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.app.core.security import encrypt_api_key
from gateway.app.db.dependencies import get_db
from gateway.app.db.models import Student
from gateway.app.middleware.auth import get_current_student

router = APIRouter(prefix="/student", tags=["student-settings"])


class KeySettingsResponse(BaseModel):
    """Key settings response."""

    has_own_key: bool
    provider_type: str
    masked_key: Optional[str] = None


class KeySettingsUpdate(BaseModel):
    """Update key settings request."""

    provider_type: str = Field(default="deepseek", pattern="^(deepseek|openrouter)$")
    api_key: str = Field(..., min_length=10)

    @field_validator("api_key")
    @classmethod
    def validate_api_key_format(cls, v: str) -> str:
        """Validate API key format."""
        if not v.startswith(("sk-", "sk-or-")):
            raise ValueError("API key must start with 'sk-' or 'sk-or-'")
        return v


class QuotaStatusResponse(BaseModel):
    """Quota status response."""

    current_week_quota: int
    used_quota: int
    remaining_quota: int
    week_number: int
    has_own_key: bool


@router.get("/settings", response_model=KeySettingsResponse)
async def get_settings(
    student: Student = Depends(get_current_student),
) -> KeySettingsResponse:
    """获取学生当前设置。"""
    masked = None
    if student.has_own_provider_key:
        # 只显示前4位和后4位
        key_preview = student.get_provider_api_key()
        if key_preview and len(key_preview) > 8:
            masked = f"{key_preview[:4]}...{key_preview[-4:]}"

    return KeySettingsResponse(
        has_own_key=student.has_own_provider_key,
        provider_type=student.provider_type,
        masked_key=masked,
    )


@router.post("/settings/key", status_code=status.HTTP_201_CREATED)
async def set_provider_key(
    settings: KeySettingsUpdate,
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """配置学生自己的 API Key。

    会先验证 Key 的有效性（调用 /models 测试）。
    """
    # 验证 Key 有效性
    base_url = {
        "deepseek": "https://api.deepseek.com/v1",
        "openrouter": "https://openrouter.ai/api/v1",
    }.get(settings.provider_type)

    try:
        client = AsyncOpenAI(
            api_key=settings.api_key,
            base_url=base_url,
            timeout=10.0,
        )
        # 尝试获取模型列表验证 key
        await client.models.list()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"API Key 验证失败: {str(e)}",
        )

    # 加密存储
    student.provider_api_key_encrypted = encrypt_api_key(settings.api_key)
    student.provider_type = settings.provider_type

    await db.commit()

    return {
        "message": "API Key 配置成功",
        "provider_type": settings.provider_type,
        "validated": True,
    }


@router.delete("/settings/key", status_code=status.HTTP_200_OK)
async def delete_provider_key(
    student: Student = Depends(get_current_student),
    db: AsyncSession = Depends(get_db),
):
    """删除学生自己的 API Key。"""
    student.provider_api_key_encrypted = None
    student.provider_type = "deepseek"

    await db.commit()

    return {
        "message": "API Key 已删除",
    }


@router.get("/quota", response_model=QuotaStatusResponse)
async def get_quota_status(
    student: Student = Depends(get_current_student),
) -> QuotaStatusResponse:
    """获取学生配额状态。"""
    from gateway.app.services.smart_router import get_current_week_number

    week_number = get_current_week_number()

    remaining = max(0, student.current_week_quota - student.used_quota)

    return QuotaStatusResponse(
        current_week_quota=student.current_week_quota,
        used_quota=student.used_quota,
        remaining_quota=remaining,
        week_number=week_number,
        has_own_key=student.has_own_provider_key,
    )
