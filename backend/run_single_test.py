import asyncio
import sqlite3
from advanced_scraper import process_website, DB_PATH  # reuse your existing code

def main():
    # read id=1 and its URL
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT id, url FROM websites WHERE id = 1")
    row = cur.fetchone()
    conn.close()

    if not row:
        print("❌ No website with id=1 found")
        return

    website_id = row["id"]
    url = row["url"]
    print(f"🔍 Testing single website id={website_id}, url={url}")

    asyncio.run(process_website(website_id, url))

if __name__ == "__main__":
    main()
