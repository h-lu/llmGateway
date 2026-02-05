"""
Test student dialog data flow
"""
import asyncio
from playwright.async_api import async_playwright

BASE_URL = "http://localhost:5173"
ADMIN_TOKEN = "_D9PyQ6EvlyNI9Rs_ZdHOijGQQ_6dI2YuvdosTcl4Bc"


async def test_student_dialog():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Capture network requests
        api_responses = []
        
        def handle_response(response):
            if '/conversations/student/' in response.url:
                api_responses.append({
                    'url': response.url,
                    'status': response.status,
                })
        
        page.on("response", handle_response)
        
        # Capture console logs
        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        
        # Login
        print("🔑 Logging in...")
        await page.goto(f"{BASE_URL}/login")
        await page.fill("input[type='password']", ADMIN_TOKEN)
        await page.click("button")
        await page.wait_for_timeout(2000)
        
        # Go to students
        print("👥 Going to Students page...")
        await page.goto(f"{BASE_URL}/students")
        await page.wait_for_timeout(2000)
        
        # Click first student message icon
        print("💬 Clicking message icon...")
        msg_buttons = await page.locator("button svg[class*='lucide-message']").all()
        if msg_buttons:
            await msg_buttons[0].click()
            await page.wait_for_timeout(3000)
            
            # Check API response
            print("\n📡 API Responses:")
            for resp in api_responses:
                print(f"  {resp['status']} {resp['url']}")
            
            # Check dialog content
            content = await page.content()
            
            print("\n🔍 Dialog Content Check:")
            if "No conversations found" in content:
                print("  ❌ Showing: 'No conversations found'")
            elif "Total:" in content and "conversations" in content:
                print("  ✅ Showing conversation count")
            else:
                print("  ⚠️ Unknown state")
            
            # Check for loading state
            if "Loading conversations" in content:
                print("  ⏳ Still loading...")
            
            print("\n📝 Console Logs:")
            for log in console_logs[-10:]:
                if 'conversations' in log.lower() or 'error' in log.lower():
                    print(f"  {log}")
        else:
            print("❌ No message buttons found")
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_student_dialog())
