"""
Simple E2E test using Playwright
"""
import pytest
from playwright.sync_api import sync_playwright, Page, expect

BASE_URL = "http://localhost:5173"
ADMIN_TOKEN = "_D9PyQ6EvlyNI9Rs_ZdHOijGQQ_6dI2YuvdosTcl4Bc"


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    page = browser.new_page()
    yield page
    page.close()


def test_login_page_loads(page: Page):
    """Test login page loads correctly"""
    page.goto(f"{BASE_URL}/login")
    
    # Check page title
    expect(page.locator("text=TeachProxy Admin")).to_be_visible()
    expect(page.locator("text=Admin Token")).to_be_visible()
    expect(page.locator("button:has-text('Login')")).to_be_visible()


def test_login_flow(page: Page):
    """Test successful login"""
    page.goto(f"{BASE_URL}/login")
    
    # Fill in token
    page.fill("input[type='password']", ADMIN_TOKEN)
    
    # Click login
    page.click("button:has-text('Login')")
    
    # Wait for redirect to dashboard
    page.wait_for_url(f"{BASE_URL}/")
    
    # Check dashboard is visible
    expect(page.locator("text=Dashboard")).to_be_visible()


def test_conversations_page(page: Page):
    """Test conversations page displays data"""
    # Login first
    page.goto(f"{BASE_URL}/login")
    page.fill("input[type='password']", ADMIN_TOKEN)
    page.click("button:has-text('Login')")
    page.wait_for_url(f"{BASE_URL}/")
    
    # Navigate to conversations
    page.click("text=Conversations")
    page.wait_for_url(f"{BASE_URL}/conversations")
    
    # Check page title
    expect(page.locator("h2:has-text('Conversations')")).to_be_visible()
    
    # Check if filter dropdown exists
    expect(page.locator("text=Filter by action")).to_be_visible()
    
    # Take screenshot for debugging
    page.screenshot(path="/tmp/conversations.png")
    
    # Check console for errors
    logs = page.evaluate("() => { return window.console ? window.console.error : []; }")
    print(f"Console errors: {logs}")


def test_students_page(page: Page):
    """Test students page"""
    # Login
    page.goto(f"{BASE_URL}/login")
    page.fill("input[type='password']", ADMIN_TOKEN)
    page.click("button:has-text('Login')")
    page.wait_for_url(f"{BASE_URL}/")
    
    # Navigate to students
    page.click("text=Students")
    page.wait_for_url(f"{BASE_URL}/students")
    
    expect(page.locator("h2:has-text('Students')")).to_be_visible()
    expect(page.locator("button:has-text('Add Student')")).to_be_visible()


def test_rules_page(page: Page):
    """Test rules page"""
    # Login
    page.goto(f"{BASE_URL}/login")
    page.fill("input[type='password']", ADMIN_TOKEN)
    page.click("button:has-text('Login')")
    page.wait_for_url(f"{BASE_URL}/")
    
    # Navigate to rules
    page.click("text=Rules")
    page.wait_for_url(f"{BASE_URL}/rules")
    
    expect(page.locator("h2:has-text('Rules')")).to_be_visible()


def test_weekly_prompts_page(page: Page):
    """Test weekly prompts page"""
    # Login
    page.goto(f"{BASE_URL}/login")
    page.fill("input[type='password']", ADMIN_TOKEN)
    page.click("button:has-text('Login')")
    page.wait_for_url(f"{BASE_URL}/")
    
    # Navigate to weekly prompts
    page.click("text=Weekly Prompts")
    page.wait_for_url(f"{BASE_URL}/weekly-prompts")
    
    expect(page.locator("h2:has-text('Weekly Prompts')")).to_be_visible()


if __name__ == "__main__":
    # Run simple test
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("Testing login page...")
        page.goto(f"{BASE_URL}/login")
        print(f"Page title: {page.title()}")
        print(f"URL: {page.url}")
        
        # Check if elements exist
        if page.locator("text=TeachProxy Admin").count() > 0:
            print("✓ Login form found")
        else:
            print("✗ Login form not found")
        
        browser.close()
