"""
Simple browser-use test for debugging
"""
import asyncio
from browser_use import Agent, Browser, BrowserConfig
from langchain_openai import ChatOpenAI

async def test_login():
    """Simple login test with screenshots"""
    
    # Configure browser (headless=False to see what's happening)
    browser = Browser(config=BrowserConfig(
        headless=False,
        disable_security=True,
    ))
    
    # Use GPT-4o-mini for speed/cost
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    try:
        agent = Agent(
            task="""
            Go to http://localhost:5173/login
            
            Wait for the page to load completely.
            
            Take note of:
            1. What is the page title?
            2. Is there a form visible?
            3. What input fields are present?
            4. Is there a login button?
            
            Then enter "_D9PyQ6EvlyNI9Rs_ZdHOijGQQ_6dI2YuvdosTcl4Bc" in the Admin Token field
            and click Login.
            
            Wait for the page to change and report:
            - What URL are you on now?
            - What is the page title?
            - What content is visible?
            """,
            llm=llm,
            browser=browser,
        )
        
        result = await agent.run()
        print("=" * 50)
        print("TEST RESULT:")
        print("=" * 50)
        print(result)
        print("=" * 50)
        
    finally:
        await browser.close()


async def test_conversations_direct():
    """Test conversations page directly"""
    
    browser = Browser(config=BrowserConfig(
        headless=False,
        disable_security=True,
    ))
    
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    
    try:
        agent = Agent(
            task="""
            1. Go to http://localhost:5173/login
            2. Login with token: _D9PyQ6EvlyNI9Rs_ZdHOijGQQ_6dI2YuvdosTcl4Bc
            3. After successful login, navigate to http://localhost:5173/conversations
            4. Wait for the page to fully load (wait 3 seconds)
            5. Open browser console (F12) and check for any red error messages
            6. Take note of what is visible on the page:
               - Is "Conversations" title visible?
               - Is there any table or data displayed?
               - Are there any "Loading" or "No data" messages?
            7. Report back everything you see, especially any errors
            """,
            llm=llm,
            browser=browser,
        )
        
        result = await agent.run()
        print("=" * 50)
        print("CONVERSATIONS TEST RESULT:")
        print("=" * 50)
        print(result)
        print("=" * 50)
        
    finally:
        await browser.close()


if __name__ == "__main__":
    print("Running login test...")
    asyncio.run(test_login())
    
    print("\n\nRunning conversations test...")
    asyncio.run(test_conversations_direct())
