"""RuleService main class."""

from __future__ import annotations

import re

from sqlalchemy.ext.asyncio import AsyncSession
from gateway.app.core.cache import get_cache
from gateway.app.core.logging import get_logger
from gateway.app.db.models import Rule
from gateway.app.services.rule_service.models import RuleResult
from gateway.app.services.rule_service.patterns import (
    BLOCK_PATTERNS,
    GUIDE_PATTERNS,
    is_week_in_range,
)
from gateway.app.services.rule_service.regex_utils import _regex_search_with_timeout

logger = get_logger(__name__)


class RuleService:
    """Rule service - manages and evaluates rules."""

    CACHE_KEY = "rules:all"
    CACHE_TTL = 300

    def __init__(self, db: AsyncSession | None = None):
        self.db = db
        self._rules_cache: list[Rule] = []
        self._cache_valid = False
        self._use_hardcoded = False
        self._compiled_patterns: dict = {}

    async def get_rules_async(self) -> list[Rule]:
        """Get current rules (from cache or database) - async version.

        Returns:
            List of Rule objects
        """
        if self._use_hardcoded:
            return []

        if self._cache_valid and self._rules_cache:
            return self._rules_cache

        try:
            # Try to get from shared cache first
            cache = get_cache()
            cached_rules = await cache.get(self.CACHE_KEY)
            if cached_rules:
                self._rules_cache = cached_rules
                self._cache_valid = True
                self._compile_patterns(self._rules_cache)
                return self._rules_cache

            # Cache miss, load from DB
            # Import here to allow tests to patch at package level
            from gateway.app.services.rule_service import get_all_rules_async

            if self.db is not None:
                rules = await get_all_rules_async(self.db)
            else:
                # For test scenarios with mocked function
                rules = await get_all_rules_async()
            self._rules_cache = rules or []
            self._cache_valid = True
            self._use_hardcoded = False
            self._compile_patterns(self._rules_cache)

            # Update cache
            await cache.set(self.CACHE_KEY, self._rules_cache, ttl=self.CACHE_TTL)

            return self._rules_cache
        except Exception as e:
            logger.error(f"Failed to load rules from DB: {e}")
            return []

    def get_rules(self) -> list[Rule]:
        """Get current rules (from cache) - sync version.

        Note: This method returns cached rules if available.
        For fresh load from database, use get_rules_async.

        Returns:
            List of Rule objects
        """
        if self._use_hardcoded:
            return []

        if self._cache_valid and self._rules_cache:
            return self._rules_cache

        # Return empty list in sync context - rules should be loaded via async methods
        return []

    def _compile_patterns(self, rules: list[Rule]) -> None:
        """Compile regex patterns for rules."""
        self._compiled_patterns = {}
        for rule in rules:
            try:
                self._compiled_patterns[rule.id] = re.compile(rule.pattern)
            except re.error as e:
                logger.error(f"Invalid regex pattern for rule {rule.id}: {e}")

    async def reload_rules_async(self) -> None:
        """Force reload rules from database (async version)."""
        self._cache_valid = False
        self._use_hardcoded = False
        # Clear shared cache
        cache = get_cache()
        await cache.delete(self.CACHE_KEY)
        await self.get_rules_async()
        logger.info("Rules reloaded successfully")

    def reload_rules(self) -> None:
        """Force reload rules from database (sync version).

        Note: In async contexts, use reload_rules_async instead.
        """
        self._cache_valid = False
        self._use_hardcoded = False
        self._rules_cache = []
        logger.info(
            "Rules reload scheduled (use reload_rules_async for immediate effect)"
        )

    def evaluate_prompt(self, prompt: str, week_number: int) -> RuleResult:
        """Evaluate a prompt against active rules (sync version).

        Rules are checked in order:
        1. Block rules from database (if enabled for current week)
        2. Guide rules from database (if enabled for current week)
        3. Fallback to hardcoded rules if DB fails

        Note: Sync version does not have regex timeout protection.
        Use evaluate_prompt_async for production API calls with ReDoS protection.

        Args:
            prompt: The user's prompt text
            week_number: Current academic week number

        Returns:
            RuleResult with action (blocked | guided | passed)
        """
        # If using hardcoded rules, use them directly
        if self._use_hardcoded:
            return self._evaluate_hardcoded_sync(prompt, week_number)

        rules = self.get_rules()

        # If no DB rules, use hardcoded fallback
        if not rules:
            return self._evaluate_hardcoded_sync(prompt, week_number)

        # Process database rules
        # First, check block rules
        for rule in rules:
            if rule.rule_type != "block":
                continue
            if not is_week_in_range(week_number, rule.active_weeks):
                continue
            if rule.id in self._compiled_patterns:
                if self._compiled_patterns[rule.id].search(prompt):
                    return RuleResult(
                        action="blocked", message=rule.message, rule_id=str(rule.id)
                    )

        # Then, check guide rules
        for rule in rules:
            if rule.rule_type != "guide":
                continue
            if not is_week_in_range(week_number, rule.active_weeks):
                continue
            if rule.id in self._compiled_patterns:
                if self._compiled_patterns[rule.id].search(prompt):
                    return RuleResult(
                        action="guided", message=rule.message, rule_id=str(rule.id)
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
        # If using hardcoded rules, use them directly
        if self._use_hardcoded:
            return await self._evaluate_hardcoded_async(prompt, week_number)

        rules = await self.get_rules_async()

        # If no DB rules, use hardcoded fallback
        if not rules:
            return await self._evaluate_hardcoded_async(prompt, week_number)

        # Process database rules
        # First, check block rules
        for rule in rules:
            if rule.rule_type != "block":
                continue
            if not is_week_in_range(week_number, rule.active_weeks):
                continue
            if rule.id in self._compiled_patterns:
                match = await _regex_search_with_timeout(
                    self._compiled_patterns[rule.id], prompt
                )
                if match:
                    return RuleResult(
                        action="blocked", message=rule.message, rule_id=str(rule.id)
                    )

        # Then, check guide rules
        for rule in rules:
            if rule.rule_type != "guide":
                continue
            if not is_week_in_range(week_number, rule.active_weeks):
                continue
            if rule.id in self._compiled_patterns:
                match = await _regex_search_with_timeout(
                    self._compiled_patterns[rule.id], prompt
                )
                if match:
                    return RuleResult(
                        action="guided", message=rule.message, rule_id=str(rule.id)
                    )

        return RuleResult(action="passed")

    def _evaluate_hardcoded_sync(self, prompt: str, week_number: int) -> RuleResult:
        """Evaluate using hardcoded rules as fallback (sync version).

        This maintains backward compatibility when database rules
        are not available. Sync version does not have timeout protection.
        """
        # Block patterns - active only in weeks 1-2 (original behavior)
        if week_number <= 2:
            for pattern, message in BLOCK_PATTERNS:
                if re.search(pattern, prompt):
                    return RuleResult(
                        action="blocked",
                        message=message,
                        rule_id=f"hardcoded:{pattern}",
                    )

        # Guide patterns - always active
        for pattern, message in GUIDE_PATTERNS:
            if re.search(pattern, prompt):
                return RuleResult(
                    action="guided", message=message, rule_id=f"hardcoded:{pattern}"
                )

        return RuleResult(action="passed")

    async def _evaluate_hardcoded_async(
        self, prompt: str, week_number: int
    ) -> RuleResult:
        """Evaluate using hardcoded rules as fallback (async version with timeout).

        This version has ReDoS protection via regex timeout.
        """
        # Block patterns - active only in weeks 1-2 (original behavior)
        if week_number <= 2:
            for pattern, message in BLOCK_PATTERNS:
                compiled = re.compile(pattern)
                match = await _regex_search_with_timeout(compiled, prompt)
                if match:
                    return RuleResult(
                        action="blocked",
                        message=message,
                        rule_id=f"hardcoded:{pattern}",
                    )

        # Guide patterns - always active
        for pattern, message in GUIDE_PATTERNS:
            compiled = re.compile(pattern)
            match = await _regex_search_with_timeout(compiled, prompt)
            if match:
                return RuleResult(
                    action="guided", message=message, rule_id=f"hardcoded:{pattern}"
                )

        return RuleResult(action="passed")


# Global instance for convenience
_default_service: RuleService | None = None


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
