#!/usr/bin/env python3
"""
Debug script to investigate field detection issues
This script will run the form filler with visible browser and enhanced logging
"""

import asyncio
import sys
import os
import logging

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Import AFTER setting up logging
os.environ['HEADLESS'] = 'False'  # Show browser window
os.environ['DEBUG_FIELD_REPORT'] = 'True'

from form_filler import fill_all_forms

# Test URL from the logs
test_url = "https://site23359-uw0p89.scloudsite101.com/dummy/index.html"

print("""
╔════════════════════════════════════════════════════════════╗
║   Debug: Contact Form Field Detection                     ║
╚════════════════════════════════════════════════════════════╝

Testing URL: {test_url}

This will:
✓ Open browser VISIBLY (HEADLESS=False)
✓ Show detailed debug logs
✓ Pause to let you inspect the page manually

Watch the browser window to see:
- Which page it navigates to
- What forms/fields are visible
- Any dynamic content loading

Press Ctrl+C to stop if needed.
""".format(test_url=test_url))

# Prepare test data
test_websites = [
    {
        "website_id": 1,
        "url": test_url,
        "contact_url_override": None
    }
]

def progress_callback(status):
    print(f"\n{'='*60}")
    print(f"[PROGRESS] {status['done']}/{status['total']}")
    print(f"Current URL: {status.get('currentUrl', 'N/A')}")
    print(f"Status: Success={status.get('success', 0)} Failed={status.get('failed', 0)} Captcha={status.get('captcha', 0)}")
    print(f"{'='*60}\n")

# Run in scrape mode
try:
    print("\n🚀 Starting form filler with visible browser...\n")
    
    result = fill_all_forms(
        userdata={"websites": test_websites},
        on_progress=progress_callback,
        mode="scrape"  # Discovery only
    )
    
    print("\n" + "="*60)
    print("FINAL RESULTS")
    print("="*60)
    
    if isinstance(result, dict):
        import json
        print(json.dumps(result, indent=2))
        
        details = result.get('details', [])
        if details:
            for detail in details:
                print(f"\n{'='*60}")
                print(f"Website {detail.get('website_id')}")
                print(f"{'='*60}")
                print(f"Final URL: {detail.get('url')}")
                print(f"Contact URL: {detail.get('contacturl')}")
                print(f"Status: {detail.get('status')}")
                
                mapping = detail.get('mapping', {})
                if mapping:
                    print(f"\n✅ FIELD MAPPING:")
                    for key, value in mapping.items():
                        print(f"  {key}: {value}")
                else:
                    print(f"\n❌ NO FIELD MAPPING")
                
                error = detail.get('error')
                if error:
                    print(f"\nError: {error}")
        
        print("\n" + "="*60)
        print("INTERPRETATION")
        print("="*60)
        
        if result.get('scraped', 0) > 0:
            print("✅ SUCCESS - Fields discovered and mapped")
        elif result.get('noform', 0) > 0:
            print("❌ NO FORM - No fields detected")
            print("\nPossible reasons:")
            print("1. Page has no form fields")
            print("2. Fields are hidden/not visible")
            print("3. Fields are in an iframe we couldn't access")
            print("4. Page requires user interaction first (e.g., click a button)")
            print("5. JavaScript didn't finish rendering")
        
        print(f"\nCheck the logs above for [DISCOVERY] messages")
        print(f"Also check what you saw in the browser window")
            
except KeyboardInterrupt:
    print("\n\n⚠️  Interrupted by user")
except Exception as e:
    print(f"\n❌ ERROR:")
    print(f"   {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("Debug session complete")
print("="*60)
