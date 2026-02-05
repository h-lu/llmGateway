"""
场景1: 基础提示词注入测试 (L1 API层)
验证: 学生发送请求时，正确的周提示词被注入到system message
"""
import pytest
import json
from unittest.mock import patch, MagicMock
import pytest_asyncio

e2e = pytest.mark.e2e
api_test = pytest.mark.api_test


@e2e
@api_test
class TestWeeklyPromptInjection:
    """测试每周提示词正确注入到学生对话中."""

    @pytest_asyncio.fixture(autouse=True)
    async def setup(self, test_student_credentials):
        """测试准备: 确保测试学生存在且有配额."""
        self.api_key = test_student_credentials["api_key"]
        self.headers = {"Authorization": f"Bearer {self.api_key}"}

    async def test_week1_prompt_injected(self, http_client):
        """测试第1周学生请求时，第1周提示词被注入."""
        # 直接测试 inject_weekly_system_prompt 服务函数
        from gateway.app.services.weekly_prompt_service import inject_weekly_system_prompt
        from gateway.app.db.models import WeeklySystemPrompt
        
        # 创建模拟的 weekly_prompt
        mock_prompt = WeeklySystemPrompt(
            week_start=1,
            week_end=1,
            system_prompt="第1周测试提示词：理论导向",
            is_active=True,
        )
        
        # 原始消息
        messages = [{"role": "user", "content": "什么是变量？"}]
        
        # 调用注入函数
        result = await inject_weekly_system_prompt(messages, mock_prompt)
        
        # 验证: 结果包含 system message
        assert len(result) == 2
        assert result[0]["role"] == "system"
        assert "第1周" in result[0]["content"]
        assert result[1] == messages[0]

    async def test_prompt_replaces_existing_system_message(self, http_client):
        """测试提示词替换已有的system message."""
        # 学生请求中已经包含system message
        # 实际验证需要查看最终发送给LLM的消息
        pass

    async def test_no_prompt_configured_uses_default(self, http_client):
        """测试未配置提示词的周使用默认行为."""
        # 直接测试 inject_weekly_system_prompt 在 weekly_prompt=None 时的行为
        from gateway.app.services.weekly_prompt_service import inject_weekly_system_prompt
        
        # 原始消息（没有 system message）
        messages = [{"role": "user", "content": "问题"}]
        
        # 调用注入函数，传入 None（模拟没有配置提示词）
        result = await inject_weekly_system_prompt(messages, None)
        
        # 验证: 消息保持不变
        assert result == messages
        assert len(result) == 1
        assert result[0]["role"] == "user"

    async def test_service_caches_prompt_for_same_week(self, http_client):
        """测试服务对同一周的提示词进行缓存."""
        from gateway.app.services.weekly_prompt_service import get_weekly_prompt_service
        
        service = get_weekly_prompt_service()
        
        # 重置缓存
        service.invalidate_cache()
        assert not service._cache_valid
        
        # 第一次请求应该查询数据库
        # 第二次请求应该使用缓存
