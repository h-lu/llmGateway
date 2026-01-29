"""Services package for the gateway.

This package provides:
- Quota management (sync and async, with caching and distributed support)
- Rule engine for content filtering
- Async conversation logging
"""

from gateway.app.services.quota import QuotaState, apply_usage
from gateway.app.services.quota_cache import (
    QuotaCacheService,
    QuotaCacheState,
    get_quota_cache_service,
    reset_quota_cache_service,
)
from gateway.app.services.distributed_quota import (
    DistributedQuotaService,
    DistributedQuotaState,
    get_distributed_quota_service,
    reset_distributed_quota_service,
)
from gateway.app.services.rule_service import (
    BLOCK_PATTERNS,
    GUIDE_PATTERNS,
    RuleResult,
    RuleService,
    evaluate_prompt,
    evaluate_prompt_async,
    get_rule_service,
    is_week_in_range,
    parse_week_range,
    reload_rules,
    reload_rules_async,
)
from gateway.app.services.async_logger import (
    AsyncConversationLogger,
    ConversationLogData,
    LogBufferEntry,
    async_logger,
    get_async_logger,
)
from gateway.app.services.conversation import save_conversation
from gateway.app.services.weekly_prompt_service import (
    WeeklyPromptService,
    get_and_inject_weekly_prompt,
    get_weekly_prompt_service,
    inject_weekly_system_prompt,
    reset_weekly_prompt_service,
)

__all__ = [
    # Quota (basic)
    "QuotaState",
    "apply_usage",
    # Quota Cache
    "QuotaCacheService",
    "QuotaCacheState",
    "get_quota_cache_service",
    "reset_quota_cache_service",
    # Distributed Quota
    "DistributedQuotaService",
    "DistributedQuotaState",
    "get_distributed_quota_service",
    "reset_distributed_quota_service",
    # Rule Service
    "BLOCK_PATTERNS",
    "GUIDE_PATTERNS",
    "RuleResult",
    "RuleService",
    "evaluate_prompt",
    "evaluate_prompt_async",
    "get_rule_service",
    "is_week_in_range",
    "parse_week_range",
    "reload_rules",
    "reload_rules_async",
    # Async Logger
    "AsyncConversationLogger",
    "ConversationLogData",
    "LogBufferEntry",
    "async_logger",
    "get_async_logger",
    # Conversation
    "save_conversation",
    # Weekly Prompt Service
    "WeeklyPromptService",
    "get_weekly_prompt_service",
    "reset_weekly_prompt_service",
    "inject_weekly_system_prompt",
    "get_and_inject_weekly_prompt",
]
