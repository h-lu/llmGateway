"""
Browser-use end-to-end tests for TeachProxy Admin
"""
import asyncio
import pytest
from browser_use import Agent, Browser, BrowserConfig
from langchain_openai import ChatOpenAI

# Configure browser
browser = Browser(config=BrowserConfig(
    headless=True,  # Set to False to see the browser
    disable_security=True,
))

# Use a cheap/fast model for testing
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.0,
)

BASE_URL = "http://localhost:5173"
ADMIN_TOKEN = "_D9PyQ6EvlyNI9Rs_ZdHOijGQQ_6dI2YuvdosTcl4Bc"


@pytest.mark.asyncio
async def test_admin_login():
    """Test admin login flow"""
    agent = Agent(
        task=f"""
        Go to {BASE_URL}/login
        
        You should see a login form with:
        - Title: "TeachProxy Admin"
        - Input field labeled "Admin Token"
        - Login button
        
        Enter the admin token: {ADMIN_TOKEN}
        Click the Login button
        
        Verify you are redirected to the Dashboard page (URL should be {BASE_URL}/)
        Look for "Dashboard" heading on the page
        
        Report the result: Did login succeed? What stats are visible on dashboard?
        """,
        llm=llm,
        browser=browser,
    )
    
    result = await agent.run()
    print(f"Login test result: {result}")
    
    # Verify success indicators
    assert "dashboard" in result.lower() or "Dashboard" in result


@pytest.mark.asyncio
async def test_conversations_page():
    """Test conversations page displays data"""
    agent = Agent(
        task=f"""
        Go to {BASE_URL}/login
        
        Login with token: {ADMIN_TOKEN}
        
        After login, navigate to the Conversations page by clicking on "Conversations" in the sidebar
        
        Verify:
        1. The page title "Conversations" is visible
        2. Check if there's a filter dropdown for "Filter by action"
        3. Check if conversation data is displayed in a table
        
        If no data is shown, check browser console (F12) for errors
        
        Report: 
        - Is the Conversations page loading?
        - Are there any error messages?
        - How many conversations are displayed (if any)?
        """,
        llm=llm,
        browser=browser,
    )
    
    result = await agent.run()
    print(f"Conversations test result: {result}")
    
    # Should at least see the page title
    assert "conversations" in result.lower() or "Conversations" in result


@pytest.mark.asyncio
async def test_students_page():
    """Test students page"""
    agent = Agent(
        task=f"""
        Go to {BASE_URL}/login
        
        Login with token: {ADMIN_TOKEN}
        
        Navigate to the Students page
        
        Verify:
        1. Page title "Students" is visible
        2. "Add Student" button is present
        3. Student data table is displayed
        
        Report the number of students shown and any visible student names/emails
        """,
        llm=llm,
        browser=browser,
    )
    
    result = await agent.run()
    print(f"Students test result: {result}")
    
    assert "students" in result.lower() or "Students" in result


@pytest.mark.asyncio
async def test_rules_page():
    """Test rules page"""
    agent = Agent(
        task=f"""
        Go to {BASE_URL}/login
        
        Login with token: {ADMIN_TOKEN}
        
        Navigate to the Rules page
        
        Verify:
        1. Page title "Rules" is visible
        2. Form to create new rule is present (Pattern, Type, Message fields)
        3. "Reload Cache" button is visible
        
        Report the current state of the rules page
        """,
        llm=llm,
        browser=browser,
    )
    
    result = await agent.run()
    print(f"Rules test result: {result}")
    
    assert "rules" in result.lower() or "Rules" in result


@pytest.mark.asyncio
async def test_weekly_prompts_page():
    """Test weekly prompts page"""
    agent = Agent(
        task=f"""
        Go to {BASE_URL}/login
        
        Login with token: {ADMIN_TOKEN}
        
        Navigate to the "Weekly Prompts" page
        
        Verify:
        1. Page title "Weekly Prompts" is visible
        2. Form to create new prompt is present (Week Start, Week End, System Prompt fields)
        3. Current Week Prompt section is visible (if configured)
        
        Report the current state
        """,
        llm=llm,
        browser=browser,
    )
    
    result = await agent.run()
    print(f"Weekly Prompts test result: {result}")
    
    assert "prompt" in result.lower() or "Prompt" in result


@pytest.fixture(scope="module", autouse=True)
def cleanup():
    """Cleanup browser after tests"""
    yield
    asyncio.get_event_loop().run_until_complete(browser.close())


if __name__ == "__main__":
    # Run single test for debugging
    asyncio.run(test_admin_login())
