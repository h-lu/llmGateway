"""
Selenium E2E tests for TeachProxy Admin
"""
import time
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

BASE_URL = "http://localhost:5173"
ADMIN_TOKEN = "_D9PyQ6EvlyNI9Rs_ZdHOijGQQ_6dI2YuvdosTcl4Bc"


@pytest.fixture
def driver():
    """Setup Chrome driver"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    driver.implicitly_wait(10)
    yield driver
    driver.quit()


def test_login_page_loads(driver):
    """Test login page loads correctly"""
    driver.get(f"{BASE_URL}/login")
    
    # Check page title
    assert "TeachProxy Admin" in driver.page_source
    
    # Check form elements
    assert "Admin Token" in driver.page_source
    
    # Find login button
    login_btn = driver.find_element(By.TAG_NAME, "button")
    assert login_btn.text == "Login"
    
    print("✓ Login page loads correctly")


def test_login_flow(driver):
    """Test successful login"""
    driver.get(f"{BASE_URL}/login")
    
    # Find and fill password input
    password_input = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
    password_input.send_keys(ADMIN_TOKEN)
    
    # Click login
    login_btn = driver.find_element(By.TAG_NAME, "button")
    login_btn.click()
    
    # Wait for redirect
    WebDriverWait(driver, 10).until(
        EC.url_to_be(f"{BASE_URL}/")
    )
    
    # Check dashboard
    assert "Dashboard" in driver.page_source
    print("✓ Login successful, dashboard visible")


def test_conversations_page(driver):
    """Test conversations page"""
    # Login first
    driver.get(f"{BASE_URL}/login")
    driver.find_element(By.CSS_SELECTOR, "input[type='password']").send_keys(ADMIN_TOKEN)
    driver.find_element(By.TAG_NAME, "button").click()
    WebDriverWait(driver, 10).until(EC.url_to_be(f"{BASE_URL}/"))
    
    # Navigate to conversations
    driver.find_element(By.LINK_TEXT, "Conversations").click()
    WebDriverWait(driver, 10).until(
        EC.url_to_be(f"{BASE_URL}/conversations")
    )
    
    # Check page title
    assert "Conversations" in driver.page_source
    
    # Check for filter dropdown
    assert "Filter by action" in driver.page_source
    
    # Take screenshot
    driver.save_screenshot("/tmp/conversations_selenium.png")
    
    # Check console logs (if available)
    logs = driver.get_log("browser") if hasattr(driver, "get_log") else []
    errors = [log for log in logs if log.get("level") == "SEVERE"]
    if errors:
        print(f"Console errors: {errors}")
    
    print(f"✓ Conversations page loaded")
    print(f"Page content preview: {driver.page_source[:500]}...")


def test_students_page(driver):
    """Test students page"""
    # Login
    driver.get(f"{BASE_URL}/login")
    driver.find_element(By.CSS_SELECTOR, "input[type='password']").send_keys(ADMIN_TOKEN)
    driver.find_element(By.TAG_NAME, "button").click()
    WebDriverWait(driver, 10).until(EC.url_to_be(f"{BASE_URL}/"))
    
    # Navigate
    driver.find_element(By.LINK_TEXT, "Students").click()
    WebDriverWait(driver, 10).until(
        EC.url_to_be(f"{BASE_URL}/students")
    )
    
    assert "Students" in driver.page_source
    assert "Add Student" in driver.page_source
    print("✓ Students page loaded")


def test_rules_page(driver):
    """Test rules page"""
    # Login
    driver.get(f"{BASE_URL}/login")
    driver.find_element(By.CSS_SELECTOR, "input[type='password']").send_keys(ADMIN_TOKEN)
    driver.find_element(By.TAG_NAME, "button").click()
    WebDriverWait(driver, 10).until(EC.url_to_be(f"{BASE_URL}/"))
    
    # Navigate
    driver.find_element(By.LINK_TEXT, "Rules").click()
    WebDriverWait(driver, 10).until(
        EC.url_to_be(f"{BASE_URL}/rules")
    )
    
    assert "Rules" in driver.page_source
    print("✓ Rules page loaded")


def test_weekly_prompts_page(driver):
    """Test weekly prompts page"""
    # Login
    driver.get(f"{BASE_URL}/login")
    driver.find_element(By.CSS_SELECTOR, "input[type='password']").send_keys(ADMIN_TOKEN)
    driver.find_element(By.TAG_NAME, "button").click()
    WebDriverWait(driver, 10).until(EC.url_to_be(f"{BASE_URL}/"))
    
    # Navigate
    driver.find_element(By.LINK_TEXT, "Weekly Prompts").click()
    WebDriverWait(driver, 10).until(
        EC.url_to_be(f"{BASE_URL}/weekly-prompts")
    )
    
    assert "Weekly Prompts" in driver.page_source
    print("✓ Weekly Prompts page loaded")


if __name__ == "__main__":
    print("Running Selenium E2E tests...")
    
    # Setup driver
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=chrome_options
    )
    driver.implicitly_wait(10)
    
    try:
        # Run tests
        print("\n1. Testing login page...")
        driver.get(f"{BASE_URL}/login")
        time.sleep(2)
        print(f"Title: {driver.title}")
        print(f"Has 'TeachProxy Admin': {'TeachProxy Admin' in driver.page_source}")
        
        print("\n2. Testing login flow...")
        driver.find_element(By.CSS_SELECTOR, "input[type='password']").send_keys(ADMIN_TOKEN)
        driver.find_element(By.TAG_NAME, "button").click()
        time.sleep(3)
        print(f"Current URL: {driver.current_url}")
        print(f"Has 'Dashboard': {'Dashboard' in driver.page_source}")
        
        print("\n3. Testing conversations page...")
        driver.find_element(By.LINK_TEXT, "Conversations").click()
        time.sleep(3)
        print(f"Current URL: {driver.current_url}")
        print(f"Has 'Conversations': {'Conversations' in driver.page_source}")
        
        # Take screenshot
        driver.save_screenshot("/tmp/conversations_debug.png")
        print("Screenshot saved to /tmp/conversations_debug.png")
        
        # Get page source snippet
        page_text = driver.find_element(By.TAG_NAME, "body").text
        print(f"\nPage text preview:\n{page_text[:1000]}")
        
    finally:
        driver.quit()
    
    print("\n✓ Tests completed")
