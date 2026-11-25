import asyncio
import sqlite3
from datetime import datetime
import logging
from typing import Dict, List, Optional
import re

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DB_PATH = "../data/urls.db"

class ContactFormScraper:
    def __init__(self, headless: bool = True, timeout: int = 30000):
        self.headless = headless
        self.timeout = timeout
        self.processed_count = 0
        self.error_count = 0

    async def get_pending_urls(self, limit: int = 10) -> List[Dict]:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(
            "SELECT id, url FROM company_urls WHERE status = 'pending' LIMIT ?",
            (limit,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    async def update_url_status(
        self, url_id: int, status: str, error_msg: Optional[str] = None
    ):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        if error_msg:
            cur.execute(
                "UPDATE company_urls "
                "SET status = ?, error_message = ?, processed_at = ? "
                "WHERE id = ?",
                (status, error_msg, datetime.now(), url_id),
            )
        else:
            cur.execute(
                "UPDATE company_urls "
                "SET status = ?, processed_at = ? "
                "WHERE id = ?",
                (status, datetime.now(), url_id),
            )
        conn.commit()
        conn.close()

    async def save_form_fields(self, url_id: int, fields: List[Dict]):
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        for f in fields:
            try:
                cur.execute(
                    """
                    INSERT INTO form_fields
                    (url_id, field_name, field_type, normalized_name, placeholder, is_required)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        url_id,
                        f.get("name"),
                        f.get("type"),
                        f.get("normalized_name"),
                        f.get("placeholder"),
                        f.get("is_required", False),
                    ),
                )
            except Exception as e:
                logger.error(f"Error saving field {f.get('name')}: {e}")
        conn.commit()
        conn.close()

    def normalize_field_name(self, name: str) -> str:
        name = name.lower().strip()
        name = re.sub(r"[^a-z0-9]+", "_", name)
        name = re.sub(r"^_|_$", "", name)
        return name

    async def extract_forms(self, page) -> List[Dict]:
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except PlaywrightTimeout:
            logger.warning("Page load timeout, continuing anyway")

        elements = await page.query_selector_all("form input, form textarea, form select")
        fields = []
        for el in elements:
            try:
                field_type = await el.get_attribute("type") or "text"
                field_name = (
                    await el.get_attribute("name")
                    or await el.get_attribute("id")
                    or "unknown"
                )
                placeholder = await el.get_attribute("placeholder") or ""
                is_required = await el.get_attribute("required") is not None
                fields.append(
                    {
                        "name": field_name,
                        "type": field_type,
                        "normalized_name": self.normalize_field_name(field_name),
                        "placeholder": placeholder,
                        "is_required": is_required,
                    }
                )
            except Exception as e:
                logger.error(f"Error extracting field: {e}")
        return fields

    async def has_captcha(self, page) -> bool:
        indicators = [
            "g-recaptcha",
            "g_recaptcha",
            "recaptcha",
            "h-captcha",
            "cloudflare",
            "captcha",
            "hcaptcha",
        ]
        html = await page.content()
        html_l = html.lower()
        return any(ind in html_l for ind in indicators)

    async def scrape_url(self, url: str, url_id: int):
        async with async_playwright() as p:
            browser = None
            try:
                logger.info(f"Starting: {url}")
                browser = await p.chromium.launch(headless=self.headless)
                ctx = await browser.new_context()
                page = await ctx.new_page()
                await page.set_extra_http_headers(
                    {
                        "User-Agent": (
                            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                            "AppleWebKit/537.36"
                        )
                    }
                )

                try:
                    await page.goto(url, wait_until="load", timeout=self.timeout)
                except PlaywrightTimeout:
                    logger.warning(f"Timeout loading {url}")
                    await self.update_url_status(url_id, "pending", "Timeout")
                    return
                except Exception as e:
                    logger.error(f"Navigation error {url}: {e}")
                    await self.update_url_status(url_id, "pending", str(e))
                    return

                if await self.has_captcha(page):
                    logger.warning(f"CAPTCHA detected on {url}")
                    await self.update_url_status(url_id, "captcha", "CAPTCHA detected")
                    self.processed_count += 1
                    return

                fields = await self.extract_forms(page)
                if fields:
                    logger.info(f"✅ Found {len(fields)} form fields on {url}")
                    await self.save_form_fields(url_id, fields)
                    await self.update_url_status(url_id, "completed")
                else:
                    logger.warning(f"No forms found on {url}")
                    await self.update_url_status(
                        url_id, "completed", "No forms found"
                    )
                self.processed_count += 1

                await ctx.close()
            except Exception as e:
                logger.error(f"Error scraping {url}: {e}")
                await self.update_url_status(url_id, "pending", str(e))
                self.error_count += 1
            finally:
                if browser:
                    await browser.close()

    async def run(self, limit: int = 10):
        logger.info("=" * 60)
        logger.info("Contact Form Scraper Starting")
        logger.info("=" * 60)

        pending = await self.get_pending_urls(limit)
        if not pending:
            logger.info("No pending URLs to process")
            return

        logger.info(f"Found {len(pending)} pending URLs")
        for item in pending:
            await self.scrape_url(item["url"], item["id"])
            await asyncio.sleep(2)

        logger.info("=" * 60)
        logger.info(f"Processing Complete!")
        logger.info(f"Processed: {self.processed_count}")
        logger.info(f"Errors: {self.error_count}")
        logger.info("=" * 60)

async def main():
    scraper = ContactFormScraper(headless=True)
    await scraper.run(limit=50)  # or any batch size you like

if __name__ == "__main__":
    asyncio.run(main())
