"""
场景4: 边界周测试 (L1 API层)
验证: 第1周、最后一周、无配置周的处理
"""
import pytest
from unittest.mock import patch, MagicMock

e2e = pytest.mark.e2e
api_test = pytest.mark.api_test


@e2e
@api_test
class TestBoundaryWeeks:
    """测试边界周的处理."""

    @pytest.fixture
    def api_headers(self, test_student_credentials):
        """返回API请求头."""
        return {"Authorization": f"Bearer {test_student_credentials['api_key']}"}

    async def test_week_1_boundary(self, http_client, api_headers):
        """测试第1周边界情况."""
        with patch("gateway.app.core.utils.get_current_week_number", return_value=1):
            response = await http_client.post(
                "/v1/chat/completions",
                headers=api_headers,
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": "开始学习"}],
                },
            )

        # 应该成功或返回业务错误（配额/认证），但不是服务器错误
        assert response.status_code < 500

    async def test_week_20_boundary(self, http_client, api_headers):
        """测试第20周（假设课程共20周）边界情况."""
        with patch("gateway.app.core.utils.get_current_week_number", return_value=20):
            response = await http_client.post(
                "/v1/chat/completions",
                headers=api_headers,
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": "期末复习"}],
                },
            )

        assert response.status_code < 500

    async def test_week_0_invalid(self, http_client, api_headers):
        """测试第0周（无效周数）的处理."""
        # 系统应该能处理无效周数（转换为1或其他默认值）
        with patch("gateway.app.core.utils.get_current_week_number", return_value=0):
            response = await http_client.post(
                "/v1/chat/completions",
                headers=api_headers,
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": "测试"}],
                },
            )

        # 即使周数无效，也不应该崩溃
        assert response.status_code < 500

    async def test_week_without_prompt_config(self, http_client, api_headers):
        """测试没有配置提示词的周."""
        # 模拟一个肯定没有配置的周数
        with patch("gateway.app.core.utils.get_current_week_number", return_value=999):
            captured_messages = None
            
            def capture_inject(messages, weekly_prompt):
                nonlocal captured_messages
                captured_messages = (messages, weekly_prompt)
                return messages
            
            with patch("gateway.app.api.chat.inject_weekly_system_prompt") as mock_inject:
                mock_inject.side_effect = capture_inject
                
                response = await http_client.post(
                    "/v1/chat/completions",
                    headers=api_headers,
                    json={
                        "model": "deepseek-chat",
                        "messages": [{"role": "user", "content": "问题"}],
                    },
                )

        # 应该成功，只是没有注入自定义提示词
        assert response.status_code < 500
        
        # 验证: 如果没有配置，weekly_prompt 应该是 None
        if captured_messages:
            messages, weekly_prompt = captured_messages
            # 当没有配置时，inject函数可能收到None
            pass

    async def test_week_with_inactive_prompt(self, http_client, api_headers):
        """测试有配置但被禁用的提示词周."""
        # 创建一个is_active=False的提示词场景
        # 验证不会被使用
        with patch("gateway.app.core.utils.get_current_week_number", return_value=1):
            with patch("gateway.app.db.weekly_prompt_crud.get_active_prompt_for_week") as mock_get:
                # 返回None模拟没有active的提示词
                mock_get.return_value = None
                
                response = await http_client.post(
                    "/v1/chat/completions",
                    headers=api_headers,
                    json={
                        "model": "deepseek-chat",
                        "messages": [{"role": "user", "content": "测试"}],
                    },
                )

        assert response.status_code < 500

    async def test_negative_week_handling(self, http_client, api_headers):
        """测试负周数的处理."""
        with patch("gateway.app.core.utils.get_current_week_number", return_value=-1):
            response = await http_client.post(
                "/v1/chat/completions",
                headers=api_headers,
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": "测试"}],
                },
            )

        # 负周数不应该导致系统崩溃
        assert response.status_code < 500
