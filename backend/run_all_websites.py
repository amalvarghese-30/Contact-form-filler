import sqlite3
import asyncio
from advanced_scraper import process_website, DB_PATH

BATCH_SIZE = 1000  # process 1000 URLs per loop


def get_pending_ids(limit: int):
    """
    Get a batch of websites that have not been tried yet.
    Uses form_found = 0 AND has_captcha = 0 as 'pending' flag.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute(
        "SELECT id, url FROM websites WHERE form_found = 0 AND has_captcha = 0 LIMIT ?",
        (limit,)
    )
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


async def main():
    batch = 1
    while True:
        pending = get_pending_ids(BATCH_SIZE)
        if not pending:
            print("✅ All pending websites processed (no form_found = 0 & has_captcha = 0 left).")
            break

        print(f"\n=== Batch {batch} | {len(pending)} websites ===")
        for row in pending:
            await process_website(row["id"], row["url"])
            await asyncio.sleep(0.5)  # small delay between sites
        batch += 1


if __name__ == "__main__":
    asyncio.run(main())
