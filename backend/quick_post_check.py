"""
Quick POST Check - Logs to file
"""
import asyncio
from playwright.async_api import async_playwright

async def check_post():
    url = "https://site23359-uw0p89.scloudsite101.com/dummy/contact.html"
    log_file = open("post_debug_log.txt", "w", encoding="utf-8")
    
    def log(msg):
        print(msg)
        log_file.write(msg + "\n")
        log_file.flush()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        post_detected = []
        
        page.on('request', lambda req: post_detected.append(f"POST: {req.url}") if req.method == "POST" else None)
        page.on('response', lambda res: log(f"RESPONSE {res.status}: {res.url}") if res.request.method == "POST" else None)
        
        log("Navigating...")
        await page.goto(url, wait_until='networkidle')
        
        form_info = await page.evaluate("""() => {
            const form = document.querySelector('form');
            return form ? {action: form.action, method: form.method} : null;
        }""")
        
        log(f"Form: {form_info}")
        
        log("Filling fields...")
        await page.fill("input[name='email']", "test@example.com")
        await page.fill("textarea[name='message']", "Test message")
        
        log("Clicking submit...")
        await page.click('button[type="submit"]')
        
        log("Waiting 10 seconds for POST...")
        await page.wait_for_timeout(10000)
        
        log(f"\nPOST Requests: {len(post_detected)}")
        for p in post_detected:
            log(f"  - {p}")
        
        log(f"\nCurrent URL: {page.url}")
        
        await browser.close()
        log_file.close()

asyncio.run(check_post())
print("\n✅ Log saved to: post_debug_log.txt")
