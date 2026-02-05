"""
场景3: 周切换测试 (L2 Browser层)
验证: 管理员可以在UI中切换周配置，学生端体验相应变化
"""
import pytest

e2e = pytest.mark.e2e
browser_test = pytest.mark.browser_test


@e2e
@browser_test
class TestWeekTransitionUI:
    """测试管理员UI中的周切换功能."""

    @pytest.fixture
    async def browser_page(self):
        """提供Playwright page实例."""
        pytest.skip("Browser tests require playwright and running frontend")
        # 实际实现需要:
        # from playwright.async_api import async_playwright
        # async with async_playwright() as p:
        #     browser = await p.chromium.launch(headless=True)
        #     page = await browser.new_page()
        #     yield page
        #     await browser.close()

    async def test_admin_can_view_all_week_prompts(self, browser_page):
        """验证管理员可以查看所有周的提示词配置."""
        # 跳过的测试占位符
        pass

    async def test_admin_can_create_week_prompt(self, browser_page):
        """验证管理员可以创建新的周提示词."""
        pass

    async def test_current_week_highlighted(self, browser_page):
        """验证当前周的提示词被高亮显示."""
        pass
