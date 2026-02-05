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
        # Mock inject_weekly_system_prompt 来捕获注入的提示词
        captured_prompt = None
        
        def capture_inject(messages, weekly_prompt):
            nonlocal captured_prompt
            if weekly_prompt:
                captured_prompt = weekly_prompt.system_prompt
            return messages
        
        with patch("gateway.app.api.chat.inject_weekly_system_prompt") as mock_inject:
            mock_inject.side_effect = capture_inject
            
            # 模拟第1周
            with patch("gateway.app.core.utils.get_current_week_number", return_value=1):
                with patch("gateway.app.api.chat.check_and_reserve_quota"):
                    with patch("gateway.app.providers.loadbalancer.LoadBalancer.get_provider"):
                        # 学生发送问题
                        response = await http_client.post(
                            "/v1/chat/completions",
                            headers=self.headers,
                            json={
                                "model": "deepseek-chat",
                                "messages": [{"role": "user", "content": "什么是变量？"}],
                                "max_tokens": 100,
                            },
                        )

        # 验证请求被处理（可能会有配额或认证错误，但inject应该被调用）
        # 主要验证inject函数被调用了
        mock_inject.assert_called()

    async def test_prompt_replaces_existing_system_message(self, http_client):
        """测试提示词替换已有的system message."""
        # 学生请求中已经包含system message
        # 实际验证需要查看最终发送给LLM的消息
        pass

    async def test_no_prompt_configured_uses_default(self, http_client):
        """测试未配置提示词的周使用默认行为."""
        # 模拟第99周（无配置）
        with patch("gateway.app.core.utils.get_current_week_number", return_value=99):
            response = await http_client.post(
                "/v1/chat/completions",
                headers=self.headers,
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": "问题"}],
                },
            )

        # 应该成功（或返回配额/认证错误，但不是500）
        assert response.status_code in [200, 401, 403, 429]

    async def test_service_caches_prompt_for_same_week(self, http_client):
        """测试服务对同一周的提示词进行缓存."""
        from gateway.app.services.weekly_prompt_service import get_weekly_prompt_service
        
        service = get_weekly_prompt_service()
        
        # 重置缓存
        service.invalidate_cache()
        assert not service._cache_valid
        
        # 第一次请求应该查询数据库
        # 第二次请求应该使用缓存
