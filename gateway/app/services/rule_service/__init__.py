"""Rule service package."""
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

__all__ = [
    "RuleResult",
    "BLOCK_PATTERNS",
    "GUIDE_PATTERNS",
    "parse_week_range",
    "is_week_in_range",
    "_regex_search_with_timeout",
    "REGEX_TIMEOUT_SECONDS",
    "cleanup_regex_executor",
]
