from fastapi import APIRouter
from typing import Any
from admin.db_utils_v2 import get_dashboard_stats, get_recent_activity

router = APIRouter()


@router.get("/stats")
async def dashboard_stats() -> dict[str, Any]:
    """Get dashboard statistics."""
    return get_dashboard_stats()


@router.get("/activity")
async def dashboard_activity(days: int = 7) -> list[dict[str, Any]]:
    """Get recent activity for charts."""
    return get_recent_activity(days=days)
