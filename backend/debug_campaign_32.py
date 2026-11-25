"""
Visual Debugger for Campaign #32
Opens browser window and shows detailed POST detection
"""
import asyncio
from playwright.async_api import async_playwright
import sys

# Set to False to see the browser
HEADLESS = False

async def debug_campaign_32():
    """Debug the form submission with visible browser and detailed logging"""
    
    url = "https://site23359-uw0p89.scloudsite101.com/dummy/contact.html"
    
    print("\n" + "="*80)
    print("🔍 DEBUGGING CAMPAIGN #32 - Visual Mode")
    print("="*80)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()
        
        # Track all network requests
        network_log = []
        
        def log_request(request):
            network_log.append({
                'type': 'request',
                'method': request.method,
                'url': request.url,
                'headers': dict(request.headers)
            })
            if request.method == 'POST':
                print(f"📤 POST REQUEST: {request.url}")
                print(f"   Headers: {dict(request.headers)}")
        
        def log_response(response):
            network_log.append({
                'type': 'response',
                'status': response.status,
                'url': response.url,
            })
            if response.request.method == 'POST':
                print(f"📥 POST RESPONSE: {response.url}")
                print(f"   Status: {response.status}")
                print(f"   Status Text: {response.status_text}")
        
        page.on('request', log_request)
        page.on('response', log_response)
        
        # Navigate to form
        print(f"\n1️⃣ Navigating to: {url}")
        await page.goto(url, wait_until='networkidle')
        print("   ✅ Page loaded")
        
        await page.wait_for_timeout(2000)
        
        # Check form action
        print("\n2️⃣ Inspecting form...")
        form_info = await page.evaluate("""
            () => {
                const form = document.querySelector('form');
                if (!form) return null;
                return {
                    action: form.action,
                    method: form.method,
                    hasAction: form.hasAttribute('action'),
                    actionAttr: form.getAttribute('action')
                };
            }
        """)
        
        if form_info:
            print(f"   Form found:")
            print(f"   - Action: {form_info['action']}")
            print(f"   - Method: {form_info['method']}")
            print(f"   - Has action attribute: {form_info['hasAction']}")
            print(f"   - Action attribute value: '{form_info['actionAttr']}'")
        else:
            print("   ❌ No form found!")
            await browser.close()
            return
        
        # Fill form
        print("\n3️⃣ Filling form fields...")
        try:
            await page.fill("input[name='email']", "test@example.com")
            print("   ✅ Filled email")
            
            await page.fill("input[name='full_name']", "Test User")
            print("   ✅ Filled full name")
            
            await page.fill("textarea[name='message']", "This is a test message")
            print("   ✅ Filled message")
        except Exception as e:
            print(f"   ❌ Error filling: {e}")
        
        await page.wait_for_timeout(1000)
        
        # Find submit button
        print("\n4️⃣ Finding submit button...")
        submit_btn = await page.evaluate("""
            () => {
                const btn = document.querySelector('button[type="submit"]');
                if (!btn) return null;
                return {
                    text: btn.innerText,
                    type: btn.type,
                    tagName: btn.tagName
                };
            }
        """)
        
        if submit_btn:
            print(f"   Submit button found: {submit_btn['text']}")
        else:
            print("   ❌ No submit button found!")
        
        # Clear network log before submit
        network_log.clear()
        
        # Click submit and monitor
        print("\n5️⃣ Clicking submit button...")
        print("   📡 Monitoring network for 12 seconds...")
        
        try:
            await page.click('button[type="submit"]')
            print("   ✅ Submit clicked")
        except Exception as e:
            print(f"   ❌ Click error: {e}")
        
        # Wait and watch for network activity
        await page.wait_for_timeout(12000)
        
        # Analyze network log
        print("\n6️⃣ Network Activity Analysis:")
        print("="*80)
        
        post_requests = [r for r in network_log if r.get('method') == 'POST']
        post_responses = [r for r in network_log if r['type'] == 'response' and any(
            req['url'] == r['url'] and req['method'] == 'POST' 
            for req in network_log if req['type'] == 'request'
        )]
        
        if not post_requests:
            print("❌ NO POST REQUESTS DETECTED!")
            print("\nPossible reasons:")
            print("1. Form action is empty or '#' (submits to same page)")
            print("2. Form uses JavaScript preventDefault()")
            print("3. Form is not properly configured")
        else:
            print(f"✅ Found {len(post_requests)} POST request(s):")
            for req in post_requests:
                print(f"\n   URL: {req['url']}")
                print(f"   Method: {req['method']}")
        
        if post_responses:
            print(f"\n✅ Found {len(post_responses)} POST response(s):")
            for res in post_responses:
                print(f"\n   URL: {res['url']}")
                print(f"   Status: {res['status']}")
        
        # Show all network activity
        print("\n7️⃣ All Network Activity (last 12 seconds):")
        print("-"*80)
        for i, entry in enumerate(network_log, 1):
            if entry['type'] == 'request':
                print(f"{i}. REQUEST  {entry['method']:6} {entry['url']}")
            else:
                print(f"{i}. RESPONSE {entry['status']:3}    {entry['url']}")
        
        # Check current URL
        print("\n8️⃣ Final State:")
        print(f"   Current URL: {page.url}")
        
        print("\n" + "="*80)
        print("✅ Debug complete. Browser will stay open for 30 seconds.")
        print("   Check the browser window to see the form state.")
        print("="*80)
        
        # Keep browser open
        await page.wait_for_timeout(30000)
        
        await browser.close()


if __name__ == "__main__":
    asyncio.run(debug_campaign_32())
