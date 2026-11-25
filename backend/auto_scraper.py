import asyncio
import time
from scraper import ContactFormScraper

async def auto_scraper():
    """Continuously scrape pending URLs"""
    scraper = ContactFormScraper(headless=True)
    
    while True:
        print(f"\n🔄 Checking for pending URLs at {time.strftime('%H:%M:%S')}")
        await scraper.run(limit=10)
        print("⏳ Waiting 30 seconds...")
        time.sleep(30)

asyncio.run(auto_scraper())
