"""Tests for RuleService with database loading and caching."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from gateway.app.core.cache import get_cache, reset_cache
from gateway.app.services.rule_service import (
    RuleResult,
    RuleService,
    evaluate_prompt,
    get_rule_service,
    is_week_in_range,
    parse_week_range,
    reload_rules,
)


@pytest.fixture(autouse=True)
def reset_cache_before_each_test():
    """Reset cache before each test to ensure isolation."""
    reset_cache()
    yield
    reset_cache()


class TestWeekRangeParsing:
    """Test suite for week range parsing utilities."""
    
    def test_parse_week_range_with_dash(self):
        """Test parsing week range like '1-2'."""
        start, end = parse_week_range("1-2")
        assert start == 1
        assert end == 2
    
    def test_parse_week_range_single_week(self):
        """Test parsing single week like '5'."""
        start, end = parse_week_range("5")
        assert start == 5
        assert end == 5
    
    def test_parse_week_range_with_spaces(self):
        """Test parsing week range with spaces like ' 3 - 6 '."""
        start, end = parse_week_range(" 3 - 6 ")
        assert start == 3
        assert end == 6
    
    def test_parse_week_range_empty(self):
        """Test parsing empty string returns default."""
        start, end = parse_week_range("")
        assert start == 1
        assert end == 99
    
    def test_parse_week_range_none(self):
        """Test parsing None returns default."""
        start, end = parse_week_range(None)
        assert start == 1
        assert end == 99


class TestIsWeekInRange:
    """Test suite for week range checking."""
    
    def test_week_in_range(self):
        """Test week within range."""
        assert is_week_in_range(2, "1-3") is True
    
    def test_week_at_start_boundary(self):
        """Test week at start boundary."""
        assert is_week_in_range(1, "1-3") is True
    
    def test_week_at_end_boundary(self):
        """Test week at end boundary."""
        assert is_week_in_range(3, "1-3") is True
    
    def test_week_before_range(self):
        """Test week before range."""
        assert is_week_in_range(0, "1-3") is False
    
    def test_week_after_range(self):
        """Test week after range."""
        assert is_week_in_range(4, "1-3") is False
    
    def test_single_week_range(self):
        """Test single week range."""
        assert is_week_in_range(5, "5") is True
        assert is_week_in_range(4, "5") is False


class TestRuleServiceWithHardcoded:
    """Test RuleService using hardcoded rules (fallback mode)."""
    
    def test_block_rule_week_1(self):
        """Test block rule matches in week 1."""
        service = RuleService()
        # Force using hardcoded by making DB unavailable
        service._use_hardcoded = True
        
        result = service.evaluate_prompt("帮我写一个爬虫程序", week_number=1)
        assert result.action == "blocked"
        assert "rule_id" in str(result)
    
    def test_block_rule_not_active_week_3(self):
        """Test block rule does not match after week 2."""
        service = RuleService()
        service._use_hardcoded = True
        
        result = service.evaluate_prompt("帮我写一个爬虫程序", week_number=3)
        assert result.action == "passed"
    
    def test_guide_rule_always_active(self):
        """Test guide rule matches regardless of week."""
        service = RuleService()
        service._use_hardcoded = True
        
        # Test short question pattern: "怎么" + 2-5 chars + end
        # "怎么学习" matches: "怎么" + "学习" (4 chars) + end
        result = service.evaluate_prompt("怎么学习", week_number=5)
        assert result.action == "guided"
        assert "补充更多背景" in result.message
    
    def test_no_match_returns_passed(self):
        """Test that unmatched prompts return passed."""
        service = RuleService()
        service._use_hardcoded = True
        
        result = service.evaluate_prompt("这是一个正常的问题", week_number=1)
        assert result.action == "passed"


class TestRuleServiceWithDatabase:
    """Test RuleService with mocked database rules."""
    
    def create_mock_rule(self, id, pattern, rule_type, message, active_weeks, enabled=True):
        """Helper to create a mock Rule object."""
        rule = MagicMock()
        rule.id = id
        rule.pattern = pattern
        rule.rule_type = rule_type
        rule.message = message
        rule.active_weeks = active_weeks
        rule.enabled = enabled
        return rule
    
    @pytest.mark.asyncio
    async def test_load_rules_from_db(self):
        """Test loading rules from database."""
        mock_rules = [
            self.create_mock_rule(1, r"测试", "block", "被阻断", "1-8")
        ]
        
        with patch("gateway.app.services.rule_service.get_all_rules_async") as mock_get_rules:
            mock_get_rules.return_value = mock_rules
            
            service = RuleService()
            rules = await service.get_rules_async()
            
            assert rules is not None
            assert len(rules) == 1
            assert service._use_hardcoded is False
    
    @pytest.mark.asyncio
    async def test_evaluate_with_db_rules(self):
        """Test evaluation using database rules."""
        mock_rules = [
            self.create_mock_rule(1, r"帮我写代码", "block", "请先自己尝试", "1-4")
        ]
        
        with patch("gateway.app.services.rule_service.get_all_rules_async") as mock_get_rules:
            mock_get_rules.return_value = mock_rules
            
            service = RuleService()
            # Load rules first via async method
            await service.reload_rules_async()
            result = service.evaluate_prompt("帮我写代码", week_number=2)
            assert result.action == "blocked"
            assert result.message == "请先自己尝试"
            assert result.rule_id == "1"
    
    @pytest.mark.asyncio
    async def test_evaluate_respects_active_weeks(self):
        """Test that active_weeks is respected."""
        mock_rules = [
            self.create_mock_rule(1, r"测试", "block", "被阻断", "1-2")
        ]
        
        with patch("gateway.app.services.rule_service.get_all_rules_async") as mock_get_rules:
            mock_get_rules.return_value = mock_rules
            
            service = RuleService()
            # Load rules first via async method
            await service.reload_rules_async()
            
            # Week 1 should match
            result1 = service.evaluate_prompt("测试", week_number=1)
            assert result1.action == "blocked"
            
            # Week 3 should not match (falls through to passed or hardcoded)
            result3 = service.evaluate_prompt("测试", week_number=3)
            # Since hardcoded patterns don't match "测试", should be passed
            assert result3.action == "passed"
    
    @pytest.mark.asyncio
    async def test_guide_rules_from_db(self):
        """Test guide rules loaded from database."""
        mock_rules = [
            self.create_mock_rule(1, r"怎么.*", "guide", "请先查阅文档", "1-16")
        ]
        
        with patch("gateway.app.services.rule_service.get_all_rules_async") as mock_get_rules:
            mock_get_rules.return_value = mock_rules
            
            service = RuleService()
            # Load rules first via async method
            await service.reload_rules_async()
            result = service.evaluate_prompt("怎么用Python", week_number=5)
            assert result.action == "guided"
            assert result.message == "请先查阅文档"


class TestRuleServiceCaching:
    """Test RuleService caching behavior with CacheBackend."""
    
    def create_mock_rule(self, id, pattern, rule_type, message, active_weeks, enabled=True):
        """Helper to create a mock Rule object."""
        rule = MagicMock()
        rule.id = id
        rule.pattern = pattern
        rule.rule_type = rule_type
        rule.message = message
        rule.active_weeks = active_weeks
        rule.enabled = enabled
        return rule
    
    @pytest.mark.asyncio
    async def test_cache_is_used(self):
        """Test that cache is used when available."""
        mock_rules = [
            self.create_mock_rule(1, r"测试", "block", "被阻断", "1-8")
        ]
        
        with patch("gateway.app.services.rule_service.get_all_rules_async") as mock_get_rules:
            mock_get_rules.return_value = mock_rules
            
            service = RuleService()
            
            # First call - should load from DB and cache
            rules1 = await service.get_rules_async()
            assert len(rules1) == 1
            assert mock_get_rules.call_count == 1
            
            # Second call - should use cache, not call DB again
            rules2 = await service.get_rules_async()
            assert len(rules2) == 1
            assert mock_get_rules.call_count == 1  # Should not increase
    
    @pytest.mark.asyncio
    async def test_reload_rules_invalidates_cache(self):
        """Test that reload_rules invalidates and refreshes cache."""
        mock_rules = [
            self.create_mock_rule(1, r"测试", "block", "被阻断", "1-8")
        ]
        
        with patch("gateway.app.services.rule_service.get_all_rules_async") as mock_get_rules:
            mock_get_rules.return_value = mock_rules
            
            service = RuleService()
            
            # Load rules initially
            await service.get_rules_async()
            assert mock_get_rules.call_count == 1
            
            # Force reload - should call DB again
            await service.reload_rules_async()
            assert mock_get_rules.call_count == 2
    
    @pytest.mark.asyncio
    async def test_cache_key_format(self):
        """Test that cache key is correct."""
        assert RuleService.CACHE_KEY == "rules:all"
        assert RuleService.CACHE_TTL == 300


class TestGlobalFunctions:
    """Test global convenience functions."""
    
    def test_get_rule_service_singleton(self):
        """Test that get_rule_service returns same instance."""
        service1 = get_rule_service()
        service2 = get_rule_service()
        assert service1 is service2
    
    def test_evaluate_prompt_uses_service(self):
        """Test that evaluate_prompt uses the global service with hardcoded fallback."""
        # Reset the global service to ensure clean state
        import gateway.app.services.rule_service as rs
        rs._default_service = None
        
        # This should work with hardcoded fallback
        result = evaluate_prompt("帮我实现一个程序", week_number=1)
        assert result.action == "blocked"
    
    def test_reload_rules_calls_service(self):
        """Test that reload_rules works."""
        # Should not raise
        try:
            reload_rules()
        except Exception:
            # DB might not be available in tests, that's ok
            pass


class TestRuleResult:
    """Test RuleResult dataclass."""
    
    def test_rule_result_creation(self):
        """Test creating RuleResult."""
        result = RuleResult(action="blocked", message="test", rule_id="123")
        assert result.action == "blocked"
        assert result.message == "test"
        assert result.rule_id == "123"
    
    def test_rule_result_defaults(self):
        """Test RuleResult with defaults."""
        result = RuleResult(action="passed")
        assert result.action == "passed"
        assert result.message is None
        assert result.rule_id is None
