# contact_only_filler.py
import asyncio
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright, BrowserContext, Page

from db_field_mapping import RawFieldsStore, DBField

logger = logging.getLogger("contact_only_filler")
logger.setLevel(logging.INFO)
if not logger.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(h)

HEADLESS = os.getenv("HEADLESS", "1").strip().lower() not in ("0", "false", "no")
NAV_TIMEOUT_MS = int(os.getenv("NAVTIMEOUTMS", "45000"))
ACTION_TIMEOUT_MS = int(os.getenv("ACTIONTIMEOUTMS", "30000"))
SUBMIT_WAIT_MS = int(os.getenv("SUBMITWAITMS", "15000"))
PER_WEBSITE_TIMEOUT_SEC = int(os.getenv("PERWEBSITETIMEOUTSEC", "130"))

# Strict contact-only
CONTACT_ONLY_WORDS = ["contact", "contact-us", "contactus", "get in touch", "getintouch", "reach us"]
CONTACT_ONLY_PATHS = ["contact", "contact-us", "contactus", "get-in-touch", "reach-us"]

SUCCESS_TEXT_RE = re.compile(
    r"(thank\s*you|message\s*has\s*been\s*sent|we\s*will\s*get\s*back|submitted\s*successfully|received\s*your\s*message)",
    re.I,
)

SKIP_HOSTS_EXACT = {
    "wa.me", "api.whatsapp.com",
    "youtube.com", "www.youtube.com",
    "link.zomato.com",
}


def host(u: str) -> str:
    try:
        return urlparse(u).netloc.lower()
    except Exception:
        return ""


def with_scheme(u: str) -> List[str]:
    u = (u or "").strip()
    if not u:
        return []
    p = urlparse(u)
    if p.scheme:
        alt = u.replace("http://", "https://", 1) if u.startswith("http://") else u.replace("https://", "http://", 1)
        return [u, alt] if alt != u else [u]
    return [f"https://{u}", f"http://{u}"]


async def _post_nav_settle(page: Page) -> None:
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=6000)
    except Exception:
        pass
    try:
        await page.wait_for_timeout(600)
    except Exception:
        pass


def _score_contact_link(text: str, href: str) -> int:
    t = (text or "").strip().lower()
    h = (href or "").strip().lower()
    if not h or h.startswith(("mailto:", "tel:", "javascript:")):
        return -999
    score = 0
    if "contact" in h:
        score += 25
    if "contact" in t:
        score += 25
    for w in CONTACT_ONLY_WORDS:
        if w in t:
            score += 6
        if w in h:
            score += 6
    if any(x in h for x in ("privacy", "terms", "login", "signin", "signup", "register")):
        score -= 10
    return score


