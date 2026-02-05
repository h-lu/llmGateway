"""
Check for 404 errors and network issues
"""
import asyncio
from playwright.async_api import async_playwright

BASE_URL = "http://localhost:5173"
ADMIN_TOKEN = "_D9PyQ6EvlyNI9Rs_ZdHOijGQQ_6dI2YuvdosTcl4Bc"


async def check_404s():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        all_404s = []
        all_requests = []
        
        def handle_response(response):
            all_requests.append(f"{response.status} {response.url}")
            if response.status == 404:
                all_404s.append(response.url)
        
        page.on("response", handle_response)
        
        # Login and navigate through all pages
        print("🔍 Checking all pages for 404 errors...\n")
        
        pages = ["/login", "/", "/students", "/conversations", "/rules", "/weekly-prompts"]
        
        for path in pages:
            all_404s.clear()
            print(f"📄 Checking {path}...")
            
            if path == "/login":
                await page.goto(f"{BASE_URL}{path}")
                await page.fill("input[type='password']", ADMIN_TOKEN)
                await page.click("button")
            else:
                await page.goto(f"{BASE_URL}{path}")
            
            await page.wait_for_timeout(2000)
            
            if all_404s:
                print(f"   ❌ 404s: {all_404s}")
            else:
                print(f"   ✅ OK")
        
        print("\n" + "=" * 80)
        print("📊 All Requests:")
        print("=" * 80)
        for req in sorted(set(all_requests)):
            if req.startswith("404") or "admin" in req:
                print(req)
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(check_404s())
