"""Hardcoded rule evaluation logic."""
from __future__ import annotations

import re
import asyncio

from gateway.app.core.logging import get_logger
from gateway.app.services.rule_service.models import RuleResult
from gateway.app.services.rule_service.patterns import BLOCK_PATTERNS, GUIDE_PATTERNS
from gateway.app.services.rule_service.regex_utils import _regex_search_with_timeout

logger = get_logger(__name__)


async def evaluate_prompt_async(
    prompt: str,
    current_week: int,
    is_conceptual: bool = False,
) -> RuleResult:
    """Evaluate prompt content asynchronously.
    
    Args:
        prompt: User input prompt
        current_week: Current semester week number
        is_conceptual: Whether it's a conceptual question
        
    Returns:
        RuleResult evaluation result
    """
    text = prompt.lower()
    
    # Check block rules first
    for pattern_str, message in BLOCK_PATTERNS:
        try:
            pattern = re.compile(pattern_str, re.IGNORECASE)
            match = await _regex_search_with_timeout(pattern, text)
            if match:
                return RuleResult(
                    action="blocked",
                    message=message,
                    rule_id=f"hardcoded:{pattern_str}"
                )
        except re.error as e:
            logger.error(f"Invalid block pattern '{pattern_str}': {e}")
            continue
    
    # Then check guide rules
    for pattern_str, message in GUIDE_PATTERNS:
        try:
            pattern = re.compile(pattern_str, re.IGNORECASE)
            match = await _regex_search_with_timeout(pattern, text)
            if match:
                return RuleResult(
                    action="guided",
                    message=message,
                    rule_id=f"hardcoded:{pattern_str}"
                )
        except re.error as e:
            logger.error(f"Invalid guide pattern '{pattern_str}': {e}")
            continue
    
    return RuleResult(action="passed")


def evaluate_prompt(
    prompt: str,
    current_week: int,
    is_conceptual: bool = False,
) -> RuleResult:
    """Evaluate prompt content synchronously (for non-async contexts).
    
    Args:
        prompt: User input prompt
        current_week: Current semester week number
        is_conceptual: Whether it's a conceptual question
        
    Returns:
        RuleResult evaluation result
    """
    import concurrent.futures
    try:
        # Check if we're already in an event loop
        _ = asyncio.get_running_loop()
        # If we get here, we're in an async context - this is problematic
        # The caller should use evaluate_prompt_async instead
        logger.warning("evaluate_prompt called from async context, consider using evaluate_prompt_async")
        # Fallback: schedule in the running loop and wait (may block)
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, evaluate_prompt_async(prompt, current_week, is_conceptual))
            return future.result()
    except RuntimeError:
        # No running event loop, safe to use asyncio.run()
        return asyncio.run(evaluate_prompt_async(prompt, current_week, is_conceptual))
