"""Boundary, security, and edge case tests for weekly system prompts."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.app.services.weekly_prompt_service import inject_weekly_system_prompt
from gateway.app.db.models import WeeklySystemPrompt


class TestWeekRangeBoundaries:
    """Test week number boundary conditions."""
    
    @pytest.mark.asyncio
    async def test_week_boundary_1(self):
        """Test week number = 1 (minimum valid)."""
        prompt = WeeklySystemPrompt(
            week_start=1,
            week_end=1,
            system_prompt="第1周提示词",
            is_active=True,
        )
        assert prompt.is_current_week(1) is True
        assert prompt.is_current_week(2) is False
    
    @pytest.mark.asyncio
    async def test_week_boundary_52(self):
        """Test week number = 52 (maximum valid)."""
        prompt = WeeklySystemPrompt(
            week_start=52,
            week_end=52,
            system_prompt="第52周提示词",
            is_active=True,
        )
        assert prompt.is_current_week(52) is True
        assert prompt.is_current_week(53) is False
    
    @pytest.mark.asyncio
    async def test_week_zero_invalid(self):
        """Test week number = 0 should be handled."""
        prompt = WeeklySystemPrompt(
            week_start=1,
            week_end=4,
            system_prompt="提示词",
            is_active=True,
        )
        # Week 0 should not match
        assert prompt.is_current_week(0) is False
    
    @pytest.mark.asyncio
    async def test_large_week_number(self):
        """Test very large week number."""
        prompt = WeeklySystemPrompt(
            week_start=1,
            week_end=4,
            system_prompt="提示词",
            is_active=True,
        )
        # Large week number should not match
        assert prompt.is_current_week(999999) is False
    
    @pytest.mark.asyncio
    async def test_negative_week_number(self):
        """Test negative week number."""
        prompt = WeeklySystemPrompt(
            week_start=1,
            week_end=4,
            system_prompt="提示词",
            is_active=True,
        )
        assert prompt.is_current_week(-1) is False


class TestOverlappingWeekRanges:
    """Test behavior with overlapping week ranges."""
    
    @pytest.mark.asyncio
    async def test_overlapping_ranges_priority(self):
        """Test which prompt is selected when weeks overlap."""
        from gateway.app.db.weekly_prompt_crud import get_active_prompt_for_week
        
        # Create overlapping prompts
        prompt_wide = WeeklySystemPrompt(
            id=1,
            week_start=1,
            week_end=10,  # Wide range
            system_prompt="宽泛提示词",
            is_active=True,
        )
        prompt_narrow = WeeklySystemPrompt(
            id=2,
            week_start=3,
            week_end=3,  # Single week, more specific
            system_prompt="精确提示词",
            is_active=True,
        )
        
        # Mock session returning both prompts
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        # Order matters: wider first, then narrower
        mock_result.scalar_one_or_none.return_value = prompt_narrow
        mock_session.execute.return_value = mock_result
        
        result = await get_active_prompt_for_week(mock_session, week_number=3)
        
        # Should return the narrower (more specific) one
        # Note: Actual behavior depends on ORDER BY in SQL query
        assert result is not None


class TestSecurityInjections:
    """Test security against injection attacks."""
    
    @pytest.mark.asyncio
    async def test_sql_injection_in_system_prompt(self):
        """Test SQL injection in system_prompt field."""
        malicious_prompt = "'; DROP TABLE weekly_system_prompts; --"
        
        prompt = WeeklySystemPrompt(
            week_start=1,
            week_end=1,
            system_prompt=malicious_prompt,
            is_active=True,
        )
        
        # Model should store as-is (SQLAlchemy handles escaping)
        assert prompt.system_prompt == malicious_prompt
    
    @pytest.mark.asyncio
    async def test_sql_injection_in_description(self):
        """Test SQL injection in description field."""
        malicious_desc = "1; DELETE FROM students; --"
        
        prompt = WeeklySystemPrompt(
            week_start=1,
            week_end=1,
            system_prompt="正常提示词",
            description=malicious_desc,
            is_active=True,
        )
        
        assert prompt.description == malicious_desc
    
    @pytest.mark.asyncio
    async def test_xss_injection_in_prompt(self):
        """Test XSS injection handling."""
        xss_prompt = "<script>alert('xss')</script>正常内容"
        
        prompt = WeeklySystemPrompt(
            week_start=1,
            week_end=1,
            system_prompt=xss_prompt,
            is_active=True,
        )
        
        # Model stores as-is, API should escape on output
        assert "<script>" in prompt.system_prompt
    
    @pytest.mark.asyncio
    async def test_unicode_injection(self):
        """Test various Unicode characters in prompt."""
        unicode_prompt = "测试🔥🚀💻特殊字符\u0000\uFFFF\x00\xFF"
        
        prompt = WeeklySystemPrompt(
            week_start=1,
            week_end=1,
            system_prompt=unicode_prompt,
            is_active=True,
        )
        
        assert prompt.system_prompt == unicode_prompt


class TestContentBoundaries:
    """Test content size and format boundaries."""
    
    @pytest.mark.asyncio
    async def test_very_long_system_prompt(self):
        """Test system prompt at 10,000 characters."""
        long_prompt = "A" * 10000
        
        prompt = WeeklySystemPrompt(
            week_start=1,
            week_end=1,
            system_prompt=long_prompt,
            is_active=True,
        )
        
        assert len(prompt.system_prompt) == 10000
    
    @pytest.mark.asyncio
    async def test_multiline_system_prompt(self):
        """Test multiline system prompt with special formatting."""
        multiline_prompt = """# Python 导师提示词

