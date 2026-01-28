"""Rule engine with database loading and caching support.

This module provides a RuleService that loads rules from the database
with LRU caching, falling back to hardcoded rules if the database
is unavailable.
"""

import asyncio
import re
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from gateway.app.core.logging import get_logger
from gateway.app.db.crud import get_all_rules as get_all_rules_async
from gateway.app.db.models import Rule

logger = get_logger(__name__)


@dataclass
class RuleResult:
    """Result of evaluating a prompt against rules."""
    action: str  # blocked | guided | passed
    message: Optional[str] = None
    rule_id: Optional[str] = None


# Fallback hardcoded rules when database is unavailable
BLOCK_PATTERNS = [
    (r"写一个.+程序", "检测到你在直接要求代码。根据课程要求，请先尝试：\n1. 描述你想解决什么问题\n2. 说明你已经尝试了什么\n3. 具体哪里卡住了\n\n请重新组织你的问题 :)"),
    (r"帮我实现.+", "检测到你在直接要求代码。根据课程要求，请先尝试：\n1. 描述你想解决什么问题\n2. 说明你已经尝试了什么\n3. 具体哪里卡住了\n\n请重新组织你的问题 :)"),
    (r"生成.+代码", "检测到你在直接要求代码。根据课程要求，请先尝试：\n1. 描述你想解决什么问题\n2. 说明你已经尝试了什么\n3. 具体哪里卡住了\n\n请重新组织你的问题 :)"),
    (r"给我.+的代码", "检测到你在直接要求代码。根据课程要求，请先尝试：\n1. 描述你想解决什么问题\n2. 说明你已经尝试了什么\n3. 具体哪里卡住了\n\n请重新组织你的问题 :)"),
    (r"这道题的答案是什么", "检测到你在直接要求答案。根据课程要求，请先尝试：\n1. 描述你想解决什么问题\n2. 说明你已经尝试了什么\n3. 具体哪里卡住了\n\n请重新组织你的问题 :)"),
    (r"帮我做.+作业", "检测到你在直接要求代做作业。根据课程要求，请先尝试：\n1. 描述你想解决什么问题\n2. 说明你已经尝试了什么\n3. 具体哪里卡住了\n\n请重新组织你的问题 :)"),
]

GUIDE_PATTERNS = [
    (r"怎么.{2,5}$", "你的问题比较简短，能否补充更多背景？"),
    (r"解释.+", "在我解释之后，请尝试用自己的话复述一遍"),
]


def parse_week_range(active_weeks: str) -> Tuple[int, int]:
    """Parse active_weeks string like '1-2' or '3-6' into (start, end) tuple.
    
    Args:
        active_weeks: String in format "start-end" or single number
        
    Returns:
        Tuple of (start_week, end_week). For single number, start=end.
        
    Examples:
        >>> parse_week_range("1-2")
        (1, 2)
        >>> parse_week_range("3-6")
        (3, 6)
        >>> parse_week_range("5")
        (5, 5)
    """
    if not active_weeks:
        return (1, 99)  # Default: always active
    
    parts = active_weeks.split("-")
    if len(parts) == 1:
        week = int(parts[0].strip())
        return (week, week)
    else:
        start = int(parts[0].strip())
        end = int(parts[1].strip())
        return (start, end)


def is_week_in_range(week_number: int, week_range: str) -> bool:
    """Check if a week number falls within the specified range.
    
    Args:
        week_number: The current week number
        week_range: String in format "start-end" or single number
        
    Returns:
        True if week_number is within the range
    """
    start, end = parse_week_range(week_range)
    return start <= week_number <= end


