#!/usr/bin/env python3
"""
Test the form filler with  localhost test page
This verifies that field detection works properly
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

# Set environment variables
os.environ['HEADLESS'] = 'False'  # Show browser

from form_filler import fill_all_forms

# Localhost test URL
test_url = "http://localhost/contact-form-filler%20-%20latest/test_contact_form.html"

print("""
╔════════════════════════════════════════════════════════════╗
║   Testing Field Detection with Localhost Form             ║
╚════════════════════════════════════════════════════════════╝

Testing URL: {test_url}

This test will:
✓ Use a known good local HTML contact form
✓ Verify field detection works correctly  
✓ Show the browser window so you can see what happens
✓ Test in SCRAPE mode (no submission)

Expected Result:
- Should navigate to localhost page
- Should discover 6 fields: fullname, email, phone, subject, message, contactMethod
- Should map at least email and message
- Status should be 'scraped' (not 'noform')

Starting test...
""".format(test_url=test_url))

test_websites = [
    {
        "website_id": 999,
        "url": test_url,
        "contact_url_override": None
    }
]

def progress_callback(status):
    print(f"[PROGRESS] {status['done']}/{status['total']} - {status.get('currentUrl', 'N/A')}")

try:
    result = fill_all_forms(
        userdata={"websites": test_websites},
        on_progress=progress_callback,
        mode="scrape"
    )
    
    print("\n" + "="*60)
    print("TEST RESULTS")
    print("="*60)
    
    import json
    print(json.dumps(result, indent=2))
    
    if result.get('scraped', 0) > 0:
        print("\n✅ SUCCESS! Field detection is working correctly.")
        print("   If your remote site still shows 'noform', the issue is:")
        print("   1. The remote site has no visible form fields")
        print("   2. The remote site loads forms via complex JavaScript")
        print("   3. The remote site requires user interaction first")
    elif result.get('noform', 0) > 0:
        print("\n❌ FAILED! Field detection not working even on localhost.")
        print("   This indicates a problem with the form_filler.py logic.")
        print("   Check the [DISCOVERY] logs above for details.")
    
    details = result.get('details', [])
    if details:
        detail = details[0]
        mapping = detail.get('mapping', {})
        print(f"\nFields Mapped: {list(mapping.keys())}")
        print(f"Status: {detail.get('status')}")
        print(f"Error: {detail.get('error', 'None')}")
    
except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("Test complete")
print("="*60)
