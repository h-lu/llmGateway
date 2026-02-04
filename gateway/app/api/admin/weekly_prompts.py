from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from admin.db_utils_v2 import (
    get_all_weekly_prompts, get_prompt_by_week,
    get_current_week_prompt, create_or_update_weekly_prompt,
    delete_weekly_prompt
)

router = APIRouter()


class WeeklyPromptCreate(BaseModel):
    week_start: int
    week_end: int
    system_prompt: str
    description: Optional[str] = None
    is_active: bool = True


@router.get("")
async def list_prompts() -> list[dict]:
    """List all weekly prompts."""
    return get_all_weekly_prompts()


@router.get("/current")
async def get_current() -> Optional[dict]:
    """Get current week prompt."""
    return get_current_week_prompt()


@router.get("/week/{week_number}")
async def get_by_week(week_number: int) -> Optional[dict]:
    """Get prompt for specific week."""
    return get_prompt_by_week(week_number)


@router.post("")
async def create_or_update(data: WeeklyPromptCreate) -> dict:
    """Create or update weekly prompt."""
    prompt = create_or_update_weekly_prompt(**data.dict())
    return prompt


@router.delete("/{prompt_id}")
async def remove_prompt(prompt_id: int) -> dict:
    """Delete weekly prompt."""
    success = delete_weekly_prompt(prompt_id)
    if not success:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return {"success": True}
