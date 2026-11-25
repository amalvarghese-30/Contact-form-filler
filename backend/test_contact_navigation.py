#!/usr/bin/env python3
"""
Test script for contact page navigation and field discovery improvements
Usage: python test_contact_navigation.py
"""

import asyncio
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from form_filler import fill_all_forms

# Test URL from the logs
test_url = "https://site23359-uw0p89.scloudsite101.com/dummy/index.html"

print("""
╔════════════════════════════════════════════════════════════╗
║   Contact Form Navigation & Field Detection Test          ║
╚════════════════════════════════════════════════════════════╝

Testing URL: {test_url}

Expected improvements:
✓ Expanded contact page paths (24 variations)
✓ Better dynamic content waiting (networkidle + 2s)
✓ Enhanced iframe field detection
✓ Comprehensive debug logging

Running test in SCRAPE mode (no submission)...
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
    print(f"[PROGRESS] {status['done']}/{status['total']} - Current: {status.get('currentUrl', 'N/A')}")

# Run in scrape mode to test navigation and field discovery only
try:
    result = fill_all_forms(
        userdata={"websites": test_websites},
        on_progress=progress_callback,
        mode="scrape"  # Discovery only, no submission
    )
    
    print("\n" + "="*60)
    print("TEST RESULTS")
    print("="*60)
    
    if isinstance(result, dict):
        print(f"\nStatus: {result.get('mode', 'N/A')}")
        print(f"Total: {result.get('total', 0)}")
        print(f"Scraped: {result.get('scraped', 0)}")
        print(f"No Form: {result.get('noform', 0)}")
        
        details = result.get('details', [])
        if details:
            for detail in details:
                print(f"\n--- Website {detail.get('website_id')} ---")
                print(f"URL: {detail.get('url')}")
                print(f"Contact URL: {detail.get('contacturl')}")
                print(f"Status: {detail.get('status')}")
                print(f"Filled Fields: {detail.get('filled_fields')}")
                
                mapping = detail.get('mapping', {})
                if mapping:
                    print(f"✓ Field Mapping Found: {list(mapping.keys())}")
                else:
                    print(f"✗ No field mapping")
                
                error = detail.get('error')
                if error:
                    print(f"Error: {error}")
        
        # Interpretation
        print("\n" + "="*60)
        if result.get('scraped', 0) > 0:
            print("✅ SUCCESS! Fields were discovered and mapped correctly.")
        elif result.get('noform', 0) > 0:
            print("⚠️  NO FORM DETECTED - Check logs above for details:")
            print("   - Did it navigate to the correct contact page?")
            print("   - Were fields found but not mapped?")
            print("   - Check [DISCOVERY] logs for field counts")
        else:
            print("❓ Unexpected result - check logs")
            
except Exception as e:
    print(f"\n❌ TEST FAILED WITH ERROR:")
    print(f"   {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "="*60)
print("Test complete. Review logs above for detailed execution flow.")
print("="*60)
