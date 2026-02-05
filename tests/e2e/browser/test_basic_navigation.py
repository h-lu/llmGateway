"""
L2 Browser 基础导航测试
验证: 前端页面可以正常访问
"""
import pytest
from playwright.async_api import async_playwright, Page

e2e = pytest.mark.e2e
browser_test = pytest.mark.browser_test


@e2e
@browser_test
class TestBasicNavigation:
    """测试前端基础导航."""

    @pytest.fixture
    async def browser_page(self):
        """提供Playwright page实例."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            yield page
            await browser.close()

    async def test_login_page_accessible(self, browser_page: Page):
        """验证登录页面可以访问."""
        page = browser_page
        
        # 访问登录页面
        response = await page.goto("http://localhost:5173/login")
        
        # 验证页面加载成功
        assert response.status == 200
        
        # 验证页面标题或内容
        title = await page.title()
        assert len(title) > 0
        
        # 截图保存
        await page.screenshot(path="/tmp/test_login_page.png")
        print(f"\n✅ Login page screenshot saved to /tmp/test_login_page.png")

    async def test_weekly_prompts_page_accessible(self, browser_page: Page):
        """验证Weekly Prompts页面可以访问（可能需要登录）."""
        page = browser_page
        
        response = await page.goto("http://localhost:5173/weekly-prompts")
        
        # 页面应该能访问（可能会重定向到登录）
        assert response.status == 200
        
        # 获取当前URL
        current_url = page.url
        print(f"\n📍 Weekly Prompts page URL: {current_url}")
        
        # 截图
        await page.screenshot(path="/tmp/test_weekly_prompts_page.png")
        print(f"✅ Weekly Prompts page screenshot saved to /tmp/test_weekly_prompts_page.png")

    async def test_page_has_react_root(self, browser_page: Page):
        """验证页面是React应用."""
        page = browser_page
        
        await page.goto("http://localhost:5173/")
        
        # 检查是否有React根元素
        root_element = await page.query_selector("#root")
        assert root_element is not None, "Page should have React root element"
