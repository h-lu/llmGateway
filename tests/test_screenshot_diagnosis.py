"""
Screenshot diagnosis - capture each page and check console errors
"""
import asyncio
from playwright.async_api import async_playwright

BASE_URL = "http://localhost:5173"
ADMIN_TOKEN = "_D9PyQ6EvlyNI9Rs_ZdHOijGQQ_6dI2YuvdosTcl4Bc"


async def diagnose():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={'width': 1400, 'height': 900})
        
        all_errors = []
        
        # Capture console errors
        def handle_console(msg):
            if msg.type == 'error':
                all_errors.append(f"[{msg.type}] {msg.text}")
        
        page.on("console", handle_console)
        
        # Capture page errors
        def handle_page_error(err):
            all_errors.append(f"[page error] {err}")
        
        page.on("pageerror", handle_page_error)
        
        try:
            # Login
            print("📸 Testing Login...")
            await page.goto(f"{BASE_URL}/login")
            await page.wait_for_timeout(2000)
            await page.screenshot(path="/tmp/debug_01_login.png")
            
            await page.fill("input[type='password']", ADMIN_TOKEN)
            await page.click("button:has-text('Login')")
            await page.wait_for_timeout(3000)
            await page.screenshot(path="/tmp/debug_02_dashboard.png")
            
            # Students page
            print("📸 Testing Students...")
            await page.click("text=Students")
            await page.wait_for_timeout(3000)
            await page.screenshot(path="/tmp/debug_03_students.png")
            
            # Click on first student conversation icon
            msg_buttons = await page.locator("button svg[class*='lucide-message']").all()
            if msg_buttons:
                await msg_buttons[0].click()
                await page.wait_for_timeout(3000)
                await page.screenshot(path="/tmp/debug_04_student_dialog.png")
            
            # Close dialog if open
            try:
                await page.keyboard.press("Escape")
                await page.wait_for_timeout(500)
            except:
                pass
            
            # Conversations page
            print("📸 Testing Conversations...")
            await page.click("text=Conversations")
            await page.wait_for_timeout(3000)
            await page.screenshot(path="/tmp/debug_05_conversations.png")
            
            # Try search
            try:
                await page.fill("input[placeholder*='Search']", "test")
                await page.wait_for_timeout(1500)
                await page.screenshot(path="/tmp/debug_06_search.png")
            except Exception as e:
                print(f"Search error: {e}")
            
            # Try student filter
            try:
                await page.click("text=All Students")
                await page.wait_for_timeout(1000)
                await page.screenshot(path="/tmp/debug_07_filter.png")
            except Exception as e:
                print(f"Filter error: {e}")
            
            # Rules page
            print("📸 Testing Rules...")
            await page.click("text=Rules")
            await page.wait_for_timeout(3000)
            await page.screenshot(path="/tmp/debug_08_rules.png")
            
            # Weekly Prompts page
            print("📸 Testing Weekly Prompts...")
            await page.click("text=Weekly Prompts")
            await page.wait_for_timeout(3000)
            await page.screenshot(path="/tmp/debug_09_prompts.png")
            
        except Exception as e:
            print(f"Test error: {e}")
            await page.screenshot(path="/tmp/debug_error.png")
        
        finally:
            print("\n" + "=" * 80)
            print("🐛 CONSOLE ERRORS FOUND:")
            print("=" * 80)
            if all_errors:
                for i, err in enumerate(all_errors[:20], 1):
                    print(f"{i}. {err}")
            else:
                print("No console errors detected!")
            print("=" * 80)
            
            print("\n📸 Screenshots saved:")
            for i in range(1, 10):
                print(f"  - /tmp/debug_0{i}_*.png")
            
            await browser.close()


if __name__ == "__main__":
    print("🔍 Running screenshot diagnosis...")
    asyncio.run(diagnose())
