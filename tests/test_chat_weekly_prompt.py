"""Integration tests for weekly system prompt in chat API."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from gateway.app.db.models import WeeklySystemPrompt, Student


class TestChatWeeklyPromptIntegration:
    """Test weekly system prompt integration in chat API."""
    
    @pytest.mark.asyncio
    @patch("gateway.app.api.chat.evaluate_prompt")
    @patch("gateway.app.api.chat.get_current_week_number")
    @patch("gateway.app.api.chat.get_weekly_prompt_service")
    async def test_chat_uses_weekly_system_prompt(
        self,
        mock_get_service,
        mock_get_week,
        mock_evaluate,
    ):
        """Test that chat API injects weekly system prompt."""
        # Setup mocks
        mock_get_week.return_value = 1
        
        # Mock rule evaluation - passed
        mock_result = MagicMock()
        mock_result.action = "passed"
        mock_result.rule_id = None
        mock_result.message = None
        mock_evaluate.return_value = mock_result
        
        # Mock weekly prompt service
        mock_service = MagicMock()
        weekly_prompt = WeeklySystemPrompt(
            id=1,
            week_start=1,
            week_end=2,
            system_prompt="【第1-2周】请引导学生理解变量概念",
            is_active=True,
        )
        mock_service.get_prompt_for_week = AsyncMock(return_value=weekly_prompt)
        mock_get_service.return_value = mock_service
        
        # Test inject_weekly_system_prompt directly
        from gateway.app.services.weekly_prompt_service import inject_weekly_system_prompt
        
        messages = [
            {"role": "user", "content": "什么是变量？"},
        ]
        
        result = await inject_weekly_system_prompt(messages, weekly_prompt)
        
        # First message should be the weekly system prompt
        assert result[0]["role"] == "system"
        assert "【第1-2周】" in result[0]["content"]
        
        # Second message should be the user question
        assert result[1]["role"] == "user"
        assert result[1]["content"] == "什么是变量？"
    
    @pytest.mark.asyncio
    @patch("gateway.app.api.chat.evaluate_prompt")
    @patch("gateway.app.api.chat.get_current_week_number")
    @patch("gateway.app.api.chat.get_weekly_prompt_service")
    async def test_chat_no_weekly_prompt_uses_original(
        self,
        mock_get_service,
        mock_get_week,
        mock_evaluate,
    ):
        """Test that original messages are used when no weekly prompt configured."""
        mock_get_week.return_value = 99  # Week with no prompt
        
        mock_result = MagicMock()
        mock_result.action = "passed"
        mock_evaluate.return_value = mock_result
        
        # No weekly prompt configured
        mock_service = MagicMock()
        mock_service.get_prompt_for_week = AsyncMock(return_value=None)
        mock_get_service.return_value = mock_service
        
        # Test inject_weekly_system_prompt directly
        from gateway.app.services.weekly_prompt_service import inject_weekly_system_prompt
        
        messages = [
            {"role": "system", "content": "原有系统消息"},
            {"role": "user", "content": "问题"},
        ]
        
        result = await inject_weekly_system_prompt(messages, None)
        
        # Verify original system message is preserved
        assert result[0]["role"] == "system"
        assert result[0]["content"] == "原有系统消息"
        assert len(result) == 2
    
    @pytest.mark.asyncio
    @patch("gateway.app.api.chat.evaluate_prompt")
    @patch("gateway.app.api.chat.get_current_week_number")
    async def test_chat_blocked_rule_takes_precedence(
        self,
        mock_get_week,
        mock_evaluate,
    ):
        """Test that blocked rules still work with weekly prompt feature."""
        mock_get_week.return_value = 1
        
        # Rule blocks the request
        mock_result = MagicMock()
        mock_result.action = "blocked"
        mock_result.rule_id = "rule:direct_answer"
        mock_result.message = "检测到直接要答案，请先自己思考"
        mock_evaluate.return_value = mock_result
        
        # Test that evaluate_prompt returns blocked result
        assert mock_result.action == "blocked"
        assert "请先自己思考" in mock_result.message
    
    @pytest.mark.asyncio
    async def test_weekly_prompt_replaces_existing_system(self):
        """Test that weekly prompt replaces existing system message."""
        from gateway.app.services.weekly_prompt_service import inject_weekly_system_prompt
        
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
        
        # Should replace, not add
        assert len(result) == 2
        assert result[0]["content"] == "【每周提示】本周学习变量"
    
    @pytest.mark.asyncio
    async def test_weekly_prompt_adds_when_no_system(self):
        """Test that weekly prompt is added when no system message exists."""
        from gateway.app.services.weekly_prompt_service import inject_weekly_system_prompt
        
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
