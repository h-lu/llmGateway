from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from admin.db_utils_v2 import (
    get_all_rules,
    create_rule,
    update_rule,
    delete_rule,
    toggle_rule_enabled,
)
from gateway.app.services.rule_service import reload_rules

router = APIRouter()


class RuleCreate(BaseModel):
    pattern: str
    rule_type: str  # "block" or "guide"
    message: str
    active_weeks: str = "1-16"
    enabled: bool = True


class RuleUpdate(BaseModel):
    pattern: Optional[str] = None
    rule_type: Optional[str] = None
    message: Optional[str] = None
    active_weeks: Optional[str] = None
    enabled: Optional[bool] = None


@router.get("")
async def list_rules() -> list[dict]:
    """List all custom rules."""
    return get_all_rules()


@router.post("")
async def create_new_rule(data: RuleCreate) -> dict:
    """Create a new rule."""
    rule = create_rule(**data.dict())
    return rule


@router.put("/{rule_id}")
async def update_existing_rule(rule_id: int, data: RuleUpdate) -> dict:
    """Update a rule."""
    success = update_rule(
        rule_id, **{k: v for k, v in data.dict().items() if v is not None}
    )
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"success": True}


@router.delete("/{rule_id}")
async def remove_rule(rule_id: int) -> dict:
    """Delete a rule."""
    success = delete_rule(rule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"success": True}


@router.post("/{rule_id}/toggle")
async def toggle_rule(rule_id: int) -> dict:
    """Toggle rule enabled state."""
    enabled = toggle_rule_enabled(rule_id)
    if enabled is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"enabled": enabled}


@router.post("/reload-cache")
async def reload_rules_cache() -> dict:
    """Reload rules cache."""
    reload_rules()
    return {"success": True}
