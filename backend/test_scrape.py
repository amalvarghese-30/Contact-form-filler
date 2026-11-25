import sys
import asyncio

# Set Windows event loop policy
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from form_filler import scrapeallforms

async def test_scrape():
    print("Starting scrape test...")
    userdata = {"websites": ["https://example.com"]}
    
    try:
        result = await scrapeallforms(userdata, 1)
        print(f"Scrape result: {result}")
        print("Test completed successfully!")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_scrape())