class RuleService:
    """Service for loading and evaluating rules from database with caching.
    
    The service implements a two-tier caching strategy:
    1. In-memory cache with TTL (5 minutes)
    2. Fallback to hardcoded rules if database is unavailable
    
    Provides both sync and async interfaces for backward compatibility.
    
    Usage:
        service = RuleService()
        result = service.evaluate_prompt("帮我写代码", week_number=1)
    """
    
    # Cache TTL in seconds (5 minutes)
    CACHE_TTL = 300
    
    def __init__(self):
        self._cache: Optional[List[Rule]] = None
        self._cache_timestamp: float = 0
        self._use_hardcoded: bool = False
        self._compiled_patterns: Dict[int, re.Pattern] = {}
    
    def _is_cache_valid(self) -> bool:
        """Check if the current cache is still valid."""
        if self._cache is None:
            return False
        return (time.time() - self._cache_timestamp) < self.CACHE_TTL
    
    async def _load_rules_from_db_async(self) -> List[Rule]:
        """Load enabled rules from database asynchronously.
        
        Returns:
            List of Rule objects from database
            
        Raises:
            Exception: If database connection fails
        """
        return await get_all_rules_async(enabled_only=True)
    
    def _load_rules_from_db_sync(self) -> List[Rule]:
        """Load enabled rules from database synchronously."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Can't run async code in running loop from sync context
                return []
            return loop.run_until_complete(self._load_rules_from_db_async())
        except RuntimeError:
            return asyncio.run(self._load_rules_from_db_async())
    
    def _compile_patterns(self, rules: List[Rule]) -> None:
        """Compile regex patterns for all rules and cache them.
        
        Args:
            rules: List of Rule objects to compile patterns for
        """
        self._compiled_patterns.clear()
        for rule in rules:
            try:
                self._compiled_patterns[rule.id] = re.compile(rule.pattern)
            except re.error as e:
                logger.error(f"Failed to compile regex pattern for rule {rule.id}: {e}")
                # Skip invalid patterns - they won't match anything
    
    def reload_rules(self) -> None:
        """Force reload rules from database (sync version).
        
        Call this after modifying rules in the database to ensure
        changes take effect immediately.
        """
        try:
            self._cache = self._load_rules_from_db_sync()
            self._cache_timestamp = time.time()
            self._use_hardcoded = False
            self._compile_patterns(self._cache or [])
            logger.info("Rules reloaded successfully")
        except Exception as e:
            logger.error(f"Failed to reload rules from DB: {e}")
            if self._cache is None:
                self._use_hardcoded = True
            raise
    
    async def reload_rules_async(self) -> None:
        """Force reload rules from database (async version)."""
        try:
            self._cache = await self._load_rules_from_db_async()
            self._cache_timestamp = time.time()
            self._use_hardcoded = False
            self._compile_patterns(self._cache or [])
            logger.info("Rules reloaded successfully")
        except Exception as e:
            logger.error(f"Failed to reload rules from DB: {e}")
            if self._cache is None:
                self._use_hardcoded = True
            raise
    
    # Backward compatibility alias
    _async_reload = reload_rules_async
    
    def get_rules(self) -> List[Rule]:
        """Get current rules (from cache or database) - sync version.
        
        Returns:
            List of Rule objects
        """
        if self._is_cache_valid():
            return self._cache or []
        
        # If explicitly set to use hardcoded, skip DB load
        if self._use_hardcoded:
            return []
        
        try:
            self._cache = self._load_rules_from_db_sync()
            self._cache_timestamp = time.time()
            self._use_hardcoded = False
            self._compile_patterns(self._cache or [])
            return self._cache or []
        except Exception as e:
            logger.error(f"Failed to load rules from DB: {e}")
            # Fallback to empty list if DB fails and no cache
            return []
    
    async def get_rules_async(self) -> List[Rule]:
        """Get current rules (from cache or database) - async version.
        
        Returns:
            List of Rule objects
        """
        if self._is_cache_valid():
            return self._cache or []
        
        # If explicitly set to use hardcoded, skip DB load
        if self._use_hardcoded:
            return []
        
        try:
            self._cache = await self._load_rules_from_db_async()
            self._cache_timestamp = time.time()
            self._use_hardcoded = False
            self._compile_patterns(self._cache or [])
            return self._cache or []
        except Exception as e:
            logger.error(f"Failed to load rules from DB: {e}")
            # Fallback to empty list if DB fails and no cache
            return []
    
    def evaluate_prompt(self, prompt: str, week_number: int) -> RuleResult:
        """Evaluate a prompt against active rules (sync version).
        
        Rules are checked in order:
        1. Block rules from database (if enabled for current week)
        2. Guide rules from database (if enabled for current week)
        3. Fallback to hardcoded rules if DB fails
        
        Args:
            prompt: The user's prompt text
            week_number: Current academic week number
            
        Returns:
            RuleResult with action (blocked | guided | passed)
        """
        rules = self.get_rules()
        
        # If no DB rules, use hardcoded fallback
        if not rules:
            return self._evaluate_hardcoded(prompt, week_number)
        
        # Process database rules
        # First, check block rules
        for rule in rules:
            if rule.rule_type != "block":
                continue
            if not is_week_in_range(week_number, rule.active_weeks):
                continue
            if rule.id in self._compiled_patterns and self._compiled_patterns[rule.id].search(prompt):
                return RuleResult(
                    action="blocked",
                    message=rule.message,
                    rule_id=str(rule.id)
                )
        
        # Then, check guide rules
        for rule in rules:
            if rule.rule_type != "guide":
                continue
            if not is_week_in_range(week_number, rule.active_weeks):
                continue
            if rule.id in self._compiled_patterns and self._compiled_patterns[rule.id].search(prompt):
                return RuleResult(
                    action="guided",
                    message=rule.message,
                    rule_id=str(rule.id)
                )
        
        return RuleResult(action="passed")
    
    async def evaluate_prompt_async(self, prompt: str, week_number: int) -> RuleResult:
        """Evaluate a prompt against active rules (async version).
        
        Args:
            prompt: The user's prompt text
            week_number: Current academic week number
            
        Returns:
            RuleResult with action (blocked | guided | passed)
        """
        rules = await self.get_rules_async()
        
        # If no DB rules, use hardcoded fallback
        if not rules:
            return self._evaluate_hardcoded(prompt, week_number)
        
        # Process database rules
        # First, check block rules
        for rule in rules:
            if rule.rule_type != "block":
                continue
            if not is_week_in_range(week_number, rule.active_weeks):
                continue
            if rule.id in self._compiled_patterns and self._compiled_patterns[rule.id].search(prompt):
                return RuleResult(
                    action="blocked",
                    message=rule.message,
                    rule_id=str(rule.id)
                )
        
        # Then, check guide rules
        for rule in rules:
            if rule.rule_type != "guide":
                continue
            if not is_week_in_range(week_number, rule.active_weeks):
                continue
            if rule.id in self._compiled_patterns and self._compiled_patterns[rule.id].search(prompt):
                return RuleResult(
                    action="guided",
                    message=rule.message,
                    rule_id=str(rule.id)
                )
        
        return RuleResult(action="passed")
    
    def _evaluate_hardcoded(self, prompt: str, week_number: int) -> RuleResult:
        """Evaluate using hardcoded rules as fallback.
        
        This maintains backward compatibility when database rules
        are not available.
        """
        # Block patterns - active only in weeks 1-2 (original behavior)
        if week_number <= 2:
            for pattern, message in BLOCK_PATTERNS:
                if re.search(pattern, prompt):
                    return RuleResult(
                        action="blocked",
                        message=message,
                        rule_id=f"hardcoded:{pattern}"
                    )
        
        # Guide patterns - always active
        for pattern, message in GUIDE_PATTERNS:
            if re.search(pattern, prompt):
                return RuleResult(
                    action="guided",
                    message=message,
                    rule_id=f"hardcoded:{pattern}"
                )
        
        return RuleResult(action="passed")


# Global instance for convenience
_default_service: Optional[RuleService] = None


def get_rule_service() -> RuleService:
    """Get the default RuleService instance (singleton pattern)."""
    global _default_service
    if _default_service is None:
        _default_service = RuleService()
    return _default_service


def evaluate_prompt(prompt: str, week_number: int) -> RuleResult:
    """Convenience function to evaluate a prompt using the default service.
    
    This maintains backward compatibility with the old API (sync version).
    
    Args:
        prompt: The user's prompt text
        week_number: Current academic week number
        
    Returns:
        RuleResult with action (blocked | guided | passed)
    """
    service = get_rule_service()
    return service.evaluate_prompt(prompt, week_number)


async def evaluate_prompt_async(prompt: str, week_number: int) -> RuleResult:
    """Convenience function to evaluate a prompt using the default service (async).
    
    Args:
        prompt: The user's prompt text
        week_number: Current academic week number
        
    Returns:
        RuleResult with action (blocked | guided | passed)
    """
    service = get_rule_service()
    return await service.evaluate_prompt_async(prompt, week_number)


def reload_rules() -> None:
    """Force reload rules from database (sync version).
    
    Call this function after modifying rules to ensure changes
    take effect immediately.
    """
    service = get_rule_service()
    service.reload_rules()


async def reload_rules_async() -> None:
    """Force reload rules from database (async version)."""
    service = get_rule_service()
    await service.reload_rules_async()
