"""
Browser-use E2E test for TeachProxy Admin
Based on context7 docs: /browser-use/browser-use
"""
import asyncio
import os
from browser_use import Agent, Browser, ChatOpenAI

BASE_URL = "http://localhost:5173"
ADMIN_TOKEN = "_D9PyQ6EvlyNI9Rs_ZdHOijGQQ_6dI2YuvdosTcl4Bc"


async def test_conversations_page():
    """Test conversations page using browser-use"""
    
    # Configure browser (headless=False to see the browser)
    browser = Browser(
        headless=False,
        window_size={'width': 1280, 'height': 800},
    )
    
    # Use ChatBrowserUse LLM (requires BROWSER_USE_API_KEY)
    llm = ChatOpenAI(model='gpt-4o-mini')
    
    try:
        agent = Agent(
            task=f"""
            1. Go to {BASE_URL}/login
            2. Login with token: {ADMIN_TOKEN}
            3. After successful login, click on "Conversations" in the left sidebar
            4. Wait for the page to fully load
            
            Debug steps:
            - Open browser console (F12) and check for red error messages
            - Look at the network tab for any failed API requests
            
            Verify and report:
            - Is the "Conversations" heading visible?
            - Is there a "Filter by action" dropdown?
            - Is there any table showing conversation data?
            - OR does it say "No conversations found" or "Loading..."?
            - Are there any error messages in the console?
            
            If the page is empty or shows errors, describe exactly what you see.
            """,
            llm=llm,
            browser=browser,
        )
        
        result = await agent.run()
        print("=" * 60)
        print("CONVERSATIONS PAGE TEST RESULT:")
        print("=" * 60)
        print(result)
        print("=" * 60)
        
    finally:
        await browser.close()


async def test_admin_login():
    """Test admin login flow"""
    
    browser = Browser(
        headless=False,
        window_size={'width': 1280, 'height': 800},
    )
    
    llm = ChatOpenAI(model='gpt-4o-mini')
    
    try:
        agent = Agent(
            task=f"""
            Go to {BASE_URL}/login
            
            Wait for the page to fully load.
            
            You should see:
            - A page titled "TeachProxy Admin"
            - An input field labeled "Admin Token"
            - A "Login" button
            
            Steps:
            1. Click on the Admin Token input field
            2. Type the token: {ADMIN_TOKEN}
            3. Click the Login button
            4. Wait for the page to change
            
            Verify:
            - What is the new URL?
            - Is there a "Dashboard" heading visible?
            - Can you see stats cards (Total Students, Conversations Today, etc.)?
            
            Report success or failure with details.
            """,
            llm=llm,
            browser=browser,
        )
        
        result = await agent.run()
        print("=" * 60)
        print("LOGIN TEST RESULT:")
        print("=" * 60)
        print(result)
        print("=" * 60)
        
    finally:
        await browser.close()


async def test_all_pages():
    """Test all admin pages"""
    
    browser = Browser(
        headless=False,
        window_size={'width': 1280, 'height': 800},
    )
    
    llm = ChatOpenAI(model='gpt-4o-mini')
    
    try:
        agent = Agent(
            task=f"""
            Complete navigation test of TeachProxy Admin:
            
            1. Login at {BASE_URL}/login with token: {ADMIN_TOKEN}
            
            2. Test each page by clicking sidebar links:
               - Dashboard: Check for stats cards
               - Students: Check for "Add Student" button and student list
               - Conversations: Check for conversation table
               - Rules: Check for rule creation form
               - Weekly Prompts: Check for prompt configuration
            
            For each page, verify:
            - Page title is visible
            - Main content loads (not blank)
            - No error messages in console (check F12)
            
            Report any pages that are blank or show errors.
            """,
            llm=llm,
            browser=browser,
        )
        
        result = await agent.run()
        print("=" * 60)
        print("FULL NAVIGATION TEST RESULT:")
        print("=" * 60)
        print(result)
        print("=" * 60)
        
    finally:
        await browser.close()


if __name__ == "__main__":
    import sys
    
    # Check for API key
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY not set.")
        print("Set it with: export OPENAI_API_KEY='your-openai-key'")
        print("\nContinuing anyway...\n")
    
    print("🚀 Starting browser-use tests...")
    print("A Chrome browser window will open. Watch the automation!\n")
    
    # Run specific test
    if len(sys.argv) > 1:
        if sys.argv[1] == "login":
            asyncio.run(test_admin_login())
        elif sys.argv[1] == "conversations":
            asyncio.run(test_conversations_page())
        elif sys.argv[1] == "all":
            asyncio.run(test_all_pages())
    else:
        # Default: test conversations page
        print("Testing conversations page (the one reported as empty)...")
        asyncio.run(test_conversations_page())
