"""Distributed quota management using Redis for multi-instance deployments.

This package provides atomic quota operations using Redis Lua scripts,
with fallback to database when Redis is unavailable.
"""

# Re-export DB functions for backward compatibility (tests mock these)
from gateway.app.db.crud import check_and_consume_quota, update_student_quota, get_student_by_id

from .models import DistributedQuotaState
from .redis_lua import CHECK_AND_CONSUME_SCRIPT
from .service import (
    DistributedQuotaService,
    get_distributed_quota_service,
    reset_distributed_quota_service,
)

__all__ = [
    "DistributedQuotaState",
    "CHECK_AND_CONSUME_SCRIPT",
    "DistributedQuotaService",
    "get_distributed_quota_service",
    "reset_distributed_quota_service",
    # DB functions for backward compatibility
    "check_and_consume_quota",
    "update_student_quota",
    "get_student_by_id",
]
