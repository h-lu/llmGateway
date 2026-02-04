from fastapi import APIRouter, Depends
from gateway.app.middleware.auth import require_admin

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

# Sub-routers will be included here
from . import students, conversations, rules, weekly_prompts, dashboard

router.include_router(students.router, prefix="/students", tags=["admin-students"])
router.include_router(conversations.router, prefix="/conversations", tags=["admin-conversations"])
router.include_router(rules.router, prefix="/rules", tags=["admin-rules"])
router.include_router(weekly_prompts.router, prefix="/weekly-prompts", tags=["admin-weekly-prompts"])
router.include_router(dashboard.router, prefix="/dashboard", tags=["admin-dashboard"])
