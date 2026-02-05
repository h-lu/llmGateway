"""
Browser-use E2E test for all TeachProxy Admin pages
Using DeepSeek API
"""
import asyncio
import os
from browser_use import Agent, Browser
from browser_use.llm.deepseek.chat import ChatDeepSeek

BASE_URL = "http://localhost:5173"
ADMIN_TOKEN = "_D9PyQ6EvlyNI9Rs_ZdHOijGQQ_6dI2YuvdosTcl4Bc"


async def test_all_pages():
    """Test all admin pages with DeepSeek LLM"""
    
    browser = Browser(
        headless=False,
        window_size={'width': 1400, 'height': 900},
    )
    
    # Use DeepSeek LLM
    llm = ChatDeepSeek(
        model='deepseek-chat',
        temperature=0.1,
    )
    
    try:
        agent = Agent(
            task=f"""
            Complete E2E test of TeachProxy Admin Dashboard:
            
            === LOGIN ===
            1. Go to {BASE_URL}/login
            2. Wait for page to load
            3. Enter Admin Token: {ADMIN_TOKEN}
            4. Click Login button
            5. Wait to be redirected to Dashboard
            
            === TEST DASHBOARD ===
            6. Verify you see "Dashboard" heading
            7. Look for stat cards (Total Students, Conversations Today, etc.)
            8. Check if data is displayed or shows "0"
            
            === TEST STUDENTS PAGE ===
            9. Click "Students" in left sidebar
            10. Wait for page to load
            11. Verify "Students" heading is visible
            12. Check for "Add Student" button
            13. Check if student table/list is displayed
            
            === TEST CONVERSATIONS PAGE ===
            14. Click "Conversations" in left sidebar
            15. Wait for page to load
            16. Verify "Conversations" heading is visible
            17. Check for "Filter by action" dropdown
            18. IMPORTANT: Check if conversation data table is visible or if page is blank
            19. If blank, open browser console (F12) and report any red error messages
            
            === TEST RULES PAGE ===
            20. Click "Rules" in left sidebar
            21. Verify "Rules" heading is visible
            22. Check for rule creation form
            
            === TEST WEEKLY PROMPTS PAGE ===
            23. Click "Weekly Prompts" in left sidebar
            24. Verify "Weekly Prompts" heading is visible
            25. Check for prompt configuration form
            
            === REPORT ===
            For each page report:
            - Page loads correctly (Yes/No)
            - Data is displayed (Yes/No/Empty)
            - Any errors in console (Yes/No, describe if yes)
            
            Give a final summary of all pages.
            """,
            llm=llm,
            browser=browser,
            max_steps=50,
        )
        
        result = await agent.run()
        print("\n" + "=" * 70)
        print("🧪 FULL E2E TEST RESULT:")
        print("=" * 70)
        print(result)
        print("=" * 70)
        
    finally:
        await browser.close()


if __name__ == "__main__":
    print("🚀 Starting complete E2E test with DeepSeek LLM...")
    print("📍 Testing URL:", BASE_URL)
    print("🔑 Admin Token:", ADMIN_TOKEN[:20] + "...")
    print("\n⚠️  A Chrome browser window will open.")
    print("👀 Watch the AI automate the testing!\n")
    
    asyncio.run(test_all_pages())
