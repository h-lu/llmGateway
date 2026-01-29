# tests/test_weekly_prompt_service.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from gateway.app.services.weekly_prompt_service import (
    WeeklyPromptService,
    get_weekly_prompt_service,
    inject_weekly_system_prompt,
    get_and_inject_weekly_prompt,
    reset_weekly_prompt_service,
)
from gateway.app.db.models import WeeklySystemPrompt


class TestWeeklyPromptService:
    """Test WeeklyPromptService."""
    
    def setup_method(self):
        """Reset service before each test."""
        reset_weekly_prompt_service()
    
    @pytest.mark.asyncio
    async def test_get_prompt_for_week_cached(self):
        """Test service returns cached prompt."""
        service = WeeklyPromptService()
        
        # Mock the cache hit
        cached_prompt = WeeklySystemPrompt(
            id=1,
            week_start=1,
            week_end=2,
            system_prompt="第1-2周提示词",
            is_active=True,
        )
        service._cached_prompt = cached_prompt
        service._cached_week = 1
        
        mock_session = AsyncMock()
        
        result = await service.get_prompt_for_week(mock_session, week_number=1)
        
        assert result == cached_prompt
        # Should not hit database when cached
        mock_session.execute.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_get_prompt_for_week_db_fetch(self):
        """Test service fetches from DB when not cached."""
        service = WeeklyPromptService()
        
        mock_session = AsyncMock()
        mock_result = MagicMock()
        db_prompt = WeeklySystemPrompt(
            id=1,
            week_start=1,
            week_end=2,
            system_prompt="从数据库获取",
            is_active=True,
        )
        mock_result.scalar_one_or_none.return_value = db_prompt
        mock_session.execute.return_value = mock_result
        
        result = await service.get_prompt_for_week(mock_session, week_number=1)
        
        assert result is not None
        assert result.system_prompt == "从数据库获取"
        # Should be cached now
        assert service._cached_week == 1
        assert service._cached_prompt == db_prompt
    
    @pytest.mark.asyncio
    async def test_get_prompt_for_week_no_config(self):
        """Test when no prompt is configured for the week."""
        service = WeeklyPromptService()
        
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        result = await service.get_prompt_for_week(mock_session, week_number=99)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_cache_invalidation_on_week_change(self):
        """Test cache is invalidated when week changes."""
        service = WeeklyPromptService()
        
        # Set cache for week 1
        service._cached_week = 1
        service._cached_prompt = MagicMock()
        
        mock_session = AsyncMock()
        mock_result = MagicMock()
        new_prompt = WeeklySystemPrompt(
            id=2,
            week_start=2,
            week_end=2,
            system_prompt="第2周",
            is_active=True,
        )
        mock_result.scalar_one_or_none.return_value = new_prompt
        mock_session.execute.return_value = mock_result
        
        # Request week 2
        result = await service.get_prompt_for_week(mock_session, week_number=2)
        
        assert result.system_prompt == "第2周"
    
    def test_invalidate_cache(self):
        """Test cache invalidation."""
        service = WeeklyPromptService()
        service._cached_week = 1
        service._cached_prompt = MagicMock()
        
        service.invalidate_cache()
        
        assert service._cached_week is None
        assert service._cached_prompt is None
    
    def test_reload(self):
        """Test reload method."""
        service = WeeklyPromptService()
        service._cached_week = 1
        service._cached_prompt = MagicMock()
        
        service.reload()
        
        assert service._cached_week is None
        assert service._cached_prompt is None


class TestInjectWeeklySystemPrompt:
    """Test inject_weekly_system_prompt function."""
    
    @pytest.mark.asyncio
    async def test_inject_replaces_system_message(self):
        """Test weekly prompt replaces existing system message."""
        weekly_prompt = WeeklySystemPrompt(
            id=1,
            week_start=1,
            week_end=1,
            system_prompt="【每周提示】本周学习变量",
            is_active=True,
        )
        
        messages = [
            {"role": "system", "content": "原有系统消息"},
            {"role": "user", "content": "学生问题"},
        ]
        
        result = await inject_weekly_system_prompt(messages, weekly_prompt)
        
        assert len(result) == 2
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "【每周提示】本周学习变量"
        assert result[1]["role"] == "user"
    
    @pytest.mark.asyncio
    async def test_inject_adds_system_message(self):
        """Test weekly prompt is added when no system message exists."""
        weekly_prompt = WeeklySystemPrompt(
            id=1,
            week_start=1,
            week_end=1,
            system_prompt="【每周提示】",
            is_active=True,
        )
        
        messages = [
            {"role": "user", "content": "学生问题"},
        ]
        
        result = await inject_weekly_system_prompt(messages, weekly_prompt)
        
        assert len(result) == 2
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "【每周提示】"
    
    @pytest.mark.asyncio
    async def test_inject_no_prompt(self):
        """Test messages unchanged when no weekly prompt."""
        messages = [
            {"role": "system", "content": "原有系统消息"},
            {"role": "user", "content": "学生问题"},
        ]
        
        result = await inject_weekly_system_prompt(messages, None)
        
        assert result == messages
    
    @pytest.mark.asyncio
    async def test_inject_preserves_other_messages(self):
        """Test that non-system messages are preserved."""
        weekly_prompt = WeeklySystemPrompt(
            id=1,
            week_start=1,
            week_end=1,
            system_prompt="【每周提示】",
            is_active=True,
        )
        
        messages = [
            {"role": "system", "content": "原有系统消息"},
            {"role": "user", "content": "问题1"},
            {"role": "assistant", "content": "回答1"},
            {"role": "user", "content": "问题2"},
        ]
        
        result = await inject_weekly_system_prompt(messages, weekly_prompt)
        
        assert len(result) == 4
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "【每周提示】"
        assert result[1]["role"] == "user"
        assert result[1]["content"] == "问题1"
        assert result[2]["role"] == "assistant"
        assert result[3]["role"] == "user"


class TestGetAndInjectWeeklyPrompt:
    """Test get_and_inject_weekly_prompt convenience function."""
    
    @pytest.mark.asyncio
    async def test_get_and_inject(self):
        """Test the convenience function."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        weekly_prompt = WeeklySystemPrompt(
            id=1,
            week_start=1,
            week_end=1,
            system_prompt="【每周提示】",
            is_active=True,
        )
        mock_result.scalar_one_or_none.return_value = weekly_prompt
        mock_session.execute.return_value = mock_result
        
        messages = [
            {"role": "user", "content": "问题"},
        ]
        
        result = await get_and_inject_weekly_prompt(mock_session, messages, week_number=1)
        
        assert len(result) == 2
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "【每周提示】"


class TestGetWeeklyPromptService:
    """Test get_weekly_prompt_service function."""
    
    def setup_method(self):
        """Reset service before each test."""
        reset_weekly_prompt_service()
    
    def test_returns_singleton(self):
        """Test that the same instance is returned."""
        service1 = get_weekly_prompt_service()
        service2 = get_weekly_prompt_service()
        
        assert service1 is service2
    
    def test_reset_creates_new_instance(self):
        """Test reset creates a new instance."""
        service1 = get_weekly_prompt_service()
        reset_weekly_prompt_service()
        service2 = get_weekly_prompt_service()
        
        assert service1 is not service2
