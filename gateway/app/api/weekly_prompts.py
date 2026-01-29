"""Admin API endpoints for managing weekly system prompts."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from gateway.app.db.dependencies import SessionDep
from gateway.app.db.models import WeeklySystemPrompt
from gateway.app.db.weekly_prompt_crud import (
    get_all_weekly_prompts,
    create_weekly_prompt,
    update_weekly_prompt,
    delete_weekly_prompt,
)
from gateway.app.services.weekly_prompt_service import get_weekly_prompt_service

router = APIRouter(prefix="/admin/weekly-prompts", tags=["admin"])


class WeeklyPromptCreate(BaseModel):
    """Schema for creating a weekly system prompt."""
    week_start: int = Field(..., ge=1, le=52, description="Start week (1-52)")
    week_end: int = Field(..., ge=1, le=52, description="End week (1-52)")
    system_prompt: str = Field(..., min_length=10, description="System prompt content")
    description: Optional[str] = Field(None, max_length=255, description="Optional description")
    
    @field_validator("week_end")
    @classmethod
    def validate_week_range(cls, week_end: int, info) -> int:
        week_start = info.data.get("week_start")
        if week_start is not None and week_end < week_start:
            raise ValueError("week_end must be >= week_start")
        return week_end


class WeeklyPromptUpdate(BaseModel):
    """Schema for updating a weekly system prompt."""
    week_start: Optional[int] = Field(None, ge=1, le=52)
    week_end: Optional[int] = Field(None, ge=1, le=52)
    system_prompt: Optional[str] = Field(None, min_length=10)
    description: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None


class WeeklyPromptResponse(BaseModel):
    """Schema for weekly prompt response."""
    id: int
    week_start: int
    week_end: int
    system_prompt: str
    description: Optional[str]
    is_active: bool
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True


@router.get("", response_model=List[WeeklyPromptResponse])
async def list_weekly_prompts(
    session: SessionDep,
    active_only: bool = False,
) -> List[WeeklySystemPrompt]:
    """List all weekly system prompts."""
    prompts = await get_all_weekly_prompts(session, active_only=active_only)
    return prompts


@router.post("", response_model=WeeklyPromptResponse, status_code=status.HTTP_201_CREATED)
async def create_prompt(
    data: WeeklyPromptCreate,
    session: SessionDep,
) -> WeeklySystemPrompt:
    """Create a new weekly system prompt."""
    prompt = await create_weekly_prompt(
        session=session,
        week_start=data.week_start,
        week_end=data.week_end,
        system_prompt=data.system_prompt,
        description=data.description,
    )
    
    # Invalidate cache so new prompt is used immediately
    get_weekly_prompt_service().invalidate_cache()
    
    return prompt


@router.put("/{prompt_id}", response_model=WeeklyPromptResponse)
async def update_prompt(
    prompt_id: int,
    data: WeeklyPromptUpdate,
    session: SessionDep,
) -> WeeklySystemPrompt:
    """Update a weekly system prompt."""
    update_data = data.model_dump(exclude_unset=True)
    
    prompt = await update_weekly_prompt(session, prompt_id, **update_data)
    
    if prompt is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Weekly prompt {prompt_id} not found"
        )
    
    # Invalidate cache
    get_weekly_prompt_service().invalidate_cache()
    
    return prompt


@router.delete("/{prompt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_prompt(
    prompt_id: int,
    session: SessionDep,
) -> None:
    """Deactivate (soft delete) a weekly system prompt."""
    success = await delete_weekly_prompt(session, prompt_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Weekly prompt {prompt_id} not found"
        )
    
    # Invalidate cache
    get_weekly_prompt_service().invalidate_cache()
