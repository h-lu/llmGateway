"""
Final browser-use test with proper DeepSeek configuration
"""
import asyncio
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Set required API keys
os.environ["DEEPSEEK_API_KEY"] = os.getenv("DEEPSEEK_API_KEY", "")
os.environ["OPENAI_API_KEY"] = "sk-fake-key-for-browser-use"  # browser-use requires this

from browser_use import Agent, Browser
from browser_use.llm.deepseek.chat import ChatDeepSeek

BASE_URL = "http://localhost:5173"
ADMIN_TOKEN = "_D9PyQ6EvlyNI9Rs_ZdHOijGQQ_6dI2YuvdosTcl4Bc"


async def test_with_browser():
    """Run comprehensive test with browser-use"""
    
    browser = Browser(
        headless=False,
        window_size={'width': 1400, 'height': 900},
    )
    
    # Use DeepSeek LLM
    llm = ChatDeepSeek(
        model='deepseek-chat',
        temperature=0.1,
        api_key=os.environ["DEEPSEEK_API_KEY"],
    )
    
    try:
        agent = Agent(
            task=f"""
            TEST TEACHPROXY ADMIN - Report all errors found:
            
            1. LOGIN:
               - Go to {BASE_URL}/login
               - Enter: {ADMIN_TOKEN}
               - Login
               - Check console (F12) for errors
            
            2. STUDENTS PAGE:
               - Click "Students"
               - Click 💬 icon on first student
               - Check if dialog opens correctly
               - Look for any "undefined" or errors
            
            3. CONVERSATIONS PAGE:
               - Click "Conversations"
               - Type "test" in search box
               - Select a student from dropdown
               - Check for errors
            
            4. Check ALL pages for console errors
            
            REPORT:
            - List every error you find
            - Describe what page it's on
            - Note any broken functionality
            """,
            llm=llm,
            browser=browser,
            max_steps=50,
        )
        
        result = await agent.run()
        print("\n" + "=" * 80)
        print("🧪 TEST RESULT:")
        print("=" * 80)
        print(result)
        print("=" * 80)
        return result
        
    finally:
        await browser.stop()


if __name__ == "__main__":
    if not os.environ["DEEPSEEK_API_KEY"]:
        print("❌ DEEPSEEK_API_KEY not found in .env")
        exit(1)
    
    print("🔍 Starting browser-use test with DeepSeek...")
    print(f"API Key: {os.environ['DEEPSEEK_API_KEY'][:20]}...")
    asyncio.run(test_with_browser())
