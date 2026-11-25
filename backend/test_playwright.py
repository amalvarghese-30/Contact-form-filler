import sys
import asyncio

# Set Windows event loop policy
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from playwright.async_api import async_playwright

async def test_playwright():
    print("Starting Playwright test...")
    async with async_playwright() as p:
        print("Launching browser...")
        browser = await p.chromium.launch(headless=True)
        print("Browser launched successfully!")
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://example.com")
        print(f"Page title: {await page.title()}")
        await browser.close()
        print("Test completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_playwright())
