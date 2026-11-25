import asyncio
import time
from datetime import datetime, UTC
from typing import List, Dict, Optional, Callable, Any
import logging

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from dbmysql import getconn

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

print("LOADED advanced_scraper_mysql from:", __file__)

# ------------------------ DB helpers ------------------------


def get_pending_websites(limit: int = 1000) -> List[Dict]:
    """Pick websites never processed (timestamp IS NULL)."""
    conn = getconn()
    try:
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute("SELECT id, url FROM websites WHERE timestamp IS NULL AND is_dead = 0 LIMIT %s", (limit,))
            rows = cur.fetchall() or []
            return [{"id": int(r["id"]), "url": r["url"]} for r in rows]
        finally:
            cur.close()
    finally:
        conn.close()


def get_websites_by_ids(website_ids: List[int]) -> List[Dict]:
    if not website_ids:
        return []
    conn = getconn()
    try:
        cur = conn.cursor(dictionary=True)
        try:
            fmt = ",".join(["%s"] * len(website_ids))
            cur.execute(f"SELECT id, url FROM websites WHERE id IN ({fmt})", tuple(int(x) for x in website_ids))
            rows = cur.fetchall() or []
            return [{"id": int(r["id"]), "url": r["url"]} for r in rows]
        finally:
            cur.close()
    finally:
        conn.close()


def update_website_flags(
    website_id: int,
    has_captcha: bool,
    form_found: bool,
    is_dead: bool = False,
    retries: int = 8,
    delay: float = 1.0,
):
    """Always set timestamp so it won’t be picked again."""
    ts = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")

    for attempt in range(retries):
        try:
            conn = getconn()
            cur = conn.cursor()
            try:
                cur.execute(
                    """
                    UPDATE websites
                    SET has_captcha=%s, form_found=%s, is_dead=%s, timestamp=%s
                    WHERE id=%s
                    """,
                    (
                        1 if has_captcha else 0,
                        1 if form_found else 0,
                        1 if is_dead else 0,
                        ts,
                        int(website_id),
                    ),
                )
                conn.commit()
                return
            finally:
                cur.close()
                conn.close()

        except Exception as e:
            msg = str(e).lower()
            if ("lock" in msg or "locked" in msg) and attempt < retries - 1:
                logger.warning("DB locked when updating website %s, retry %s/%s", website_id, attempt + 1, retries)
                time.sleep(delay)
                continue
            raise


def delete_raw_fields_for_website(website_id: int, retries: int = 6, delay: float = 0.5):
    """Optional: avoid duplicate raw_fields rows when re-scraping the same website."""
    for attempt in range(retries):
        try:
            conn = getconn()
            cur = conn.cursor()
            try:
                cur.execute("DELETE FROM raw_fields WHERE website_id=%s", (int(website_id),))
                conn.commit()
                return
            finally:
                cur.close()
                conn.close()
        except Exception as e:
            msg = str(e).lower()
            if ("lock" in msg or "locked" in msg) and attempt < retries - 1:
                time.sleep(delay)
                continue
            # don't crash scrape if delete fails; just log
            logger.warning("Failed deleting old raw_fields for website_id=%s: %s", website_id, e)
            return


def save_raw_field(
    website_id: int,
    tag_name: str,
    field_id: Optional[str],
    field_name: Optional[str],
    field_type: Optional[str],
    placeholder: Optional[str],
    class_name: Optional[str],
    form_id: Optional[str],
    form_class: Optional[str],
):
    """
    Writes to table raw_fields (underscore) as per your DB.
    Expected columns (minimum):
      website_id, tag_name, field_id, field_name, field_type, placeholder, class_name, form_id, form_class
    """
    conn = getconn()
    try:
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO raw_fields
                  (website_id, tag_name, field_id, field_name, field_type, placeholder, class_name, form_id, form_class)
                VALUES
                  (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    int(website_id),
                    tag_name or "",
                    field_id or "",
                    field_name or "",
                    field_type or "",
                    placeholder or "",
                    class_name or "",
                    form_id or "",
                    form_class or "",
                ),
            )
            conn.commit()
        finally:
            cur.close()
    finally:
        conn.close()


# ------------------------ CAPTCHA + navigation helpers ------------------------

CAPTCHA_SELECTORS = [
    "iframe[src*='recaptcha']",
    "div.g-recaptcha",
    "iframe[src*='hcaptcha']",
    "div.h-captcha",
    "div.cf-turnstile",
    "iframe[src*='challenges.cloudflare.com']",
    "iframe[title*='challenge']",
]


async def detect_captcha(page) -> bool:
    for sel in CAPTCHA_SELECTORS:
        loc = page.locator(sel)
        try:
            if await loc.count() > 0:
                return True
        except PlaywrightTimeout:
            continue
        except Exception:
            # ignore selector errors
            continue
    return False


