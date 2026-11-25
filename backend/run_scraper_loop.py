import asyncio
import time
from scraper import ContactFormScraper

async def continuous_scraper():
    """Run scraper every 5 minutes"""
    scraper = ContactFormScraper(headless=True)
    
    while True:
        print("\n" + "="*60)
        print(f"🔄 Running scraper at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        try:
            await scraper.run(limit=10)
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print("⏳ Waiting 5 minutes before next run...")
        time.sleep(300)

if __name__ == "__main__":
    asyncio.run(continuous_scraper())
