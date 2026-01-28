"""Rules engine for evaluating prompts.

This module provides backward compatibility by re-exporting from rule_service.
New code should import from gateway.app.services.rule_service directly.

Note: The hardcoded patterns below are deprecated in favor of database rules
but are kept as fallback when database is unavailable.
"""

# Re-export from new rule_service module for backward compatibility
from gateway.app.services.rule_service import (
    BLOCK_PATTERNS,
    GUIDE_PATTERNS,
    RuleResult,
    RuleService,
    evaluate_prompt,
    get_rule_service,
    is_week_in_range,
    parse_week_range,
    reload_rules,
)

# Backward compatibility: maintain old hardcoded patterns
BLOCK_MESSAGE = (
    "检测到你在直接要求代码。根据课程要求，请先尝试：\n"
    "1. 描述你想解决什么问题\n"
    "2. 说明你已经尝试了什么\n"
    "3. 具体哪里卡住了\n\n"
    "请重新组织你的问题 :)"
)


__all__ = [
    "RuleResult",
    "RuleService",
    "evaluate_prompt",
    "get_rule_service",
    "reload_rules",
    "parse_week_range",
    "is_week_in_range",
    # Backward compatibility exports
    "BLOCK_PATTERNS",
    "GUIDE_PATTERNS",
    "BLOCK_MESSAGE",
]
