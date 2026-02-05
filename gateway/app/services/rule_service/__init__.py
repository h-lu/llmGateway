"""Rule service package.

Refactored package structure splitting the original 716-line rule_service.py into:
- models.py: Data models
- patterns.py: Rule patterns and utilities
- regex_utils.py: Regex utilities
- hardcoded_rules.py: Hardcoded rules
- service.py: Main service class
"""

from gateway.app.services.rule_service.models import RuleResult
from gateway.app.services.rule_service.patterns import (
    BLOCK_PATTERNS,
    GUIDE_PATTERNS,
    parse_week_range,
    is_week_in_range,
)
from gateway.app.services.rule_service.regex_utils import (
    _regex_search_with_timeout,
    REGEX_TIMEOUT_SECONDS,
    cleanup_regex_executor,
)
from gateway.app.services.rule_service.service import (
    RuleService,
    get_rule_service,
    evaluate_prompt,
    evaluate_prompt_async,
    reload_rules,
    reload_rules_async,
)
from gateway.app.db.crud import get_all_rules as get_all_rules_async

__all__ = [
    "RuleResult",
    "BLOCK_PATTERNS",
    "GUIDE_PATTERNS",
    "parse_week_range",
    "is_week_in_range",
    "_regex_search_with_timeout",
    "REGEX_TIMEOUT_SECONDS",
    "cleanup_regex_executor",
    "RuleService",
    "get_rule_service",
    "evaluate_prompt",
    "evaluate_prompt_async",
    "reload_rules",
    "reload_rules_async",
    "get_all_rules_async",
]
