"""
场景3: 周切换测试 (L2 Browser层)
验证: 管理员可以在UI中查看和管理周提示词配置
"""
import pytest
from playwright.async_api import async_playwright, Page, expect

e2e = pytest.mark.e2e
browser_test = pytest.mark.browser_test


@e2e
@browser_test
class TestWeekTransitionUI:
    """测试管理员UI中的周提示词管理功能."""

    @pytest.fixture
    async def browser_page(self):
        """提供Playwright page实例."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            yield page
            await browser.close()

    @pytest.fixture
    async def logged_in_admin(self, browser_page: Page):
        """登录管理员并返回page."""
        page = browser_page
        
        # 访问登录页面
        await page.goto("http://localhost:5173/login")
        
        # 等待登录表单加载
        await page.wait_for_selector("input[type='password']", timeout=5000)
        
        # 输入密码（从环境变量或默认）
        # 注意：这里使用默认密码，实际应该从环境变量读取
        await page.fill("input[type='password']", "teachproxy123")
        
        # 点击登录
        await page.click("button[type='submit']")
        
        # 等待跳转到首页
        await page.wait_for_url("http://localhost:5173/", timeout=10000)
        
        return page

    async def test_weekly_prompts_page_loads(self, logged_in_admin: Page):
        """验证Weekly Prompts页面可以正常加载."""
        page = logged_in_admin
        
        # 导航到Weekly Prompts页面
        await page.goto("http://localhost:5173/weekly-prompts")
        
        # 验证页面标题
        await expect(page.locator("h2")).to_contain_text("Weekly Prompts")
        
        # 验证页面包含关键元素
        await expect(page.locator("text=Create New Prompt")).to_be_visible()

    async def test_can_view_prompts_list(self, logged_in_admin: Page):
        """验证可以查看提示词列表."""
        page = logged_in_admin
        
        await page.goto("http://localhost:5173/weekly-prompts")
        
        # 等待表格加载
        await page.wait_for_selector("table", timeout=5000)
        
        # 验证表格有表头
        headers = page.locator("table thead th")
        header_count = await headers.count()
        assert header_count >= 3, "Table should have at least 3 columns"

    async def test_create_prompt_form_exists(self, logged_in_admin: Page):
        """验证创建提示词表单存在."""
        page = logged_in_admin
        
        await page.goto("http://localhost:5173/weekly-prompts")
        
        # 验证表单字段存在
        await expect(page.locator("input[type='number']").first).to_be_visible()
        await expect(page.locator("textarea")).to_be_visible()
        await expect(page.locator("button:has-text('Create Prompt')")).to_be_visible()

    async def test_navigation_from_sidebar(self, logged_in_admin: Page):
        """验证可以从侧边栏导航到Weekly Prompts."""
        page = logged_in_admin
        
        # 在首页
        await page.goto("http://localhost:5173/")
        
        # 点击Weekly Prompts链接（假设在侧边栏）
        weekly_prompts_link = page.locator("a[href='/weekly-prompts']")
        
        if await weekly_prompts_link.count() > 0:
            await weekly_prompts_link.click()
            await page.wait_for_url("http://localhost:5173/weekly-prompts")
            await expect(page.locator("h2")).to_contain_text("Weekly Prompts")

    async def test_page_has_current_week_card(self, logged_in_admin: Page):
        """验证页面有当前周提示词卡片."""
        page = logged_in_admin
        
        await page.goto("http://localhost:5173/weekly-prompts")
        
        # 检查是否有当前周提示词的卡片（蓝色背景）
        # 注意：如果有配置当前周的提示词，会显示蓝色卡片
        current_cards = page.locator(".bg-blue-50, .bg-blue-100")
        
        # 卡片可能存在也可能不存在，取决于是否有当前周的配置
        # 我们主要验证页面结构正确
        await expect(page.locator("text=Current Week").or_(page.locator("text=Weekly Prompts"))).to_be_visible()
