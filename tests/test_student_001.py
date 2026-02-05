"""
Test student_001 specifically (has conversations)
"""
import asyncio
from playwright.async_api import async_playwright

BASE_URL = "http://localhost:5173"
ADMIN_TOKEN = "_D9PyQ6EvlyNI9Rs_ZdHOijGQQ_6dI2YuvdosTcl4Bc"


async def test_student_001():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Login
        await page.goto(f"{BASE_URL}/login")
        await page.fill("input[type='password']", ADMIN_TOKEN)
        await page.click("button")
        await page.wait_for_timeout(2000)
        
        # Go to students
        await page.goto(f"{BASE_URL}/students")
        await page.wait_for_timeout(2000)
        
        # Find student_001 row and click message button
        rows = await page.locator("table tbody tr").all()
        print(f"Found {len(rows)} student rows")
        
        for i, row in enumerate(rows):
            cells = await row.locator("td").all()
            if len(cells) >= 2:
                name = await cells[0].text_content()
                email = await cells[1].text_content()
                print(f"Row {i}: {name} ({email})")
                
                # Click message button in this row
                msg_button = row.locator("button svg[class*='lucide-message']")
                if await msg_button.count() > 0:
                    print(f"  Clicking message button for {name}...")
                    await msg_button.first.click()
                    await page.wait_for_timeout(3000)
                    
                    # Check content
                    content = await page.content()
                    if "Total: 2" in content or "Total: 2 conversations" in content:
                        print(f"  ✅ SUCCESS: Showing 2 conversations for {name}")
                        await page.screenshot(path=f"/tmp/student_{i}_success.png")
                    elif "No conversations found" in content:
                        print(f"  ❌ FAIL: Showing 'No conversations' for {name}")
                        await page.screenshot(path=f"/tmp/student_{i}_empty.png")
                    else:
                        print(f"  ⚠️ Unknown state for {name}")
                        print(f"     Content preview: {content[:500]}")
                    
                    # Close dialog
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(500)
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_student_001())
