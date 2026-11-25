"""
Check for JavaScript that might block form submission
"""
import asyncio
from playwright.async_api import async_playwright

async def check_js():
    url = "https://site23359-uw0p89.scloudsite101.com/dummy/contact.html"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto(url, wait_until='networkidle')
        
        # Check for JavaScript event listeners and validation
        js_info = await page.evaluate("""
            () => {
                const form = document.querySelector('form');
                const submit_btn = document.querySelector('button[type="submit"]');
                
                return {
                    formHasSubmitListener: form && form.onsubmit !== null,
                    formHasEventListeners: form && getEventListeners(form).submit ? getEventListeners(form).submit.length : 'N/A',
                    buttonHasClickListener: submit_btn && submit_btn.onclick !== null,
                    formHTML: form ? form.outerHTML.substring(0, 500) : null,
                    scripts: Array.from(document.querySelectorAll('script')).map(s => ({
                        src: s.src || 'inline',
                        content: s.src ? null : s.innerHTML.substring(0, 200)
                    }))
                };
            }
        """)
        
        print("JavaScript Analysis:")
        print("="*80)
        print(f"Form has onsubmit: {js_info['formHasSubmitListener']}")
        print(f"Button has onclick: {js_info['buttonHasClickListener']}")
        print(f"\nScripts on page:")
        for i, script in enumerate(js_info['scripts'], 1):
            print(f"{i}. {script['src']}")
            if script['content']:
                print(f"   Content: {script['content'][:100]}...")
        
        print(f"\nForm HTML:")
        print(js_info['formHTML'])
        
        await browser.close()

asyncio.run(check_js())
