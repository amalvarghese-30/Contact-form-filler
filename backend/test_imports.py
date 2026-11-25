"""Test if imports work correctly"""
import sys
import asyncio

# Set Windows event loop policy
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

print("Testing imports...")

try:
    from form_filler import fillallforms, scrapeallforms
    print("✅ form_filler imports successful")
    print(f"   fillallforms: {fillallforms}")
    print(f"   scrapeallforms: {scrapeallforms}")
except Exception as e:
    print(f"❌ form_filler import failed: {e}")
    import traceback
    traceback.print_exc()

try:
    from advanced_scraper_mysql import scrape_websites_by_ids
    print("✅ advanced_scraper_mysql import successful")
    print(f"   scrape_websites_by_ids: {scrape_websites_by_ids}")
except Exception as e:
    print(f"❌ advanced_scraper_mysql import failed: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*50)
print("Testing if scrapeallforms is callable...")
print("="*50)

async def test_call():
    try:
        print("Calling scrapeallforms with test data...")
        result = await scrapeallforms({"websites": ["https://example.com"]}, 1)
        print(f"✅ scrapeallforms executed successfully!")
        print(f"Result type: {type(result)}")
        if isinstance(result, dict):
            print(f"Result keys: {result.keys()}")
            print(f"Status: {result.get('status')}")
        return result
    except Exception as e:
        print(f"❌ scrapeallforms failed: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("\nRunning async test...")
    result = asyncio.run(test_call())
    print(f"\nFinal result: {result}")
