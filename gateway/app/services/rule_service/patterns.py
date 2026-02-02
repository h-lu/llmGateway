"""Rule patterns and utilities."""
import re
from typing import Dict, List, Tuple, Optional, Any
from gateway.app.core.logging import get_logger

logger = get_logger(__name__)

# Hardcoded rule patterns
BLOCK_PATTERNS: List[Tuple[str, str]] = [
    (r"密码|password|secret|key.*=", "不得询问敏感信息"),
    (r"攻击|hack|exploit|injection", "不得涉及攻击行为"),
]

GUIDE_PATTERNS: List[Tuple[str, str]] = [
    (r"直接给答案|直接告诉我|给我代码", "请引导思考而非直接给答案"),
    (r"帮我写|帮我做|帮我完成", "建议先尝试自己完成"),
]


def parse_week_range(week_range_str: Optional[str]) -> Tuple[int, int]:
    """Parse week range string.
    
    Args:
        week_range_str: Format "1-16" or "1" or "1,3,5"
        
    Returns:
        (start_week, end_week) tuple
    """
    if not week_range_str:
        return (1, 16)
    
    try:
        if "-" in week_range_str:
            parts = week_range_str.split("-")
            return (int(parts[0]), int(parts[1]))
        elif "," in week_range_str:
            weeks = [int(w.strip()) for w in week_range_str.split(",")]
            return (min(weeks), max(weeks))
        else:
            week = int(week_range_str)
            return (week, week)
    except (ValueError, IndexError) as e:
        logger.warning(f"Invalid week range '{week_range_str}': {e}")
        return (1, 16)


def is_week_in_range(current_week: int, week_range_str: Optional[str]) -> bool:
    """Check if current week is in range."""
    start, end = parse_week_range(week_range_str)
    return start <= current_week <= end
