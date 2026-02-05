"""
Debug test with browser-use - check for errors in all features
"""
import asyncio
import os
from browser_use import Agent, Browser
from browser_use.llm.deepseek.chat import ChatDeepSeek

BASE_URL = "http://localhost:5173"
ADMIN_TOKEN = "_D9PyQ6EvlyNI9Rs_ZdHOijGQQ_6dI2YuvdosTcl4Bc"


async def debug_all_features():
    """Debug all features and report errors"""
    
    browser = Browser(
        headless=False,
        window_size={'width': 1400, 'height': 900},
    )
    
    llm = ChatDeepSeek(
        model='deepseek-chat',
        temperature=0.1,
    )
    
    try:
        agent = Agent(
            task=f"""
            DEBUG MISSION: Find and report all errors in TeachProxy Admin
            
            === STEP 1: LOGIN ===
            - Go to {BASE_URL}/login
            - Enter token: {ADMIN_TOKEN}
            - Click Login
            - Check browser console (F12) for any red errors
            - Report: Any login errors?
            
            === STEP 2: DASHBOARD ===
            - Check if stats load correctly
            - Look for "undefined" or "NaN" displays
            - Report: Any data display issues?
            
            === STEP 3: STUDENTS PAGE ===
            - Click "Students" in sidebar
            - Wait for page to load
            - Check console for errors
            - Click on a student's 💬 (message) icon
            - Check if student conversations dialog opens
            - Check for any errors in the dialog
            - Report: Student page errors? Dialog errors?
            
            === STEP 4: CONVERSATIONS PAGE ===
            - Click "Conversations" in sidebar
            - Wait for page to load
            - Check console for errors
            - Try typing in search box
            - Try selecting a student from dropdown
            - Check if filters work
            - Click "Export JSON" button
            - Report: Any errors in conversations page?
            
            === STEP 5: RULES PAGE ===
            - Click "Rules" in sidebar
            - Check console for errors
            - Report: Any errors?
            
            === STEP 6: WEEKLY PROMPTS PAGE ===
            - Click "Weekly Prompts" in sidebar
            - Check console for errors
            - Report: Any errors?
            
            === FINAL REPORT ===
            List ALL errors found with:
            1. Page name
            2. Error description
            3. How to reproduce
            4. Screenshot if possible
            """,
            llm=llm,
            browser=browser,
            max_steps=100,
        )
        
        result = await agent.run()
        print("\n" + "=" * 80)
        print("🐛 DEBUG REPORT:")
        print("=" * 80)
        print(result)
        print("=" * 80)
        
    finally:
        await browser.close()


if __name__ == "__main__":
    print("🔍 Starting comprehensive debug with browser-use...")
    print("This will open a browser and check for all errors\n")
    asyncio.run(debug_all_features())