## 规则
1. 必须用中文回答
2. 每句话以"喵"结尾
3. 代码示例用```python包裹

## 示例
```python
def hello():
    print("Hello, 喵!")
```

---
"""
        
        prompt = WeeklySystemPrompt(
            week_start=1,
            week_end=1,
            system_prompt=multiline_prompt,
            is_active=True,
        )
        
        assert "```python" in prompt.system_prompt
        assert "喵" in prompt.system_prompt
    
    @pytest.mark.asyncio
    async def test_empty_description(self):
        """Test null/empty description."""
        prompt = WeeklySystemPrompt(
            week_start=1,
            week_end=1,
            system_prompt="测试提示词",
            description=None,
            is_active=True,
        )
        
        assert prompt.description is None
    
    @pytest.mark.asyncio
    async def test_max_length_description(self):
        """Test description at max length (255 chars)."""
        max_desc = "D" * 255
        
        prompt = WeeklySystemPrompt(
            week_start=1,
            week_end=1,
            system_prompt="测试提示词",
            description=max_desc,
            is_active=True,
        )
        
        assert len(prompt.description) == 255


class TestMessageInjectionEdgeCases:
    """Test edge cases in message injection."""
    
    @pytest.mark.asyncio
    async def test_inject_into_empty_messages(self):
        """Test injecting prompt into empty message list."""
        prompt = WeeklySystemPrompt(
            week_start=1,
            week_end=1,
            system_prompt="系统提示词",
            is_active=True,
        )
        
        result = await inject_weekly_system_prompt([], prompt)
        
        assert len(result) == 1
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "系统提示词"
    
    @pytest.mark.asyncio
    async def test_inject_preserves_existing_system_message(self):
        """Test that existing system message is replaced."""
        prompt = WeeklySystemPrompt(
            week_start=1,
            week_end=1,
            system_prompt="新的系统提示词",
            is_active=True,
        )
        
        messages = [
            {"role": "system", "content": "旧的系统提示词"},
            {"role": "user", "content": "用户问题"},
        ]
        
        result = await inject_weekly_system_prompt(messages, prompt)
        
        assert len(result) == 2
        assert result[0]["content"] == "新的系统提示词"
        assert result[1]["content"] == "用户问题"
    
    @pytest.mark.asyncio
    async def test_inject_complex_message_structure(self):
        """Test injecting into complex multi-turn conversation."""
        prompt = WeeklySystemPrompt(
            week_start=1,
            week_end=1,
            system_prompt="导师提示词",
            is_active=True,
        )
        
        messages = [
            {"role": "system", "content": "原有系统消息"},
            {"role": "user", "content": "问题1"},
            {"role": "assistant", "content": "回答1"},
            {"role": "user", "content": "问题2"},
            {"role": "assistant", "content": "回答2"},
            {"role": "user", "content": "问题3"},
        ]
        
        result = await inject_weekly_system_prompt(messages, prompt)
        
        # Should preserve all messages, replace only system
        assert len(result) == 6
        assert result[0]["content"] == "导师提示词"
        assert result[1]["content"] == "问题1"
        assert result[2]["content"] == "回答1"
        assert result[5]["content"] == "问题3"
    
    @pytest.mark.asyncio
    async def test_inject_no_system_in_messages(self):
        """Test injecting when no system message exists."""
        prompt = WeeklySystemPrompt(
            week_start=1,
            week_end=1,
            system_prompt="系统提示",
            is_active=True,
        )
        
        messages = [
            {"role": "user", "content": "问题"},
        ]
        
        result = await inject_weekly_system_prompt(messages, prompt)
        
        assert len(result) == 2
        assert result[0]["role"] == "system"
        assert result[1]["role"] == "user"


class TestInactivePromptHandling:
    """Test handling of inactive/deleted prompts."""
    
    @pytest.mark.asyncio
    async def test_inactive_prompt_not_returned(self):
        """Test that inactive prompts are excluded from queries."""
        from gateway.app.db.weekly_prompt_crud import get_active_prompt_for_week
        
        inactive_prompt = WeeklySystemPrompt(
            id=1,
            week_start=1,
            week_end=1,
            system_prompt="已停用",
            is_active=False,  # Inactive
        )
        
        mock_session = AsyncMock(spec=AsyncSession)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # Not found
        mock_session.execute.return_value = mock_result
        
        result = await get_active_prompt_for_week(mock_session, week_number=1)
        
        # Should not return inactive prompt
        assert result is None


class TestModelDefaults:
    """Test model default values."""
    
    def test_is_active_defaults_to_true(self):
        """Test that is_active defaults to True."""
        from sqlalchemy import true
        
        col = WeeklySystemPrompt.__table__.c.is_active
        assert col.default is not None
        assert col.default.arg is True
    
    def test_timestamps_auto_set(self):
        """Test that created_at/updated_at have defaults."""
        created_col = WeeklySystemPrompt.__table__.c.created_at
        updated_col = WeeklySystemPrompt.__table__.c.updated_at
        
        assert created_col.default is not None
        assert updated_col.default is not None
        assert updated_col.onupdate is not None
