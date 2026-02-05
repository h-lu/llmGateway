"""
Pure Playwright E2E test for all pages (no LLM required)
"""
import asyncio
from playwright.async_api import async_playwright

BASE_URL = "http://localhost:5173"
ADMIN_TOKEN = "_D9PyQ6EvlyNI9Rs_ZdHOijGQQ_6dI2YuvdosTcl4Bc"


async def test_all_pages():
    """Test all admin pages using Playwright directly"""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=100)
        page = await browser.new_page(viewport={'width': 1400, 'height': 900})
        
        # Capture console logs
        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"[{msg.type}] {msg.text}"))
        
        results = []
        
        try:
            # ===== LOGIN =====
            print("\n🔑 Testing Login...")
            await page.goto(f"{BASE_URL}/login")
            await page.wait_for_load_state("networkidle")
            
            # Fill login form
            await page.fill("input[type='password']", ADMIN_TOKEN)
            await page.click("button:has-text('Login')")
            
            # Wait for redirect
            await page.wait_for_url(f"{BASE_URL}/", timeout=10000)
            print("✅ Login successful")
            results.append(("Login", "✅ Pass", "Redirected to Dashboard"))
            
            # ===== DASHBOARD =====
            print("\n📊 Testing Dashboard...")
            await page.wait_for_selector("text=Dashboard")
            dashboard_content = await page.content()
            
            has_stats = "Total Students" in dashboard_content or "Conversations Today" in dashboard_content
            results.append(("Dashboard", "✅ Pass" if has_stats else "⚠️ Empty", "Stats cards visible" if has_stats else "No stats displayed"))
            print(f"{'✅' if has_stats else '⚠️'} Dashboard loaded")
            
            # ===== STUDENTS PAGE =====
            print("\n👥 Testing Students...")
            await page.click("text=Students")
            await page.wait_for_url(f"{BASE_URL}/students")
            await page.wait_for_load_state("networkidle")
            
            students_content = await page.content()
            has_students = "Students" in students_content and "Add Student" in students_content
            results.append(("Students", "✅ Pass" if has_students else "❌ Fail", "Page loaded with Add Student button" if has_students else "Missing elements"))
            print(f"{'✅' if has_students else '❌'} Students page loaded")
            
            # Take screenshot
            await page.screenshot(path="/tmp/students.png")
            
            # ===== CONVERSATIONS PAGE =====
            print("\n💬 Testing Conversations...")
            await page.click("text=Conversations")
            await page.wait_for_url(f"{BASE_URL}/conversations")
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)  # Extra wait for data
            
            conversations_content = await page.content()
            has_conv_title = "Conversations" in conversations_content
            has_filter = "Filter by action" in conversations_content
            has_table = "<table" in conversations_content or "No conversations" in conversations_content
            
            # Check for errors in console
            errors = [log for log in console_logs if log.startswith("[error]")]
            
            if errors:
                status = "❌ Error"
                detail = f"Console errors: {errors[:3]}"
            elif not has_conv_title:
                status = "❌ Fail"
                detail = "Page title not found"
            elif not has_table:
                status = "⚠️ Empty"
                detail = "No table/data displayed"
            else:
                status = "✅ Pass"
                detail = "Page loaded with data"
            
            results.append(("Conversations", status, detail))
            print(f"{status} Conversations page - {detail}")
            
            # Take screenshot
            await page.screenshot(path="/tmp/conversations.png")
            
            # ===== RULES PAGE =====
            print("\n🛡️ Testing Rules...")
            await page.click("text=Rules")
            await page.wait_for_url(f"{BASE_URL}/rules")
            await page.wait_for_load_state("networkidle")
            
            rules_content = await page.content()
            has_rules = "Rules" in rules_content and ("Create New Rule" in rules_content or "Pattern" in rules_content)
            results.append(("Rules", "✅ Pass" if has_rules else "❌ Fail", "Form visible" if has_rules else "Missing form"))
            print(f"{'✅' if has_rules else '❌'} Rules page loaded")
            
            await page.screenshot(path="/tmp/rules.png")
            
            # ===== WEEKLY PROMPTS PAGE =====
            print("\n📅 Testing Weekly Prompts...")
            await page.click("text=Weekly Prompts")
            await page.wait_for_url(f"{BASE_URL}/weekly-prompts")
            await page.wait_for_load_state("networkidle")
            
            prompts_content = await page.content()
            has_prompts = "Weekly Prompts" in prompts_content
            results.append(("Weekly Prompts", "✅ Pass" if has_prompts else "❌ Fail", "Page loaded" if has_prompts else "Not found"))
            print(f"{'✅' if has_prompts else '❌'} Weekly Prompts page loaded")
            
            await page.screenshot(path="/tmp/weekly_prompts.png")
            
        except Exception as e:
            print(f"\n❌ Test error: {e}")
            results.append(("Error", "❌ Fail", str(e)))
            
        finally:
            # Print results
            print("\n" + "=" * 70)
            print("🧪 E2E TEST RESULTS:")
            print("=" * 70)
            print(f"{'Page':<20} {'Status':<10} {'Details'}")
            print("-" * 70)
            for page_name, status, detail in results:
                print(f"{page_name:<20} {status:<10} {detail}")
            print("=" * 70)
            
            # Print console errors
            if console_logs:
                print("\n📝 Console Logs:")
                for log in console_logs[-10:]:  # Last 10 logs
                    print(f"  {log}")
            
            print("\n📸 Screenshots saved:")
            print("  - /tmp/students.png")
            print("  - /tmp/conversations.png")
            print("  - /tmp/rules.png")
            print("  - /tmp/weekly_prompts.png")
            
            await browser.close()


if __name__ == "__main__":
    print("🚀 Starting Playwright E2E tests...")
    print(f"📍 URL: {BASE_URL}")
    print("👀 Watch the browser window!\n")
    
    asyncio.run(test_all_pages())
