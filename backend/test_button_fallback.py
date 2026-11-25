#!/usr/bin/env python3
"""
Test the button click fallback with headless=false to see it in action
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

os.environ['HEADLESS'] = 'False'  # Show browser

from form_filler import fill_all_forms

test_url = "https://site23359-uw0p89.scloudsite101.com/dummy/index.html"

print(f"""
╔════════════════════════════════════════════════════════════╗
║   Testing Button Click Fallback                           ║
╚════════════════════════════════════════════════════════════╝

URL: {test_url}

Expected Flow:
1. Navigate to contact page (should land on /service)
2. Find no form fields initially
3. 🆕 CLICK "Contact Us Now" button
4. 🆕 Retry field discovery after click
5. Hopefully find form fields!

Watch the browser to see the button click in action...

""")

test_websites = [{"website_id": 1, "url": test_url}]

try:
    result = fill_all_forms(
        userdata={"websites": test_websites},
        mode="scrape"
    )
    
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    
    import json
    print(json.dumps(result, indent=2))
    
    if result.get('scraped', 0) > 0:
        print("\n✅ SUCCESS! Button click fallback worked!")
    elif result.get('noform', 0) > 0:
        print("\n⚠️  Still no form found even after button click")
        print("Check [FALLBACK] logs above to see what happened")
        
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