CONTACT_KEYWORDS = [
    "contact",
    "contact us",
    "contact me",
    "get in touch",
    "get in touch with us",
    "reach us",
    "reach out",
    "reach out to us",
    "talk to us",
    "lets talk",
    "support",
    "customer support",
    "help center",
    "help support",
    "request a quote",
    "request quote",
    "book a call",
    "schedule a call",
    "sales",
]


async def find_contact_like_url(page) -> str:
    current = page.url

    # try keyword links first
    for key in CONTACT_KEYWORDS:
        link = page.locator(f"a:visible:text-matches('{key}', 'i')")
        if await link.count() > 0:
            try:
                await link.first.click()
                await page.wait_for_timeout(1500)
                return page.url
            except Exception:
                pass

    # fallback: scan a[href]
    anchors = page.locator("a[href]")
    count = await anchors.count()
    for i in range(min(count, 200)):
        href = await anchors.nth(i).get_attribute("href")
        if not href:
            continue
        lower = href.lower()
        if "contact" in lower or "support" in lower:
            try:
                await anchors.nth(i).click()
                await page.wait_for_timeout(1500)
                return page.url
            except Exception:
                continue

    return current


# ------------------------ form scraping helpers ------------------------


async def extract_forms_and_fields(page, website_id: int) -> int:
    total = 0
    forms = page.locator("form")
    formcount = await forms.count()

    for i in range(formcount):
        form = forms.nth(i)
        form_id = await form.get_attribute("id")
        form_class = await form.get_attribute("class")

        for tag in ["input", "textarea", "select"]:
            elements = form.locator(tag)
            elemcount = await elements.count()

            for j in range(elemcount):
                el = elements.nth(j)
                field_id = await el.get_attribute("id")
                field_name = await el.get_attribute("name")
                field_type = await el.get_attribute("type")
                placeholder = await el.get_attribute("placeholder")
                class_name = await el.get_attribute("class")

                save_raw_field(
                    website_id=website_id,
                    tag_name=tag,
                    field_id=field_id,
                    field_name=field_name,
                    field_type=field_type,
                    placeholder=placeholder,
                    class_name=class_name,
                    form_id=form_id,
                    form_class=form_class,
                )
                total += 1

    return total


# ------------------------ main scrape flow ------------------------


async def processwebsite(page, website: Dict):
    website_id = int(website["id"])
    url = website["url"]
    logger.info("Processing %s %s", website_id, url)

    try:
        # Clear old fields so your DB doesn't grow duplicates when re-scraping
        delete_raw_fields_for_website(website_id)

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            logger.warning("Initial load failed for %s, using partial DOM: %s", url, e)
            await page.wait_for_timeout(5000)

        currenturl = page.url
        if currenturl.startswith("chrome-error://") or currenturl.startswith("chromewebdata"):
            logger.warning("Dead site detected chrome error for %s", url)
            update_website_flags(website_id, False, False, True)
            return

        if await detect_captcha(page):
            logger.info("CAPTCHA detected on %s", url)
            update_website_flags(website_id, True, False, False)
            return

        contacturl = await find_contact_like_url(page)
        if contacturl != url:
            logger.info("Navigating to contact-like page %s", contacturl)
            try:
                await page.goto(contacturl, wait_until="domcontentloaded", timeout=60000)
            except Exception as e:
                logger.warning("Contact page load failed for %s, using partial DOM: %s", contacturl, e)
                await page.wait_for_timeout(5000)

        currenturl = page.url
        if currenturl.startswith("chrome-error://") or currenturl.startswith("chromewebdata"):
            logger.warning("Dead site detected chrome error on contact page for %s", url)
            update_website_flags(website_id, False, False, True)
            return

        totalfields = await extract_forms_and_fields(page, website_id)
        logger.info("Saved %s fields for website %s", totalfields, website_id)
        update_website_flags(website_id, False, totalfields > 0, False)

    except PlaywrightTimeout:
        logger.warning("Timeout loading %s", url)
        update_website_flags(website_id, False, False, False)
    except Exception as e:
        logger.exception("Error processing %s %s", url, e)
        update_website_flags(website_id, False, False, False)


async def scrape_websites_by_ids(
    website_ids: List[int],
    headless: bool = True,
    on_progress: Optional[Callable[[int, int, Dict[str, Any]], None]] = None,
):
    sites = get_websites_by_ids(website_ids)
    if not sites:
        logger.info("No websites found for ids=%s", website_ids)
        return

    total = len(sites)
    done = 0

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page()

        for site in sites:
            await processwebsite(page, site)
            done += 1
            if callable(on_progress):
                try:
                    on_progress(done, total, site)
                except Exception:
                    pass

        await browser.close()


async def main(batchsize: int = 500):
    """Original behavior: scrape pending websites only."""
    sites = get_pending_websites(batchsize)
    if not sites:
        logger.info("No pending websites.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        for site in sites:
            await processwebsite(page, site)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
