"""
Quick check for specific errors
"""
import asyncio
from playwright.async_api import async_playwright

BASE_URL = "http://localhost:5173"
ADMIN_TOKEN = "_D9PyQ6EvlyNI9Rs_ZdHOijGQQ_6dI2YuvdosTcl4Bc"


async def quick_check():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        errors = []
        page.on("console", lambda msg: msg.type == "error" and errors.append(msg.text))
        page.on("pageerror", lambda err: errors.append(str(err)))
        
        # Login
        await page.goto(f"{BASE_URL}/login")
        await page.fill("input[type='password']", ADMIN_TOKEN)
        await page.click("button")
        await page.wait_for_timeout(2000)
        
        # Check Students
        await page.goto(f"{BASE_URL}/students")
        await page.wait_for_timeout(2000)
        
        # Check if student dialog works
        try:
            msg_button = page.locator("svg[class*='lucide-message-square']").first
            await msg_button.click()
            await page.wait_for_timeout(2000)
            dialog_content = await page.content()
            if "undefined" in dialog_content.lower():
                errors.append("Student dialog shows 'undefined'")
            await page.keyboard.press("Escape")
        except Exception as e:
            errors.append(f"Student dialog error: {e}")
        
        # Check Conversations
        await page.goto(f"{BASE_URL}/conversations")
        await page.wait_for_timeout(2000)
        
        # Try search
        try:
            await page.fill("input[placeholder*='Search' i]", "你好")
            await page.wait_for_timeout(1500)
        except Exception as e:
            errors.append(f"Search error: {e}")
        
        # Check for 404s
        responses = []
        page.on("response", lambda r: responses.append(r) if r.status == 404 else None)
        
        await page.reload()
        await page.wait_for_timeout(3000)
        
        print("\n" + "=" * 80)
        print("🐛 ERRORS FOUND:")
        print("=" * 80)
        
        if errors:
            for i, err in enumerate(set(errors), 1):
                print(f"{i}. {err}")
        else:
            print("✅ No JavaScript errors detected!")
        
        # Check for 404s
        four_oh_fours = [r.url for r in responses if r.status == 404]
        if four_oh_fours:
            print("\n⚠️  404 Errors:")
            for url in set(four_oh_fours):
                print(f"   - {url}")
        
        print("=" * 80)
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(quick_check())
