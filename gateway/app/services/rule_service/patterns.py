"""Rule patterns and utilities."""

from __future__ import annotations

from gateway.app.core.logging import get_logger

logger = get_logger(__name__)

# Hardcoded rule patterns - matching original rule_service.py behavior
BLOCK_PATTERNS: list[tuple[str, str]] = [
    (
        r"写一个.+程序",
        "检测到你在直接要求代码。根据课程要求，请先尝试：\n1. 描述你想解决什么问题\n2. 说明你已经尝试了什么\n3. 具体哪里卡住了\n\n请重新组织你的问题 :)",
    ),
    (
        r"帮我实现.+",
        "检测到你在直接要求代码。根据课程要求，请先尝试：\n1. 描述你想解决什么问题\n2. 说明你已经尝试了什么\n3. 具体哪里卡住了\n\n请重新组织你的问题 :)",
    ),
    (
        r"生成.+代码",
        "检测到你在直接要求代码。根据课程要求，请先尝试：\n1. 描述你想解决什么问题\n2. 说明你已经尝试了什么\n3. 具体哪里卡住了\n\n请重新组织你的问题 :)",
    ),
    (
        r"给我.+的代码",
        "检测到你在直接要求代码。根据课程要求，请先尝试：\n1. 描述你想解决什么问题\n2. 说明你已经尝试了什么\n3. 具体哪里卡住了\n\n请重新组织你的问题 :)",
    ),
    (
        r"这道题的答案是什么",
        "检测到你在直接要求答案。根据课程要求，请先尝试：\n1. 描述你想解决什么问题\n2. 说明你已经尝试了什么\n3. 具体哪里卡住了\n\n请重新组织你的问题 :)",
    ),
    (
        r"帮我做.+作业",
        "检测到你在直接要求代做作业。根据课程要求，请先尝试：\n1. 描述你想解决什么问题\n2. 说明你已经尝试了什么\n3. 具体哪里卡住了\n\n请重新组织你的问题 :)",
    ),
]

GUIDE_PATTERNS: list[tuple[str, str]] = [
    (r"怎么.{2,5}$", "你的问题比较简短，能否补充更多背景？"),
    (r"解释.+", "在我解释之后，请尝试用自己的话复述一遍"),
]


def parse_week_range(week_range_str: str | None) -> tuple[int, int]:
    """Parse week range string.

    Args:
        week_range_str: Format "1-16" or "1" or "1,3,5"

    Returns:
        (start_week, end_week) tuple
    """
    if not week_range_str:
        return (1, 99)

    # Strip whitespace from the input
    week_range_str = week_range_str.strip()

    try:
        if "-" in week_range_str:
            parts = week_range_str.split("-")
            return (int(parts[0].strip()), int(parts[1].strip()))
        elif "," in week_range_str:
            weeks = [int(w.strip()) for w in week_range_str.split(",")]
            return (min(weeks), max(weeks))
        else:
            week = int(week_range_str)
            return (week, week)
    except (ValueError, IndexError) as e:
        logger.warning(f"Invalid week range '{week_range_str}': {e}")
        return (1, 99)


def is_week_in_range(current_week: int, week_range_str: str | None) -> bool:
    """Check if current week is in range."""
    start, end = parse_week_range(week_range_str)
    return start <= current_week <= end