async def goto_contact_page_only(page: Page, base_url: str, contact_url_override: Optional[str] = None) -> Optional[str]:
    async def safe_goto(u: str) -> bool:
        for attempt in with_scheme(u):
            try:
                resp = await page.goto(attempt, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
                if resp is not None and int(resp.status or 0) >= 400:
                    continue
                await _post_nav_settle(page)
                return True
            except Exception:
                continue
        return False

    if contact_url_override:
        ok = await safe_goto(contact_url_override)
        return page.url if ok else None

    ok = await safe_goto(base_url)
    if not ok:
        return None

    anchors: List[Dict[str, str]] = []
    try:
        anchors = await page.eval_on_selector_all(
            "a[href]",
            "els => els.map(a => ({ href: a.getAttribute('href') || '', abs: a.href || '', text: (a.innerText || a.textContent || '').trim().slice(0,160)}))",
        )
    except Exception:
        anchors = []

    best_href = None
    best_score = -999
    base_host = host(base_url)
    for a in anchors:
        href_abs = (a.get("abs") or "").strip()
        href_raw = (a.get("href") or "").strip()
        href = href_abs or href_raw
        txt = (a.get("text") or "").strip()
        sc = _score_contact_link(txt, href)
        if sc > best_score and (host(href) in ("", base_host)):
            best_score = sc
            best_href = href_raw or href_abs

    if best_href and best_score >= 15:
        target = urljoin(page.url, best_href)
        ok = await safe_goto(target)
        return page.url if ok else None

    try:
        parsed = urlparse(base_url if urlparse(base_url).scheme else f"https://{base_url}")
        origin = f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        origin = base_url.rstrip("/")

    for p in CONTACT_ONLY_PATHS:
        cand = origin.rstrip("/") + "/" + p.lstrip("/")
        ok = await safe_goto(cand)
        if ok:
            return page.url

    return None


async def detect_captcha(page: Page) -> bool:
    checks = [
        "iframe[src*='recaptcha']",
        "script[src*='recaptcha']",
        "div.g-recaptcha",
        "iframe[src*='hcaptcha']",
        "script[src*='hcaptcha']",
        "div.h-captcha",
        "input[name='g-recaptcha-response']",
        "textarea[name='g-recaptcha-response']",
    ]
    for sel in checks:
        try:
            if await page.locator(sel).count() > 0:
                return True
        except Exception:
            pass
    return False


def build_selector_candidates(dbf: DBField) -> List[str]:
    """
    Build a small set of robust selectors from DB raw_fields row:
      - prefer #id
      - then tag[name=...]
      - then [name=...] (sometimes tag differs)
      - then placeholder contains (last resort)
    """
    tag = (dbf.tag_name or "").strip().lower() or "input"
    fid = (dbf.field_id or "").strip()
    fname = (dbf.field_name or "").strip()
    ph = (dbf.placeholder or "").strip()

    cands: List[str] = []

    if fid:
        # if already '#id' keep it; else add '#id'
        cands.append(fid if fid.startswith("#") else f"#{fid}")

    if fname:
        cands.append(f"{tag}[name='{fname.replace(\"'\", \"\") }']")
        cands.append(f"[name='{fname.replace(\"'\", \"\") }']")

    if ph and len(ph) >= 3:
        safe = ph.replace("'", "")
        cands.append(f"{tag}[placeholder*='{safe}']")
        cands.append(f"[placeholder*='{safe}']")

    return cands


async def fill_clustered_fields(page: Page, db_fields: List[DBField], values_by_cluster: Dict[str, str]) -> Tuple[int, List[str]]:
    """
    For each DBField (already clustered), fill it using user value for its cluster_key.
    """
    filled = 0
    errors: List[str] = []

    # Fill higher-confidence first
    for f in sorted(db_fields, key=lambda x: float(x.cluster_score), reverse=True):
        val = (values_by_cluster.get(f.cluster_key) or "").strip()
        if not val:
            continue

        cands = build_selector_candidates(f)
        ok = False
        last_err = None

        for sel in cands:
            try:
                loc = page.locator(sel).first
                if await loc.count() == 0:
                    continue
                if not await loc.is_visible():
                    continue
                await loc.scroll_into_view_if_needed()
                try:
                    await loc.click(timeout=1500)
                except Exception:
                    pass
                await loc.fill(val, timeout=ACTION_TIMEOUT_MS)
                filled += 1
                ok = True
                break
            except Exception as e:
                last_err = e

        if not ok:
            errors.append(f"{f.cluster_key}: could not fill field_id={f.field_id} field_name={f.field_name} ({last_err})")

    return filled, errors


async def click_submit(page: Page) -> Tuple[bool, str]:
    submit_locators = [
        "form button[type='submit']",
        "form input[type='submit']",
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Submit')",
        "button:has-text('Send')",
        "button:has-text('Message')",
    ]
    for s in submit_locators:
        try:
            loc = page.locator(s).first
            if await loc.count() == 0:
                continue
            if not await loc.is_visible():
                continue
            await loc.scroll_into_view_if_needed()
            await loc.click(timeout=8000)
            return True, ""
        except Exception:
            continue
    return False, "No clickable submit button found"


async def wait_for_post_response(page: Page, base_url: str) -> Tuple[str, Any, Any, int]:
    base_host = host(base_url)

    def predicate(resp) -> bool:
        try:
            req = resp.request
            if req.method != "POST":
                return False
            h = host(req.url)
            return (h == base_host) or h.endswith("." + base_host)
        except Exception:
            return False

    try:
        resp = await page.wait_for_event("response", predicate=predicate, timeout=SUBMIT_WAIT_MS)
        req = resp.request
        statuscode = int(resp.status or 0)

        payload_raw = ""
        try:
            payload_raw = req.post_data or ""
        except Exception:
            payload_raw = ""

        payload: Any = payload_raw
        if isinstance(payload_raw, str) and payload_raw.strip():
            try:
                payload = json.loads(payload_raw)
            except Exception:
                payload = payload_raw

        body: Any = None
        try:
            txt = await resp.text()
            try:
                body = json.loads(txt)
            except Exception:
                body = txt
        except Exception as e:
            body = {"error": f"response body unavailable: {e}"}

        return req.url, payload, body, statuscode
    except Exception:
        return "", None, None, 0


async def success_text_present(page: Page) -> bool:
    try:
        txt = await page.inner_text("body")
        return bool(SUCCESS_TEXT_RE.search(txt or ""))
    except Exception:
        return False


async def process_one_website(
    context: BrowserContext,
    website_id: int,
    url: str,
    values_by_cluster: Dict[str, str],
    contact_url_override: Optional[str] = None,
) -> Dict[str, Any]:
    page = await context.new_page()
    page.set_default_timeout(ACTION_TIMEOUT_MS)

    try:
        if host(url) in SKIP_HOSTS_EXACT:
            return {"websiteid": website_id, "url": url, "status": "skipped", "error": "Skipped host"}

        final_url = await goto_contact_page_only(page, url, contact_url_override)
        if not final_url:
            return {"websiteid": website_id, "url": url, "status": "no", "error": "No contact page found"}

        if await detect_captcha(page):
            return {"websiteid": website_id, "url": final_url, "status": "captcha", "error": "Captcha detected"}

        store = RawFieldsStore(table=os.getenv("RAW_FIELDS_TABLE", "raw_fields"))
        db_fields = store.load_for_website(website_id, min_score=float(os.getenv("CLUSTER_MIN_SCORE", "0.55")))

        if not db_fields:
            return {"websiteid": website_id, "url": final_url, "status": "no", "error": "No clustered fields in DB for this website"}

        filled, fill_errors = await fill_clustered_fields(page, db_fields, values_by_cluster)
        if filled == 0:
            return {"websiteid": website_id, "url": final_url, "status": "no", "error": "No fields were filled", "details": fill_errors[:25]}

        submit_ok, submit_err = await click_submit(page)
        if not submit_ok:
            return {"websiteid": website_id, "url": final_url, "status": "failed", "filledfields": filled, "error": submit_err}

        t0 = time.time()
        req_url, payload, resp_body, statuscode = await wait_for_post_response(page, final_url)
        dt = round(time.time() - t0, 2)

        if await detect_captcha(page):
            return {"websiteid": website_id, "url": final_url, "status": "captcha", "filledfields": filled, "error": "Captcha detected after submit"}

        received = False
        if statuscode and 200 <= statuscode < 400:
            received = True
        if not received and await success_text_present(page):
            received = True

        return {
            "websiteid": website_id,
            "url": final_url,
            "status": "success" if received else "unknown",
            "filledfields": filled,
            "submit_capture_seconds": dt,
            "request_url": req_url,
            "payload": payload,
            "response": resp_body,
            "statuscode": statuscode,
        }

    finally:
        try:
            await page.close()
        except Exception:
            pass


async def run_contact_only_batch(websites: List[Dict[str, Any]], values_by_cluster: Dict[str, str]) -> Dict[str, Any]:
    results: List[Dict[str, Any]] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context()
        context.set_default_timeout(ACTION_TIMEOUT_MS)

        try:
            for w in websites:
                website_id = int(w.get("websiteid") or w.get("website_id") or w.get("id") or 0)
                url = str(w.get("url") or "").strip()
                contact_override = w.get("contact_url_override") or w.get("contactUrlOverride") or None
                if not url or not website_id:
                    continue

                r = await asyncio.wait_for(
                    process_one_website(context, website_id, url, values_by_cluster, contact_override),
                    timeout=PER_WEBSITE_TIMEOUT_SEC,
                )
                results.append(r)

        finally:
            await context.close()
            await browser.close()

    return {
        "total": len(results),
        "success": sum(1 for r in results if r.get("status") == "success"),
        "captcha": sum(1 for r in results if r.get("status") == "captcha"),
        "no": sum(1 for r in results if r.get("status") == "no"),
        "failed": sum(1 for r in results if r.get("status") == "failed"),
        "unknown": sum(1 for r in results if r.get("status") == "unknown"),
        "details": results,
    }


def main() -> None:
    """
    Usage:
      python contact_only_filler.py websites.json values.json

    values.json should be keyed by your cluster_key, e.g.:
      {
        "email": "abc@x.com",
        "first_name": "Gaurav",
        "last_name": "Sharma",
        "full_name": "Gaurav Sharma",
        "phone": "9999999999",
        "message": "Hello..."
      }
    """
    import sys
    if len(sys.argv) < 3:
        raise SystemExit("Usage: python contact_only_filler.py websites.json values.json")

    with open(sys.argv[1], "r", encoding="utf-8") as f:
        websites = json.load(f)

    with open(sys.argv[2], "r", encoding="utf-8") as f:
        values_by_cluster = json.load(f)

    out = asyncio.run(run_contact_only_batch(websites, values_by_cluster))
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
