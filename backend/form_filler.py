import asyncio
import json
import logging
import os
import re
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import parse_qs, parse_qsl, urlencode, urljoin, urlparse, urlunparse

# Fix for Windows: Set event loop policy for subprocess support (required for Playwright)
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from playwright.async_api import async_playwright, Browser, BrowserContext, Frame, Locator, Page

# ---------- OPTIONAL MySQL ----------
try:
    import mysql.connector  # type: ignore
except Exception:
    mysql = None  # noqa

# Prefer dbmysql.getconn(), fallback to dbmysql.get_conn(), fallback to db_mysql.get_conn()
_get_conn = None
for mod, fn in [("dbmysql", "getconn"), ("dbmysql", "get_conn"), ("db_mysql", "get_conn")]:
    try:
        m = __import__(mod, fromlist=[fn])
        _get_conn = getattr(m, fn)
        print(f"[INIT] Successfully imported {mod}.{fn}")
        break
    except Exception as e:
        print(f"[INIT] Failed to import {mod}.{fn}: {e}")
        continue

if _get_conn is None:
    print("[WARNING] No MySQL connector helper found. DB operations will fail.")

# ---------- Small env helpers ----------
def env_str(name: str, default: str = "") -> str:
    v = str(os.getenv(name, "")).strip()
    return v if v else default

def env_int(name: str, default: int) -> int:
    v = str(os.getenv(name, "")).strip()
    if not v:
        return int(default)
    try:
        return int(v)
    except Exception:
        return int(default)

def env_float(name: str, default: float) -> float:
    v = str(os.getenv(name, "")).strip()
    if not v:
        return float(default)
    try:
        return float(v)
    except Exception:
        return float(default)

def env_bool(name: str, default: bool) -> bool:
    v = str(os.getenv(name, "")).strip().lower()
    if not v:
        return bool(default)
    return v not in {"0", "false", "no", "off"}

# ---------- CONFIG ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HEADLESS = env_bool("HEADLESS", True)
NAV_TIMEOUT_MS = env_int("NAV_TIMEOUT_MS", env_int("NAVTIMEOUTMS", 45000))
ACTION_TIMEOUT_MS = env_int("ACTION_TIMEOUT_MS", env_int("ACTIONTIMEOUTMS", 30000))
SUBMIT_WAIT_MS = env_int("SUBMIT_WAIT_MS", env_int("SUBMITWAITMS", 15000))
SUBMIT_WINDOW_SECONDS = env_float("SUBMIT_WINDOW_SECONDS", env_float("SUBMITWINDOWSECONDS", 14.0))
PER_WEBSITE_TIMEOUT_SEC = env_int("PER_WEBSITE_TIMEOUT_SEC", env_int("PERWEBSITETIMEOUTSEC", 130))
POST_NAV_SLEEP_MS = env_int("POST_NAV_SLEEP_MS", 1200)
DEFAULT_BATCH_LIMIT = env_int("DEFAULT_BATCH_LIMIT", env_int("DEFAULTBATCHLIMIT", 250))
MYSQL_WEBSITES_TABLE = env_str("MYSQL_WEBSITES_TABLE", env_str("MYSQLWEBSITESTABLE", "websites"))
FRAME_DELIM = " ||| "
SKIP_HOSTS_EXACT = {
    "wa.me",
    "api.whatsapp.com",
    "youtube.com",
    "www.youtube.com",
    "link.zomato.com",
}

DROP_QUERY_KEYS_PREFIX = ("utm_",)
DROP_QUERY_KEYS_EXACT = {"gclid", "fbclid"}
SUCCESS_TEXT_RE = re.compile(
    r"(thank\s*you|message\s*(has\s*)?been\s*sent|we\s*will\s*get\s*back|submitted\s*successfully|received\s*your\s*message)",
    re.I,
)

# require these clusters before any submit attempt
CONFIDENCE_REQUIRED = {"email", "message"}

# Debug / reporting
DEBUG_FIELD_REPORT = env_bool("DEBUG_FIELD_REPORT", True)
SCREENSHOT_DIR = env_str("SCREENSHOT_DIR", "").strip()

# -------------- Submit control --------------
DRY_RUN = env_bool("DRY_RUN", False)
ALLOW_RERUNS = env_bool("ALLOW_RERUNS", True)
POST_SUBMIT_WAIT_MS = env_int("POST_SUBMIT_WAIT_MS", 10000)  # 10 seconds
CONCURRENT_BROWSERS = env_int("CONCURRENT_BROWSERS", 1)
POLITE_DELAY_MS = env_int("POLITE_DELAY_MS", 300)

# Random pool config
RANDOM_POOL_TABLE = env_str("RANDOM_POOL_TABLE", "random_value_pool")
RANDOM_POOL_RANDOM_SQL = env_str("RANDOM_POOL_RANDOM_SQL", "RAND()")

# IMPORTANT: MUST be these exact table names
FORM_SUBMISSIONS_TABLE = "form_submissions"
FORM_SUBMISSIONS_DETAILS_TABLE = "form_submissions_details"

# ---------- LOGGING ----------
logger = logging.getLogger("smart_form_filler")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logger.addHandler(_handler)

# ---------- URL helpers ----------
def host(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""

def with_scheme(u: str) -> List[str]:
    u = (u or "").strip()
    if not u:
        return []
    p = urlparse(u)
    if p.scheme:
        alt = u
        try:
            alt_p = p._replace(scheme="https" if p.scheme == "http" else "http")
            alt = urlunparse(alt_p)
        except Exception:
            pass
        return [u, alt]
    return [f"https://{u}", f"http://{u}"]

def canonical_url(u: str) -> str:
    u = (u or "").strip()
    if not u:
        return ""
    p = urlparse(u)
    scheme = (p.scheme or "http").lower()
    netloc = (p.netloc or "").lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = (p.path or "/").rstrip("/")
    if path == "":
        path = "/"
    q = []
    for k, v in parse_qsl(p.query, keep_blank_values=True):
        kl = (k or "").lower()
        if kl in DROP_QUERY_KEYS_EXACT:
            continue
        if any(kl.startswith(pref) for pref in DROP_QUERY_KEYS_PREFIX):
            continue
        q.append((kl, v))
    q.sort()
    return urlunparse((scheme, netloc, path, "", urlencode(q, doseq=True), ""))

def is_noise_url(url: str) -> bool:
    """Filter out tracking/analytics URLs that aren't actual form submissions."""
    u = (url or "").lower()
    noise = [
        # Google
        "google-analytics",
        "googletagmanager",
        "doubleclick",
        "google.com/pagead",
        "google.com/ccm",
        "g/collect",
        "maps.googleapis.com",
        "fonts.googleapis.com",
        # Analytics & Tracking
        "hotjar",
        "clarity.ms",
        "facebook.com/tr",
        "fbq",
        "pixel",
        "analytics",
        "stats",
        "beacon",
        "track",
        "telemetry",
        # Wix
        "frog.wix.com",
        "panorama.wixapps.net",
        # Shopify monitoring
        ".well-known/shopify/monorail",
        # Common noise patterns
        "ccm/collect",
        "sentry.io",
        "bugsnag",
        "newrelic",
        "segment.io",
        "segment.com",
        "mixpanel",
        "amplitude",
        "intercom",
        "crisp.chat",
        "tawk.to",
        "livechat",
        "zendesk",
        "freshdesk",
    ]
    return any(x in u for x in noise)

def same_host(a: str, b: str) -> bool:
    ha = host(a).removeprefix("www.")
    hb = host(b).removeprefix("www.")
    return bool(ha and hb and ha == hb)

def submission_allowed(url: str) -> bool:
    return True

# ---------- Debug helpers ----------
def safe_filename(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"[^a-zA-Z0-9_.-]+", "_", s)
    return s[:180] if s else "page"

async def maybe_screenshot(page: Page, tag: str, website_id: int, url: str) -> None:
    if not SCREENSHOT_DIR:
        return
    try:
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        name = safe_filename(f"{website_id}_{tag}_{host(url)}")
        path = os.path.join(SCREENSHOT_DIR, f"{name}.png")
        await page.screenshot(path=path, full_page=True)
        logger.info(f"[DEBUG] Screenshot saved: {path}")
    except Exception:
        pass

async def dismiss_overlays(page: Page) -> None:
    candidates = [
        "button#onetrust-accept-btn-handler",
        "button:has-text('Accept')",
        "button:has-text('I agree')",
        "button:has-text('Agree')",
        "button:has-text('Allow all')",
        "button:has-text('Got it')",
        "button:has-text('OK')",
        "button[aria-label*=close i]",
        "div[role=dialog] button:has-text('Accept')",
        "div[role=dialog] button:has-text('OK')",
    ]
    for sel in candidates:
        try:
            loc = page.locator(sel)
            if await loc.count() == 0:
                continue
            btn = await pick_visible_from_locator(loc)
            try:
                await btn.click(timeout=1200)
                await page.wait_for_timeout(250)
            except Exception:
                pass
        except Exception:
            continue

async def wait_for_formish_content(page: Page) -> None:
    """Wait for form content to be visible and rendered"""
    try:
        # Wait for form elements to exist
        await page.wait_for_selector("form, input, textarea, select, iframe", timeout=8000)
    except Exception:
        pass
    
    # Wait additional time for visible fields
    try:
        await page.wait_for_selector("input:visible, textarea:visible, select:visible", timeout=5000)
    except Exception:
        pass
    
    # Additional settle time for dynamic rendering
    try:
        await page.wait_for_timeout(1500)
    except Exception:
        pass

# ---------- MySQL DB adapter ----------
def _require_get_conn():
    if _get_conn is None:
        raise RuntimeError("No MySQL connector helper found. Provide dbmysql.getconn/get_conn.")
    return _get_conn

class RandomValuePool:
    def __init__(self) -> None:
        gc = _require_get_conn()
        self.conn = gc()
        self.ensure_schema()

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass

    def ensure_schema(self) -> None:
        cur = self.conn.cursor()
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {RANDOM_POOL_TABLE} (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                field_concept VARCHAR(64) NOT NULL,
                value TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                INDEX ix_{RANDOM_POOL_TABLE}_concept (field_concept)
            )
            """
        )
        self.conn.commit()
        cur.close()

    def random_value(self, concept: str) -> str:
        concept = (concept or "").strip()
        if not concept:
            return ""
        
        # Map Python concept names to database field_concept names
        # This handles variations in naming conventions (camelCase, snake_case, compound words)
        concept_map = {
            # Name fields
            'fullname': 'full_name',
            'firstname': 'first_name', 
            'lastname': 'last_name',
            
            # Date fields
            'dateofbirth': 'date_of_birth',
            'dob': 'date_of_birth',
            
            # Postal/ZIP code variations
            'zipcode': 'zip_code',
            'postalcode': 'zip_code',
            'postal_code': 'zip_code',
            'postcode': 'zip_code',
            'pincode': 'zip_code',
            
            # Address fields
            'addressline1': 'address',
            'addressline2': 'address',
            'address1': 'address',
            'address2': 'address',
            'streetaddress': 'address',
            'street': 'address',
            
            # Job/Work fields  
            'jobtitle': 'job_title',
            'position': 'job_title',
            'title': 'job_title',
            
            # Other common variations
            'companyname': 'company',
            'organization': 'company',
            'employer': 'company',
        }
        
        # Convert concept name if needed
        db_concept = concept_map.get(concept, concept)
        
        cur = self.conn.cursor()
        cur.execute(
            f"SELECT value FROM {RANDOM_POOL_TABLE} WHERE field_concept=%s ORDER BY {RANDOM_POOL_RANDOM_SQL} LIMIT 1",
            (db_concept,),
        )
        row = cur.fetchone()
        cur.close()
        if not row:
            return ""
        return str(row[0] or "")

    def values_for_concepts(self, concepts: List[str]) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for c in concepts:
            out[c] = self.random_value(c)
        return out

class MySQLDB:
    def __init__(self) -> None:
        gc = _require_get_conn()
        self.conn = gc()
        self.init_schema()

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass

    def exec(self, sql: str, params: Optional[Tuple[Any, ...]] = None) -> None:
        cur = self.conn.cursor()
        cur.execute(sql, params or ())
        self.conn.commit()
        cur.close()

    def init_schema(self) -> None:
        self.exec(
            f"""
            CREATE TABLE IF NOT EXISTS {FORM_SUBMISSIONS_TABLE} (
                id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                website_id INT UNSIGNED NULL,
                url TEXT NULL,
                normalized_url TEXT NULL,
                status VARCHAR(32) NULL,
                filled_fields INT UNSIGNED NOT NULL DEFAULT 0,
                error TEXT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.exec(
            f"""
            CREATE TABLE IF NOT EXISTS {FORM_SUBMISSIONS_DETAILS_TABLE} (
                id INT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                submission_id INT UNSIGNED NOT NULL,
                request_url TEXT NULL,
                payload_json LONGTEXT NULL,
                response_json LONGTEXT NULL,
                status_code INT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        try:
            self.exec(
                f"CREATE UNIQUE INDEX ux_{FORM_SUBMISSIONS_TABLE}_normalized_url ON {FORM_SUBMISSIONS_TABLE} (normalized_url(255))"
            )
        except Exception:
            pass

    def already_processed(self, normalized_url: str) -> bool:
        if not normalized_url:
            return False
        cur = self.conn.cursor()
        cur.execute(f"SELECT 1 FROM {FORM_SUBMISSIONS_TABLE} WHERE normalized_url=%s LIMIT 1", (normalized_url,))
        row = cur.fetchone()
        cur.close()
        return row is not None

    def save_submission(
        self,
        website_id: int,
        url: str,
        normalized_url: str,
        status: str,
        filled_fields: int,
        error: str,
        campaign_id: Optional[int] = None,
    ) -> int:
        cur = self.conn.cursor()
        try:
            cur.execute(
                f"""
                INSERT INTO {FORM_SUBMISSIONS_TABLE}
                    (website_id, url, normalized_url, status, filled_fields, error, campaignid)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    status = VALUES(status),
                    filled_fields = VALUES(filled_fields),
                    error = VALUES(error),
                    campaignid = COALESCE(VALUES(campaignid), campaignid),
                    created_at = CURRENT_TIMESTAMP
                """,
                (
                    int(website_id or 0),
                    url or "",
                    normalized_url or "",
                    status or "",
                    int(filled_fields or 0),
                    (error or "")[:2000],
                    int(campaign_id) if campaign_id is not None else None,
                ),
            )
            self.conn.commit()
            submission_id = int(cur.lastrowid or 0)
            if submission_id == 0 and normalized_url:
                cur.execute(
                    f"SELECT id FROM {FORM_SUBMISSIONS_TABLE} WHERE normalized_url=%s LIMIT 1",
                    (normalized_url,),
                )
                row = cur.fetchone()
                if row:
                    submission_id = int(row[0])
            logger.info(f"[DB] Saved submission: id={submission_id} website_id={website_id} status={status}")
            return submission_id
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception:
                pass
            logger.exception(
                "DB save_submission FAILED (website_id=%s url=%s normalized_url=%s status=%s): %s",
                website_id, url, normalized_url, status, e
            )
            return -1
        finally:
            try:
                cur.close()
            except Exception:
                pass

    def update_website_scan_status(
        self,
        website_id: int,
        form_found: bool,
        has_captcha: bool,
        is_dead: bool = False,
    ) -> None:
        if not website_id or website_id <= 0:
            return
        cur = self.conn.cursor()
        try:
            cur.execute(
                """
                UPDATE websites
                SET form_found = %s, has_captcha = %s, is_dead = %s, timestamp = NOW()
                WHERE id = %s
                """,
                (1 if form_found else 0, 1 if has_captcha else 0, 1 if is_dead else 0, int(website_id)),
            )
            self.conn.commit()
        except Exception as e:
            logger.warning(f"[DB] Failed to update website scan status for {website_id}: {e}")
        finally:
            try:
                cur.close()
            except Exception:
                pass

    def save_discovered_fields(self, website_id: int, fields: List["FieldMeta"]) -> None:
        if not website_id or website_id <= 0 or not fields:
            return
        cur = self.conn.cursor()
        try:
            cur.execute("DELETE FROM raw_fields WHERE website_id = %s", (int(website_id),))
            rows = []
            for f in fields:
                cluster, score = best_cluster_for_field(f)
                rows.append((
                    int(website_id),
                    (f.tag or "")[:50],
                    (f.id or "")[:255],
                    (f.name or "")[:255],
                    (f.type or "")[:100],
                    (f.placeholder or "")[:500],
                    cluster if cluster != "unmapped" else "unknown",
                    round(min(max(float(score) / 10.0, 0.0), 1.0), 3),
                ))
            cur.executemany(
                """
                INSERT INTO raw_fields
                    (website_id, tag_name, field_id, field_name, field_type, placeholder, cluster_key, cluster_score, cluster_version, clustered_at)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, 'v2', NOW())
                """,
                rows,
            )
            try:
                cur.execute("UPDATE websites SET fields_count=%s WHERE id=%s", (len(rows), int(website_id)))
            except Exception:
                pass
            self.conn.commit()
        except Exception as e:
            logger.warning(f"[DB] Failed to save discovered raw_fields for {website_id}: {e}")
        finally:
            try:
                cur.close()
            except Exception:
                pass

    def save_details(
        self,
        submission_id: int,
        request_url: str,
        payload: Optional[Dict[str, Any]],
        response_data: Optional[Dict[str, Any]],
        status_code: int,
    ) -> None:
        if not submission_id or submission_id <= 0:
            logger.warning(f"[DB] Skipping save_details: invalid submission_id={submission_id}")
            return
        cur = self.conn.cursor()
        try:
            cur.execute(
                f"""
                INSERT INTO {FORM_SUBMISSIONS_DETAILS_TABLE}
                    (submission_id, request_url, payload_json, response_json, status_code)
                VALUES
                    (%s, %s, %s, %s, %s)
                """,
                (
                    int(submission_id),
                    request_url or "",
                    json.dumps(payload or {}, ensure_ascii=False)[:65500],
                    json.dumps(response_data or {}, ensure_ascii=False)[:65500],
                    int(status_code or 0),
                ),
            )
            self.conn.commit()
            logger.info(f"[DB] Saved details: submission_id={submission_id} status_code={status_code}")
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception:
                pass
            logger.exception(
                "DB save_details FAILED (submission_id=%s request_url=%s status_code=%s): %s",
                submission_id, request_url, status_code, e
            )
        finally:
            try:
                cur.close()
            except Exception:
                pass

    def load_websites_from_mysql(self, limit: int = DEFAULT_BATCH_LIMIT) -> List[Dict[str, Any]]:
        gc = _require_get_conn()
        conn = gc()
        cur = conn.cursor(dictionary=True)
        queries = [
            f"SELECT id AS website_id, url FROM {MYSQL_WEBSITES_TABLE} WHERE url IS NOT NULL AND url <> '' AND is_dead = 0 ORDER BY id ASC LIMIT %s",
            f"SELECT id AS website_id, url FROM {MYSQL_WEBSITES_TABLE} WHERE url IS NOT NULL AND url <> '' ORDER BY id ASC LIMIT %s",
        ]
        rows: List[Dict[str, Any]] = []
        last_err: Optional[Exception] = None
        for q in queries:
            try:
                cur.execute(q, (int(limit),))
                rows = cur.fetchall() or []
                break
            except Exception as e:
                last_err = e
                rows = []
                continue
        cur.close()
        conn.close()
        if not rows and last_err is not None:
            raise RuntimeError(f"MySQL load failed: {last_err}")
        out: List[Dict[str, Any]] = []
        for i, r in enumerate(rows, start=1):
            out.append(
                {
                    "website_id": int(r.get("website_id") or i),
                    "url": str(r.get("url") or "").strip(),
                    "contact_url_override": None,
                }
            )
        return out

# ---------- Field discovery mapping ----------
@dataclass
class FieldMeta:
    selector: str
    tag: str
    type: str
    name: str
    id: str
    placeholder: str
    aria_label: str
    label_text: str
    visible: bool

def norm(s: Optional[str]) -> str:
    return str(s or "").strip().lower()

def blob_field(f: FieldMeta) -> str:
    return " ".join(
        [
            norm(f.tag),
            norm(f.type),
            norm(f.name),
            norm(f.id),
            norm(f.placeholder),
            norm(f.aria_label),
            norm(f.label_text),
        ]
    )

CLUSTERS: Dict[str, set] = {
    "fullname": {"name", "full name", "fullname", "your name"},
    "firstname": {"first", "first name", "firstname", "given name"},
    "lastname": {"last", "last name", "lastname", "surname", "family name"},
    "email": {"email", "e-mail"},
    "phone": {"phone", "mobile", "tel", "telephone", "contact number", "whatsapp"},
    "company": {"company", "organization", "organisation", "business", "firm"},
    "website": {"website", "site", "url", "domain"},
    "jobtitle": {"job title", "designation", "role", "position"},
    "department": {"department", "team"},
    "addressline1": {"address", "address 1", "address1", "street", "street address", "house", "building"},
    "addressline2": {"address 2", "address2", "apartment", "apt", "suite", "landmark"},
    "city": {"city", "town"},
    "state": {"state", "province", "region"},
    "postalcode": {"zip", "zipcode", "postal", "postal code", "pincode", "pin code"},
    "country": {"country", "nation"},
    "dateofbirth": {"dob", "date of birth", "birth date", "birthdate"},
    "date": {"date", "select date"},
    "gender": {"gender", "male", "female", "other"},
    "subject": {"subject", "topic", "title"},
    "message": {"message", "comment", "enquiry", "inquiry", "details", "how can we help", "your message"},
    "consent": {"consent", "agree", "i agree", "privacy", "terms", "gdpr"},
}

def looks_like_phone(f: FieldMeta) -> bool:
    if norm(f.tag) == "textarea":
        return False
    b = blob_field(f)
    if norm(f.type) in {"tel", "phone"}:
        return True
    if any(k in b for k in ["phone", "mobile", "telephone", "whatsapp"]):
        return True
    return bool(re.search(r"\btel\b", b))

def looks_like_email(f: FieldMeta) -> bool:
    b = blob_field(f)
    if "email" in norm(f.type):
        return True
    return "email" in b

def looks_like_message(f: FieldMeta) -> bool:
    b = blob_field(f)
    if norm(f.tag) == "textarea" or norm(f.type) == "contenteditable":
        return True
    return any(k in b for k in ["message", "comment", "enquiry", "inquiry"])


def has_contact_form_confidence(mapping: Dict[str, str]) -> bool:
    keys = set(mapping.keys())
    if CONFIDENCE_REQUIRED.issubset(keys):
        return True
    # Multi-step / lead-capture forms: email + at least 2 other contact fields
    if "email" in keys and len(keys & {"fullname", "firstname", "lastname", "phone", "company", "subject"}) >= 2:
        return True
    return False


async def discover_contact_details(page: Page) -> Dict[str, List[str]]:
    """Extract mailto:, tel:, and WhatsApp contact details when no web form is present."""
    try:
        details = await page.evaluate(
            """() => {
                const emails = new Set();
                const phones = new Set();
                const whatsapp = new Set();
                for (const a of document.querySelectorAll('a[href]')) {
                    const href = (a.getAttribute('href') || '').trim();
                    const low = href.toLowerCase();
                    if (low.startsWith('mailto:')) {
                        const val = href.slice(7).split('?')[0].trim();
                        if (val) emails.add(val);
                    } else if (low.startsWith('tel:')) {
                        const val = href.slice(4).trim();
                        if (val) phones.add(val);
                    } else if (low.includes('wa.me/') || low.includes('api.whatsapp.com')) {
                        whatsapp.add(href);
                    }
                }
                return {
                    emails: Array.from(emails).slice(0, 5),
                    phones: Array.from(phones).slice(0, 5),
                    whatsapp: Array.from(whatsapp).slice(0, 3),
                };
            }"""
        )
        return details if isinstance(details, dict) else {"emails": [], "phones": [], "whatsapp": []}
    except Exception:
        return {"emails": [], "phones": [], "whatsapp": []}

def looks_like_date(f: FieldMeta) -> bool:
    b = blob_field(f)
    if norm(f.type) == "date":
        return True
    return any(k in b for k in ["dob", "date of birth", "birth date", "birthdate", "ddmm", "mmdd", "yyyy"])

def looks_like_postal(f: FieldMeta) -> bool:
    b = blob_field(f)
    return any(k in b for k in ["zip", "zipcode", "postal", "postal code", "pincode", "pin code"])

def looks_like_country(f: FieldMeta) -> bool:
    b = blob_field(f)
    return "country" in b or "nation" in b

def looks_like_consent(f: FieldMeta) -> bool:
    b = blob_field(f)
    if norm(f.type) == "checkbox":
        return True
    return any(k in b for k in ["consent", "i agree", "privacy", "terms", "gdpr"])

async def get_label_text(root: Union[Page, Frame], selector: str) -> str:
    try:
        el = root.locator(selector).first
        el_id = await el.get_attribute("id")
        if el_id:
            lab = root.locator(f"label[for='{el_id}']").first
            if await lab.count() > 0:
                t = await lab.inner_text() or ""
                if t.strip():
                    return t.strip()[:200]
        # Fallback: wrapping <label> or sibling <label> in parent container
        fallback = await el.evaluate(
            """(node) => {
                const wrap = node.closest('label');
                if (wrap && wrap.innerText) return wrap.innerText.trim();
                const parent = node.parentElement;
                if (parent) {
                    const lbl = parent.querySelector('label');
                    if (lbl && lbl.innerText) return lbl.innerText.trim();
                }
                return '';
            }"""
        )
        if fallback:
            return str(fallback).strip()[:200]
    except Exception:
        pass
    return ""

async def build_field_meta(root: Union[Page, Frame], selector: str) -> Optional[FieldMeta]:
    loc = root.locator(selector).first
    try:
        if await loc.count() == 0:
            return None
        tag = norm(await loc.evaluate("el => el.tagName.toLowerCase()"))
        typ = norm(await loc.get_attribute("type"))
        ce = norm(await loc.get_attribute("contenteditable"))
        role = norm(await loc.get_attribute("role"))
        if not typ and (ce == "true" or role == "textbox"):
            typ = "contenteditable"
        name = norm(await loc.get_attribute("name"))
        el_id = norm(await loc.get_attribute("id"))
        placeholder = norm(await loc.get_attribute("placeholder"))
        aria_label = norm(await loc.get_attribute("aria-label"))
        try:
            visible = bool(await loc.is_visible())
        except Exception:
            visible = False
        label_text = norm(await get_label_text(root, selector))
        if typ in {"hidden", "submit", "button", "image", "file", "reset"}:
            return None
        return FieldMeta(
            selector=selector,
            tag=tag,
            type=typ,
            name=name,
            id=el_id,
            placeholder=placeholder,
            aria_label=aria_label,
            label_text=label_text,
            visible=visible,
        )
    except Exception:
        return None

def combine_selector(iframe_selector: Optional[str], inner_selector: str) -> str:
    if iframe_selector:
        return f"{iframe_selector}{FRAME_DELIM}{inner_selector}"
    return inner_selector

def split_selector(selector: str) -> Tuple[Optional[str], str]:
    if FRAME_DELIM in selector:
        a, b = selector.split(FRAME_DELIM, 1)
        return a.strip() or None, b.strip() or ""
    return None, selector

async def pick_visible_from_locator(loc: Locator) -> Locator:
    try:
        n = await loc.count()
    except Exception:
        n = 0
    n = min(int(n or 0), 10)
    for i in range(n):
        cand = loc.nth(i)
        try:
            if await cand.is_visible() and await cand.is_enabled():
                return cand
        except Exception:
            continue
    return loc.first

async def iframe_selector_for_frame(page: Page, fr: Frame) -> Optional[str]:
    try:
        el = await fr.frame_element()
        iframe_id = await el.get_attribute("id")
        if iframe_id:
            return f"iframe#{iframe_id}"
        iframe_name = await el.get_attribute("name")
        if iframe_name:
            return f"iframe[name='{iframe_name}']"
    except Exception:
        pass
    return None

async def discover_fields_from_root(root: Union[Page, Frame], iframe_selector: Optional[str] = None) -> List[FieldMeta]:
    form_scope = None
    try:
        forms_info = await root.eval_on_selector_all(
            "form",
            """(forms) => {
                const kw = ["contact","message","enquiry","inquiry","get in touch","reach us","send"];
                return forms.map((f, idx) => {
                    f.setAttribute("data-cff-form", String(idx));
                    const txt = (f.innerText + " " + (f.getAttribute("action")||"") + " " + (f.id||"") + " " + (f.getAttribute("name")||"")).toLowerCase();
                    const fields = f.querySelectorAll("input,textarea,select").length;
                    let score = fields;
                    for (const k of kw) if (txt.includes(k)) score += 10;
                    if (txt.includes("search")) score -= 8;
                    if (txt.includes("newsletter") || txt.includes("subscribe")) score -= 5;
                    return {idx, score, fields};
                });
            }""",
        )
        if forms_info:
            forms_info.sort(key=lambda x: (int(x.get("score") or 0), int(x.get("fields") or 0)), reverse=True)
            if int(forms_info[0].get("fields") or 0) > 0:
                form_scope = f"form[data-cff-form='{int(forms_info[0]['idx'])}']"
                logger.info(f"[DISCOVERY] Selected form scope: {form_scope} with {forms_info[0].get('fields')} fields (score: {forms_info[0].get('score')})")
    except Exception as e:
        logger.debug(f"[DISCOVERY] Error finding forms: {e}")
        form_scope = None

    js = f"""
    () => {{
        const formSel = {json.dumps(form_scope)};
        const scope = formSel ? document.querySelector(formSel) : document;
        if (!scope) return [];

        const collectAll = (rootNode) => {{
            const out = [];
            const walk = (node) => {{
                if (!node || !node.querySelectorAll) return;
                out.push(...Array.from(node.querySelectorAll("input, textarea, select, [contenteditable='true'], [role='textbox']")));
                for (const el of node.querySelectorAll("*")) {{
                    if (el.shadowRoot) walk(el.shadowRoot);
                }}
            }};
            walk(rootNode);
            return out;
        }};

        const els = collectAll(scope);
        const forms = Array.from(document.querySelectorAll("form"));
        const esc = (s) => {{
            try {{ return CSS.escape(s); }} catch(e) {{ return String(s).replace(/'/g,""); }}
        }};
        return els.map((el, i) => {{
            const tag = el.tagName.toLowerCase();
            const id = el.getAttribute("id");
            const name = el.getAttribute("name");
            const f = el.closest("form");
            const formIndex = f ? forms.indexOf(f) : -1;
            let selector = "";
            if (id) selector = "#" + esc(id);
            else if (name && formIndex >= 0) {{
                f.setAttribute("data-cff-form", String(formIndex));
                selector = `form[data-cff-form='${{formIndex}}'] ${{tag}}[name='${{name.replace(/'/g,"")}}']`;
            }}
            else if (name) selector = `${{tag}}[name='${{name.replace(/'/g,"")}}']`;
            else {{
                el.setAttribute("data-cff-idx", String(i));
                selector = `${{tag}}[data-cff-idx='${{i}}']`;
            }}
            return selector;
        }});
    }}
    """
    try:
        candidate_selectors: List[str] = await root.evaluate(js)
    except Exception:
        candidate_selectors = []

    metas: List[FieldMeta] = []
    seen = set()
    for sel in candidate_selectors:
        if not sel or sel in seen:
            continue
        seen.add(sel)
        meta = await build_field_meta(root, sel)
        if meta:
            meta.selector = combine_selector(iframe_selector, meta.selector)
            metas.append(meta)
    return metas

async def try_click_contact_button(page: Page) -> bool:
    """Try to click contact-related buttons/links on the page as a fallback.
    Uses JavaScript to find elements by text content for better reliability.
    Returns True if a button was clicked successfully."""
    
    logger.info("[FALLBACK] Using JavaScript to find clickable contact elements...")
    
    # JavaScript function to find all clickable elements containing contact-related text
    js_find_buttons = """
    () => {
        const contactPatterns = [
            /contact\\s*us\\s*now/i,
            /contact\\s*us/i,
            /get\\s*in\\s*touch/i,
            /send\\s*message/i,
            /send\\s*us\\s*a\\s*message/i,
            /contact/i,
            /inquire/i,
            /enquiry/i,
            /message\\s*us/i,
            /reach\\s*out/i,
            /talk\\s*to\\s*us/i
        ];
        
        // Find all potentially clickable elements
        const selectors = 'button, a, div[role="button"], span[role="button"], [onclick], .btn, .button';
        const elements = Array.from(document.querySelectorAll(selectors));
        
        const matches = [];
        
        for (const el of elements) {
            // Skip if not visible
            const rect = el.getBoundingClientRect();
            const style = window.getComputedStyle(el);
            if (rect.width === 0 || rect.height === 0 || 
                style.display === 'none' || style.visibility === 'hidden' ||
                style.opacity === '0') {
                continue;
            }
            
            const text = (el.innerText || el.textContent || '').trim();
            
            // Check if text matches any pattern
            for (const pattern of contactPatterns) {
                if (pattern.test(text)) {
                    matches.push({
                        text: text.substring(0, 100),
                        tagName: el.tagName,
                        className: el.className,
                        id: el.id,
                        index: matches.length
                    });
                    // Store element reference
                    el.setAttribute('data-contact-btn-idx', matches.length - 1);
                    break;
                }
            }
        }
        
        return matches;
    }
    """
    
    try:
        # Find all matching elements
        matches = await page.evaluate(js_find_buttons)
        
        if not matches or len(matches) == 0:
            logger.info("[FALLBACK] No contact buttons found via JavaScript")
            return False
        
        logger.info(f"[FALLBACK] Found {len(matches)} potential contact button(s):")
        for match in matches:
            logger.info(f"  - {match['tagName']}: '{match['text'][:50]}' (class={match.get('className', 'none')}, id={match.get('id', 'none')})")
        
        # Try clicking each match in order
        for match in matches:
            try:
                idx = match['index']
                btn_text = match['text'][:50]
                
                logger.info(f"[FALLBACK] Attempting to click: '{btn_text}'")
                
                # Click using the data attribute we set
                btn_selector = f"[data-contact-btn-idx='{idx}']"
                btn = page.locator(btn_selector)
                
                # Verify it's still visible
                count = await btn.count()
                if count == 0:
                    logger.debug(f"[FALLBACK] Button disappeared")
                    continue
                
                is_visible = await btn.is_visible()
                if not is_visible:
                    logger.debug(f"[FALLBACK] Button not visible")
                    continue
                
                # Click it
                await btn.click(timeout=5000)
                logger.info(f"[FALLBACK] Successfully clicked: '{btn_text}'")
                
                # Wait for modal/form/navigation
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=3000)
                except Exception:
                    pass
                
                # Wait for animations
                await page.wait_for_timeout(2000)
                
                # Dismiss any overlays that appeared
                await dismiss_overlays(page)
                
                logger.info(f"[FALLBACK] After click, URL: {page.url}")
                return True
                
            except Exception as e:
                logger.debug(f"[FALLBACK] Click failed for '{btn_text}': {e}")
                continue
        
        logger.warning("[FALLBACK] Found buttons but couldn't click any")
        return False
        
    except Exception as e:
        logger.error(f"[FALLBACK] JavaScript button finding failed: {e}")
        return False

async def discover_fields(page: Page) -> List[FieldMeta]:
    """Discover form fields with improved dynamic content handling and button click fallback"""
    await dismiss_overlays(page)
    await wait_for_formish_content(page)
    
    # Add extra wait for dynamic content to load
    try:
        await page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass
    
    # Additional wait for JavaScript-rendered fields
    try:
        await page.wait_for_timeout(2000)
    except Exception:
        pass
    
    logger.info("[DISCOVERY] Starting field discovery on main page...")
    metas = await discover_fields_from_root(page, iframe_selector=None)
    if metas:
        logger.info(f"[DISCOVERY] Found {len(metas)} fields in main page")
        return metas
    
    # Check all iframes, collect all fields from all iframes
    logger.info(f"[DISCOVERY] No fields in main page, checking {len(page.frames)} frames...")
    all_iframe_metas = []
    for idx, fr in enumerate(page.frames):
        if fr == page.main_frame:
            continue
        iframe_sel = await iframe_selector_for_frame(page, fr)
        if not iframe_sel:
            logger.debug(f"[DISCOVERY] Frame {idx}: No selector found")
            continue
        try:
            fm = await discover_fields_from_root(fr, iframe_selector=iframe_sel)
            if fm:
                logger.info(f"[DISCOVERY] Frame {idx} ({iframe_sel}): Found {len(fm)} fields")
                all_iframe_metas.extend(fm)
        except Exception as e:
            logger.debug(f"[DISCOVERY] Frame {idx}: Error - {e}")
            continue
    
    if all_iframe_metas:
        logger.info(f"[DISCOVERY] Total fields from iframes: {len(all_iframe_metas)}")
        return all_iframe_metas
    
    # FALLBACK: No fields found anywhere, try clicking contact buttons
    logger.warning("[DISCOVERY] No fields found in main page or iframes")
    logger.info("[FALLBACK] Attempting to click contact buttons...")
    
    button_clicked = await try_click_contact_button(page)
    
    if not button_clicked:
        logger.warning("[DISCOVERY] No fields found and no contact buttons to click")
        return []
    
    # After clicking button, try discovering fields again
    logger.info("[FALLBACK] Re-attempting field discovery after button click...")
    
    # Wait for any content to load after button click
    try:
        await page.wait_for_load_state("networkidle", timeout=5000)
    except Exception:
        pass
    
    await wait_for_formish_content(page)
    
    # Try main page again
    metas_after_click = await discover_fields_from_root(page, iframe_selector=None)
    if metas_after_click:
        logger.info(f"[FALLBACK] Success! Found {len(metas_after_click)} fields after button click")
        return metas_after_click
    
    # Try iframes again
    logger.info(f"[FALLBACK] Checking {len(page.frames)} frames after button click...")
    all_iframe_metas_after = []
    for idx, fr in enumerate(page.frames):
        if fr == page.main_frame:
            continue
        iframe_sel = await iframe_selector_for_frame(page, fr)
        if not iframe_sel:
            continue
        try:
            fm = await discover_fields_from_root(fr, iframe_selector=iframe_sel)
            if fm:
                logger.info(f"[FALLBACK] Frame {idx}: Found {len(fm)} fields")
                all_iframe_metas_after.extend(fm)
        except Exception:
            continue
    
    if all_iframe_metas_after:
        logger.info(f"[FALLBACK] Success! Total fields from iframes: {len(all_iframe_metas_after)}")
        return all_iframe_metas_after
    
    logger.warning("[FALLBACK] Still no fields found even after clicking contact button")
    return []

def score_field_for_cluster(f: FieldMeta, cluster: str) -> int:
    if cluster == "phone" and not looks_like_phone(f):
        return -999
    if cluster == "email" and not looks_like_email(f):
        return -999
    if cluster == "message" and not looks_like_message(f):
        return -999
    if cluster in {"dateofbirth", "date"} and not looks_like_date(f):
        return -999
    if cluster == "postalcode" and not looks_like_postal(f):
        return -999
    if cluster == "country" and not looks_like_country(f):
        return -999
    if cluster == "consent" and not looks_like_consent(f):
        return -999
    cwords = CLUSTERS.get(cluster, set())
    b = blob_field(f)
    score = 0
    for w in cwords:
        if w and w in b:
            score += 4
    if cluster == "email" and "email" in norm(f.type):
        score += 10
    if cluster == "phone" and norm(f.type) in {"tel", "phone"}:
        score += 8
    if cluster == "message" and (norm(f.tag) == "textarea" or norm(f.type) == "contenteditable"):
        score += 10
    if cluster in {"dateofbirth", "date"} and norm(f.type) == "date":
        score += 10
    if cluster == "consent" and norm(f.type) == "checkbox":
        score += 8
    if cluster in {"fullname", "firstname", "lastname", "company", "subject", "city", "state", "country"} and norm(f.type) in {
        "text",
        "",
    }:
        score += 2
    if f.visible:
        score += 2
    return score

def build_mapping(fields: List[FieldMeta]) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    used = set()
    ordered = [
        "fullname",
        "firstname",
        "lastname",
        "email",
        "phone",
        "company",
        "website",
        "jobtitle",
        "department",
        "addressline1",
        "addressline2",
        "city",
        "state",
        "postalcode",
        "country",
        "dateofbirth",
        "date",
        "gender",
        "subject",
        "message",
        "consent",
    ]
    for cluster in ordered:
        best_score = -10000
        best_sel = None
        for f in fields:
            if f.selector in used:
                continue
            s = score_field_for_cluster(f, cluster)
            if s > best_score:
                best_score = s
                best_sel = f.selector
        # Lower threshold to 6 to include phone fields (which typically score 6)
        if best_sel and best_score >= 6:
            mapping[cluster] = best_sel
            used.add(best_sel)
    return mapping

def best_cluster_for_field(f: FieldMeta) -> Tuple[str, int]:
    best_c = "unmapped"
    best_s = -10000
    for c in CLUSTERS.keys():
        s = score_field_for_cluster(f, c)
        if s > best_s:
            best_s = s
            best_c = c
    if best_s < 6:
        return "unmapped", best_s
    return best_c, best_s

def log_field_report(fields: List[FieldMeta]) -> None:
    if not DEBUG_FIELD_REPORT:
        return
    logger.info("[FIELD REPORT] ---- discovered fields ----")
    for f in fields:
        c, s = best_cluster_for_field(f)
        logger.info(
            f"[FIELD] cluster={c:12} score={s:4} tag={f.tag:8} type={f.type:10} visible={str(f.visible):5} "
            f"selector={f.selector} name={f.name} id={f.id} placeholder={f.placeholder} aria={f.aria_label} label={f.label_text}"
        )

async def fill_fields(page: Page, mapping: Dict[str, str], values: Dict[str, str]) -> Tuple[int, List[str], List[Dict[str, Any]]]:
    filled = 0
    errors: List[str] = []
    filled_report: List[Dict[str, Any]] = []
    for cluster, selector in mapping.items():
        val = str(values.get(cluster) or "").strip()
        if not val and cluster != "consent":
            continue
        ok = False
        err = ""
        try:
            iframe_sel, inner_sel = split_selector(selector)
            if iframe_sel:
                loc = page.frame_locator(iframe_sel).locator(inner_sel)
            else:
                loc = page.locator(inner_sel)
            loc = await pick_visible_from_locator(loc)
            await loc.scroll_into_view_if_needed()
            try:
                await loc.click(timeout=2000)
            except Exception:
                pass
            
            # Special handling for consent checkbox
            if cluster == "consent":
                try:
                    await loc.check(timeout=ACTION_TIMEOUT_MS)
                except Exception:
                    await loc.click(timeout=ACTION_TIMEOUT_MS)
            
            # Detect if this is a select dropdown
            elif "select" in selector.lower():
                # Use select_option for dropdowns
                try:
                    # Try selecting by label (human-readable)
                    await loc.select_option(label=val, timeout=ACTION_TIMEOUT_MS)
                except Exception:
                    try:
                        # Fallback: try selecting by value attribute
                        await loc.select_option(value=val, timeout=ACTION_TIMEOUT_MS)
                    except Exception:
                        # Last resort: get first option that matches
                        await loc.select_option(index=1, timeout=ACTION_TIMEOUT_MS)
            
            # Regular text input/textarea
            else:
                await loc.fill(val, timeout=ACTION_TIMEOUT_MS)
            
            ok = True
            filled += 1
            logger.info(f"[FILL] Filled {cluster:14} via {selector}")
        except Exception as e:
            err = f"{e}"
            msg = f"Fill failed for {cluster} ({selector}): {e}"
            logger.warning(f"[FILL] {msg}")
            errors.append(msg)
        filled_report.append(
            {"cluster": cluster, "selector": selector, "value": val if cluster != "consent" else "CHECKED", "ok": ok, "error": err[:300]}
        )
    logger.info(f"[FILL RESULT] Filled {filled} fields")
    return filled, errors, filled_report

# ---------- Captcha + submit helpers ----------
async def detect_captcha_on_page(page: Page) -> bool:
    checks = [
        "iframe[src*='recaptcha' i]",
        "script[src*='recaptcha' i]",
        "div.g-recaptcha",
        "textarea[name='g-recaptcha-response']",
        "input[name='g-recaptcha-response']",
        "iframe[src*='hcaptcha' i]",
        "script[src*='hcaptcha' i]",
        "div.h-captcha",
        "textarea[name='h-captcha-response']",
        "input[name='h-captcha-response']",
        "iframe[src*='turnstile' i]",
        "div.cf-turnstile",
        "input[name='cf-turnstile-response']",
        "form#challenge-form",
        "div#cf-challenge",
        "div.challenge-running",
        "iframe[title*='captcha' i]",
        "div[id*='captcha' i]",
    ]
    for sel in checks:
        try:
            if await page.locator(sel).count() > 0:
                return True
        except Exception:
            pass
    try:
        t = (await page.title() or "").lower()
        if "captcha" in t or "just a moment" in t or "cloudflare" in t:
            return True
    except Exception:
        pass
    try:
        bt = (await page.inner_text("body") or "").lower()
        if any(x in bt for x in ["captcha", "cloudflare", "turnstile", "hcaptcha", "recaptcha"]):
            return True
    except Exception:
        pass
    return False

def interpret_submission_response(resp_data: Any) -> Tuple[str, str]:
    if not isinstance(resp_data, dict):
        return "unknown", ""
    if "success" in resp_data and isinstance(resp_data.get("success"), bool):
        if resp_data["success"] is True:
            return "success", norm(resp_data.get("message") or resp_data.get("msg") or "")
        msg = norm(resp_data.get("message") or resp_data.get("errors") or "")
        return "failed", msg[:500]
    msg = norm(resp_data.get("message") or "")
    errors = resp_data.get("data") or resp_data.get("errors") or {}
    flat = norm(json.dumps(errors, ensure_ascii=False))
    combined = (msg + " " + flat).strip()
    if any(x in combined for x in ["captcha", "recaptcha", "hcaptcha", "turnstile", "cloudflare"]):
        return "captcha", combined[:500]
    if any(x in combined for x in ["error", "failed", "invalid"]):
        return "failed", combined[:500]
    if any(x in combined for x in ["success", "sent", "thank", "received"]):
        return "success", combined[:500]
    return "unknown", combined[:500]

async def success_text_on_page(page: Page) -> bool:
    try:
        txt = await page.inner_text("body")
        return bool(SUCCESS_TEXT_RE.search(txt or ""))
    except Exception:
        return False

async def submit_form(page: Page) -> Tuple[bool, str]:
    if page.is_closed():
        return False, "Page already closed before submit"
    submit_locators = [
        "form button[type=submit]",
        "form input[type=submit]",
        "button[type=submit]",
        "input[type=submit]",
        ".wpcf7-submit",
        "button:has-text('Send')",
        "button:has-text('Submit')",
        "button:has-text('Enquiry')",
        "button:has-text('Inquiry')",
        "button[aria-label*=submit i]",
        "button[aria-label*=send i]",
    ]
    for loc_str in submit_locators:
        try:
            btn_loc = page.locator(loc_str)
            if await btn_loc.count() == 0:
                continue
            btn = await pick_visible_from_locator(btn_loc)
            try:
                if not await btn.is_visible():
                    continue
            except Exception:
                pass
            logger.info(f"[SUBMIT] Found submit button via {loc_str}")
            if DRY_RUN:
                logger.info("[SUBMIT] DRY_RUN=True -> not clicking submit")
                return True, "DRY_RUN: skipped actual submit click"
            await btn.scroll_into_view_if_needed()
            await btn.click(timeout=8000)
            logger.info(f"[SUBMIT] Clicked submit via {loc_str}")
            return True, ""
        except Exception:
            continue
    return False, "No clickable submit button found"

# ---------- Network capture ----------
class SubmitNetworkCapture:
    def __init__(self) -> None:
        self.enabled = False
        self.start_ts = 0.0
        self.end_ts = 0.0
        self.requests: List[Dict[str, Any]] = []
        self.responses: List[Dict[str, Any]] = []
        self._response_event: Optional[asyncio.Event] = None

    def start_submit_window(self, seconds: float = SUBMIT_WINDOW_SECONDS) -> None:
        self.enabled = True
        self.start_ts = time.time()
        self.end_ts = self.start_ts + float(seconds)
        self.requests.clear()
        self.responses.clear()
        self._response_event = asyncio.Event()
        logger.info(f"[NETWORK] Submit window started ({int(seconds)}s)")

    async def wait_for_first_response(self, timeout_ms: int) -> None:
        if self._response_event is None:
            return
        try:
            await asyncio.wait_for(self._response_event.wait(), timeout=max(0.5, timeout_ms / 1000.0))
        except asyncio.TimeoutError:
            pass

    def stop_submit_window(self) -> None:
        self.enabled = False
        logger.info("[NETWORK] Submit window stopped")

    def in_window(self) -> bool:
        return self.enabled and time.time() <= self.end_ts

    async def on_request(self, request) -> None:
        if not self.in_window():
            return
        try:
            if request.method != "POST":
                return
            if is_noise_url(request.url):
                return
            payload_raw = request.post_data or ""
            payload: Any = None
            if payload_raw:
                try:
                    payload = json.loads(payload_raw)
                except Exception:
                    try:
                        payload = {k: v[0] for k, v in parseqs(raw, keep_blank_values=True).items()}


                    except Exception:
                        payload = {"raw": str(payload_raw)[:2000]}
            self.requests.append({"url": request.url, "method": request.method, "payload": payload or {}, "ts": time.time()})
        except Exception:
            return

    async def on_response(self, response) -> None:
        if not self.in_window():
            return
        try:
            req = response.request
            if req.method != "POST":
                return
            if is_noise_url(req.url):
                return
            status_code = int(response.status or 0)
            body: Any = None
            try:
                txt = await response.text()
                try:
                    body = json.loads(txt)
                except Exception:
                    body = {"raw_response": (txt or "")[:2000]}
            except Exception as e:
                body = {"error": f"response_body_unavailable: {e}"}
            self.responses.append({"url": req.url, "status_code": status_code, "body": body or {}, "ts": time.time()})
            if self._response_event is not None:
                self._response_event.set()
        except Exception:
            return

    def _score_response(self, resp: Dict[str, Any], base_host: str = "") -> int:
        """Score a response to prioritize actual form submissions over noise."""
        score = 0
        url = str(resp.get("url") or "").lower()

        # Positive signals: form-related URLs
        form_keywords = ["contact", "form", "submit", "send", "message", "inquiry", "enquiry", "feedback"]
        for kw in form_keywords:
            if kw in url:
                score += 10

        # Big bonus if same domain
        if base_host and base_host in url:
            score += 20

        # Look at payload for form field names
        payload = None
        for r in self.requests:
            if str(r.get("url") or "") == resp.get("url"):
                payload = r.get("payload")
                break

        if payload and isinstance(payload, dict):
            payload_str = json.dumps(payload).lower()
            # Common form field names
            if any(f in payload_str for f in ["email", "name", "message", "phone", "subject"]):
                score += 25

        # Slight penalty for common third-party form handlers (still valid but less preferred)
        if any(x in url for x in ["formspree", "getform", "web3forms", "zapier"]):
            score += 5  # These are valid form handlers

        return score

    def best_submission(self, base_domain: str = "") -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]], int, str]:
        """Returns payload, body, status_code, req_url - prioritizing actual form submissions."""
        if not self.responses:
            if self.requests:
                best_req = self.requests[-1]
                return best_req.get("payload") or {}, None, 0, str(best_req.get("url") or "")
            return None, None, 0, ""

        # Score all responses and pick the best
        scored = [(self._score_response(r, base_domain), r) for r in self.responses]
        scored.sort(key=lambda x: x[0], reverse=True)
        best = scored[0][1]
        req_url = str(best.get("url") or "")

        payload = None
        for r in reversed(self.requests):
            if str(r.get("url") or "") == req_url:
                payload = r.get("payload")
                break

        logger.info(f"[NETWORK] Best submission: {req_url} (score={scored[0][0]}, total_responses={len(self.responses)})")
        return payload or {}, best.get("body") or {}, int(best.get("status_code") or 0), req_url

# FIXED: Added localhost support and made predicate less restrictive
async def wait_for_submit_post_response(page: Page, base_url: str, timeout_ms: int = SUBMIT_WAIT_MS) -> Tuple[str, Dict[str, Any], Dict[str, Any], int]:
    base_host = host(base_url)
    # Allow common form handlers AND localhost for development
    allow = {"formspree.io", "getform.io", "api.web3forms.com", "hooks.zapier.com", "localhost", "127.0.0.1"}

    def predicate(resp) -> bool:
        try:
            req = resp.request
            if req.method != "POST":
                return False
            if is_noise_url(req.url):
                return False
            h = host(req.url)
            # Allow same host, subdomain, whitelisted hosts, OR localhost/127.0.0.1
            return (h == base_host or 
                    h.endswith("." + base_host) or 
                    h in allow or
                    "localhost" in h or
                    "127.0.0.1" in h)
        except Exception:
            return False

    try:
        resp = await page.wait_for_event("response", predicate=predicate, timeout=timeout_ms)
        req = resp.request
        status_code = int(resp.status or 0)
        payload: Dict[str, Any] = {}
        try:
            raw = req.post_data or ""
            if raw:
                try:
                    payload = json.loads(raw)
                except Exception:
                    try:
                        payload = {k: v[0] for k, v in parseqs(payloadraw, keep_blank_values=True).items()}

                    except Exception:
                        payload = {"raw": str(raw)[:2000]}
        except Exception as e:
            payload = {"error": f"payload_unavailable: {e}"}
        resp_data: Dict[str, Any] = {}
        try:
            txt = await resp.text()
            try:
                resp_data = json.loads(txt)
            except Exception:
                resp_data = {"raw_response": (txt or "")[:2000]}
        except Exception as e:
            resp_data = {"error": f"response_body_unavailable: {e}"}
        return req.url, payload, resp_data, status_code
    except Exception:
        return "", {}, {}, 0

# ---------- Contact page discovery ----------
CONTACT_HINT_WORDS = [
    "contact", "contact-us", "contactus", "get in touch", "getintouch", 
    "reach us", "enquiry", "inquiry", "support", "help", "connect",
    "contact us", "reach out", "write us", "email us", "touch",
    "get in touch with us", "message us", "ask", "question"
]
COMMON_CONTACT_PATHS = [
    "contact", "contact-us", "contactus", "get-in-touch", "reach-us", 
    "support", "help", "enquiry", "inquiry", "contact_us", "contact-page",
    "contact-form", "get-in-touch-with-us", "reach-out", "write-to-us",
    "email", "feedback", "message-us", "ask", "question", "questions",
    "help-center", "customer-support", "customer-service", "service"
]

def score_contact_link(text: str, href: str) -> int:
    t = (text or "").strip().lower()
    h = (href or "").strip().lower()
    if not h or h.startswith(("mailto:", "tel:", "javascript:")):
        return -999
    score = 0
    if "contact" in h:
        score += 20
    if "contact" in t:
        score += 20
    for w in CONTACT_HINT_WORDS:
        if w in t:
            score += 5
        if w in h:
            score += 5
    if any(x in h for x in ["privacy", "terms", "login", "signin", "signup", "register"]):
        score -= 10
    return score

async def post_nav_settle(page: Page) -> None:
    try:
        await page.wait_for_load_state("domcontentloaded", timeout=6000)
    except Exception:
        pass
    try:
        await page.wait_for_timeout(POST_NAV_SLEEP_MS)
    except Exception:
        pass

async def goto_best_contact_page(page: Page, base_url: str, contact_url_override: Optional[str] = None) -> str:
    async def safe_goto(u: str, wait_forms: bool = True) -> bool:
        for attempt_url in with_scheme(u):
            try:
                resp = await page.goto(attempt_url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
                if resp is not None and int(resp.status or 0) >= 400:
                    continue
                await post_nav_settle(page)
                await dismiss_overlays(page)
                if wait_forms:
                    await wait_for_formish_content(page)
                return True
            except PlaywrightTimeout:
                # If DOM partially loaded with links or inputs, keep going instead of wasting another 25s
                try:
                    if page.url and page.url != "about:blank" and await page.locator("a[href], input, textarea, form").count() > 0:
                        return True
                except Exception:
                    pass
                continue
            except Exception:
                continue
        return False

    if contact_url_override:
        await safe_goto(contact_url_override, wait_forms=True)
        return page.url

    await safe_goto(base_url, wait_forms=False)

    anchors: List[Dict[str, str]] = []
    try:
        anchors = await page.eval_on_selector_all(
            "a[href]",
            "(els) => els.map(a => ({href: a.getAttribute('href') || '', abs: a.href || '', text: (a.innerText || a.textContent || '').trim().slice(0,160)}))",
        )
    except Exception:
        anchors = []

    candidates: List[Tuple[int, str]] = []
    seen_targets = set()
    for a in anchors:
        href_abs = (a.get("abs") or "").strip()
        href_raw = (a.get("href") or "").strip()
        href = href_abs or href_raw
        txt = (a.get("text") or "").strip()
        sc = score_contact_link(txt, href)
        if sc >= 10 and (same_host(href_abs or page.url, base_url) or same_host(href_abs or page.url, page.url)):
            target = urljoin(page.url, href)
            if target not in seen_targets:
                seen_targets.add(target)
                candidates.append((sc, target))

    candidates.sort(key=lambda x: x[0], reverse=True)
    for _, target in candidates[:3]:
        ok = await safe_goto(target)
        if not ok:
            continue
        try:
            if await page.locator("input, textarea, select").count() > 0:
                return page.url
        except Exception:
            return page.url

    if candidates:
        # Fallback to top-scoring candidate even if form is rendered lazily or in iframe
        await safe_goto(candidates[0][1])
        return page.url

    try:
        ref = page.url or base_url
        parsed = urlparse(ref if urlparse(ref).scheme else "https://" + ref)
        origin = f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        origin = base_url.rstrip("/")

    for pth in COMMON_CONTACT_PATHS[:10]:
        cand = origin.rstrip("/") + "/" + pth.lstrip("/")
        ok = await safe_goto(cand)
        if not ok:
            continue
        try:
            if await page.locator("form").count() > 0 or await page.locator("input, textarea, select").count() > 3:
                return page.url
        except Exception:
            return page.url
    return page.url

# ---------- Core per-website ----------
def _resolve_cluster_values(
    pool: RandomValuePool,
    mapped_clusters: List[str],
    field_values: Dict[str, str],
    field_strategies: Dict[str, Dict[str, Any]],
) -> Dict[str, str]:
    """Resolve values per cluster honoring campaign strategies -> explicit values -> random pool."""
    alias_map = {
        "fullname": ["full_name", "fullname", "name"],
        "firstname": ["first_name", "firstname"],
        "lastname": ["last_name", "lastname"],
        "email": ["email", "sender_email"],
        "phone": ["phone"],
        "company": ["company"],
        "subject": ["subject", "subject_line"],
        "message": ["message", "message_body"],
        "website": ["website"],
        "addressline1": ["address", "addressline1"],
        "postalcode": ["zip_code", "postalcode"],
    }
    resolved: Dict[str, str] = {}
    for cluster in mapped_clusters:
        candidates = alias_map.get(cluster, [cluster])
        val = ""
        strategy_cfg = None
        for key in candidates:
            if key in field_strategies:
                strategy_cfg = field_strategies[key]
                break

        if isinstance(strategy_cfg, dict):
            strat = str(strategy_cfg.get("strategy") or "constant").lower()
            if strat in ("constant", "custom"):
                val = str(strategy_cfg.get("value") or strategy_cfg.get("constant_value") or "").strip()
            elif strat == "random":
                val = pool.random_value(cluster)

        if not val:
            for key in candidates:
                if field_values.get(key):
                    val = str(field_values[key]).strip()
                    break

        if not val:
            val = pool.random_value(cluster)

        resolved[cluster] = val
    return resolved


async def process_website_inner(
    db: MySQLDB,
    pool: RandomValuePool,
    context: BrowserContext,
    website_id: int,
    url: str,
    contact_url_override: Optional[str],
    mode: str = "fill",  # "scrape" = discover only, "fill" = fill + submit
    field_values: Optional[Dict[str, str]] = None,
    field_strategies: Optional[Dict[str, Dict[str, Any]]] = None,
    campaign_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Process a single website.
    Modes:
    - "scrape": Navigate to contact page, discover form fields, save mapping. No submit.
    - "fill": Full flow - navigate, discover, fill, submit, collect response.
    """
    logger.info("=" * 80)
    logger.info(f"[WEBSITE] {website_id} Processing: {url} (mode={mode})")
    logger.info("=" * 80)

    page = await context.new_page()
    page.set_default_timeout(ACTION_TIMEOUT_MS)

    capture = SubmitNetworkCapture()
    page.on("request", capture.on_request)
    page.on("response", capture.on_response)

    status = "failed"
    error = ""
    filled_fields = 0
    req_url = ""
    payload: Dict[str, Any] = {}
    resp_data: Dict[str, Any] = {}
    status_code = 0
    final_url = ""
    normalized_url = ""
    discovered_mapping: Dict[str, str] = {}

    try:
        if host(url) in SKIP_HOSTS_EXACT:
            status = "skipped"
            error = f"Skipped host {host(url)}"
            normalized_url = canonical_url(url)
            db.save_submission(website_id, url, normalized_url, status, 0, error)
            return {"website_id": website_id, "url": url, "status": status, "filled_fields": 0, "error": error, "mapping": {}}

        logger.info("[NAVIGATION] Finding contact page ...")
        final_url = await goto_best_contact_page(page, url, contact_url_override)
        normalized_url = canonical_url(final_url)
        logger.info(f"[NAVIGATION] Landed on {final_url}")

        await dismiss_overlays(page)

        has_captcha = await detect_captcha_on_page(page)

        fields = await discover_fields(page)
        visible_count = sum(1 for f in fields if f.visible)
        logger.info(f"[DISCOVERY] Found {visible_count} visible fields ({len(fields)} candidates)")
        log_field_report(fields)
        db.save_discovered_fields(website_id, fields)

        mapping = build_mapping(fields)
        discovered_mapping = mapping.copy()
        logger.info(f"[MAPPING] Final mapping: {mapping}")
        form_ok = has_contact_form_confidence(mapping)

        db.update_website_scan_status(website_id, form_found=form_ok, has_captcha=has_captcha, is_dead=False)

        contact_details_note = ""
        if not form_ok:
            cd = await discover_contact_details(page)
            parts = []
            if cd.get("emails"):
                parts.append("emails=" + ",".join(cd["emails"]))
            if cd.get("phones"):
                parts.append("phones=" + ",".join(cd["phones"]))
            if cd.get("whatsapp"):
                parts.append("whatsapp=" + ",".join(cd["whatsapp"]))
            if parts:
                contact_details_note = " | Contact details found: " + "; ".join(parts)

        if mode == "scrape":
            if has_captcha:
                status = "captcha"
                error = "Captcha detected on page (form fields discovered)" if form_ok else "Captcha detected on page before filling"
                await maybe_screenshot(page, "captcha_pre", website_id, final_url)
            elif not form_ok:
                status = "noform"
                error = f"Low confidence mapping. Need {sorted(CONFIDENCE_REQUIRED)} got {sorted(mapping.keys())}{contact_details_note}"
            else:
                status = "scraped"
                error = ""
            logger.info(f"[SCRAPE MODE] Discovered {len(mapping)} mapped fields (captcha={has_captcha}), not submitting")
            sub_id = db.save_submission(website_id, final_url, normalized_url, status, 0, error, campaign_id=campaign_id)
            return {"website_id": website_id, "url": final_url, "status": status, "filled_fields": 0, "error": error, "mapping": discovered_mapping, "contacturl": final_url, "fields_count": len(fields), "submission_id": sub_id}

        # FILL MODE: Full flow (never bypass CAPTCHA)
        if has_captcha:
            status = "captcha"
            error = "Captcha detected on page before filling"
            await maybe_screenshot(page, "captcha_pre", website_id, final_url)
            sub_id = db.save_submission(website_id, final_url, normalized_url, status, 0, error, campaign_id=campaign_id)
            return {"website_id": website_id, "url": final_url, "status": status, "filled_fields": 0, "error": error, "mapping": discovered_mapping, "submission_id": sub_id}

        if not form_ok:
            status = "noform"
            error = f"Low confidence mapping. Need {sorted(CONFIDENCE_REQUIRED)} got {sorted(mapping.keys())}"
            await maybe_screenshot(page, "noform", website_id, final_url)
            sub_id = db.save_submission(website_id, final_url, normalized_url, status, 0, error, campaign_id=campaign_id)
            return {"website_id": website_id, "url": final_url, "status": status, "filled_fields": 0, "error": error, "mapping": discovered_mapping, "submission_id": sub_id}
        mapped_clusters = list(mapping.keys())
        values = _resolve_cluster_values(pool, mapped_clusters, field_values or {}, field_strategies or {})
        
        # Fallback for empty values (especially important for required fields)
        fallbacks = {
            'fullname': 'Contact User',
            'email': 'contact@example.com',
            'subject': 'Inquiry',
            'message': 'I would like more information.',
            'company': 'Company Name',
            'phone': '1234567890'
        }
        for cluster in mapped_clusters:
            if not values.get(cluster):
                values[cluster] = fallbacks.get(cluster, 'N/A')
        
        logger.info(f"[FILL DEBUG] Generated values: {[(k, v[:30] if v else 'EMPTY') for k, v in values.items()]}")

        filled_fields, fill_errors, filled_report = await fill_fields(page, mapping, values)

        if filled_fields == 0:
            status = "nofill"
            error = "No fields were filled"
            if fill_errors:
                error = "; ".join(fill_errors)[:500]
            await maybe_screenshot(page, "nofill", website_id, final_url)
            db.save_submission(website_id, final_url, normalized_url, status, 0, error)
            return {"website_id": website_id, "url": final_url, "status": status, "filled_fields": 0, "error": error, "mapping": discovered_mapping}

        await dismiss_overlays(page)

        base_domain = host(final_url)

        # FIXED: Correct submit flow order
        # 1. Start network capture window BEFORE clicking submit
        capture.start_submit_window(seconds=SUBMIT_WINDOW_SECONDS)

        # 2. Click submit button
        submit_ok, submit_err = await submit_form(page)

        # 3. Wait for network activity to complete AFTER submit (early exit on POST response)
        if submit_ok and not DRY_RUN:
            logger.info(f"[SUBMIT] Waiting up to {POST_SUBMIT_WAIT_MS}ms for network activity...")
            await capture.wait_for_first_response(POST_SUBMIT_WAIT_MS)
            await page.wait_for_timeout(500)

        # 4. Stop capture after we've waited
        capture.stop_submit_window()
        
        # DEBUG: Log what was captured
        logger.info(f"[NETWORK DEBUG] Captured {len(capture.requests)} POST request(s)")
        logger.info(f"[NETWORK DEBUG] Captured {len(capture.responses)} POST response(s)")
        for i, req in enumerate(capture.requests):
            logger.info(f"[NETWORK DEBUG] Request {i+1}: {req.get('method')} {req.get('url')[:100]}")
        for i, resp in enumerate(capture.responses):
            logger.info(f"[NETWORK DEBUG] Response {i+1}: {resp.get('status_code')} {resp.get('url')[:100]}")

        # 5. Try to get the direct response via event listener (parallel approach)
        try:
            direct_req_url, direct_payload, direct_resp, direct_statuscode = await wait_for_submit_post_response(page,         	    base_url=final_url, timeout_ms=2000)  # Short timeout since we already waited
            
        except Exception:
            direct_req_url, direct_payload, direct_resp, direct_statuscode = "", {}, {}, 0

        # 6. Score all responses from capture window and pick the best
        payload2, resp2, statuscode2, requrl2 = capture.best_submission(base_domain=base_domain)
        logger.info(f"[NETWORK DEBUG] Best submission: status={statuscode2}, url={requrl2[:100] if requrl2 else 'None'}")

        # 7. Prefer captured responses, fall back to direct
        req_url = requrl2 or direct_req_url
        payload = payload2 or direct_payload
        resp_data = resp2 or direct_resp
        status_code = int(statuscode2 or direct_statuscode or 0)

        if not submit_ok:
            status = "failed"
            error = submit_err or "Submit click failed"
        else:
            if DRY_RUN:
                status = "dryrun"
                error = "DRY_RUN: submit skipped"
            elif await detect_captcha_on_page(page):
                status = "captcha"
                error = "Captcha detected after submit"
                await maybe_screenshot(page, "captcha_post", website_id, final_url)
            elif resp_data:
                interpreted, msg = interpret_submission_response(resp_data)
                if interpreted != "unknown":
                    status = interpreted
                    error = msg or ""
                elif await success_text_on_page(page):
                    status = "success"
                    error = ""
                else:
                    status = "unconfirmed"
                    error = msg or "POST response received without explicit confirmation of success"
            elif await success_text_on_page(page):
                status = "success"
                error = ""
            else:
                status = "failed"
                error = "Submit clicked but no POST response captured"

        submission_id = db.save_submission(
            website_id, final_url, normalized_url, status, filled_fields, error, campaign_id=campaign_id
        )
        if req_url or payload or resp_data:
            db.save_details(submission_id, req_url, payload, resp_data, status_code)
        
        # Send email notification for successful submissions
        if status == "success":
            try:
                from email_notifier import EmailNotifier
                notifier = EmailNotifier(db)
                notifier.send_notification(
                    website_url=url,
                    contact_url=final_url,
                    filled_values=values,
                    submission_id=submission_id,
                    campaign_id=campaign_id,
                    status_code=status_code
                )
            except Exception as email_err:
                logger.warning(f"[EMAIL] Failed to send notification: {email_err}")

        return {
            "website_id": website_id,
            "url": final_url,
            "status": status,
            "filled_fields": filled_fields,
            "error": error,
            "mapping": discovered_mapping,
            "submission_id": submission_id,
        }

    except Exception as e:
        status = "failed"
        error = str(e)[:500]
        if not normalized_url:
            normalized_url = canonical_url(final_url or url)
        await maybe_screenshot(page, "exception", website_id, final_url or url)
        db.update_website_scan_status(website_id, form_found=False, has_captcha=False, is_dead=True)
        sub_id = db.save_submission(
            website_id, final_url or url, normalized_url, status, filled_fields, error, campaign_id=campaign_id
        )
        return {
            "website_id": website_id,
            "url": final_url or url,
            "status": status,
            "filled_fields": filled_fields,
            "error": error,
            "submission_id": sub_id,
        }
    finally:
        try:
            await page.close()
        except Exception:
            pass

async def process_website(
    db: MySQLDB,
    pool: RandomValuePool,
    context: BrowserContext,
    website_id: int,
    url: str,
    contact_url_override: Optional[str] = None,
    mode: str = "fill",
    field_values: Optional[Dict[str, str]] = None,
    field_strategies: Optional[Dict[str, Dict[str, Any]]] = None,
    campaign_id: Optional[int] = None,
) -> Dict[str, Any]:
    try:
        return await asyncio.wait_for(
            process_website_inner(
                db=db,
                pool=pool,
                context=context,
                website_id=website_id,
                url=url,
                contact_url_override=contact_url_override,
                mode=mode,
                field_values=field_values,
                field_strategies=field_strategies,
                campaign_id=campaign_id,
            ),
            timeout=PER_WEBSITE_TIMEOUT_SEC,
        )
    except asyncio.TimeoutError:
        normalized = canonical_url(url)
        status = "timeout"
        error = f"Per-website timeout after {PER_WEBSITE_TIMEOUT_SEC}s"
        sub_id = db.save_submission(website_id, url, normalized, status, 0, error, campaign_id=campaign_id)
        return {"website_id": website_id, "url": url, "status": status, "filled_fields": 0, "error": error, "mapping": {}, "submission_id": sub_id}

# ---------- Batch processing ----------
async def run_batch(
    websites: List[Dict[str, Any]],
    on_progress=None,
    mode: str = "fill",
    field_values: Optional[Dict[str, str]] = None,
    field_strategies: Optional[Dict[str, Dict[str, Any]]] = None,
    campaign_id: Optional[int] = None,
) -> Dict[str, Any]:
    db = MySQLDB()
    pool = RandomValuePool()

    unique_websites = []
    seen_urls = set()
    for w in websites:
        u = str(w.get("url") or "").strip()
        if u and u not in seen_urls:
            unique_websites.append(w)
            seen_urls.add(u)

    total_planned = len(unique_websites)

    if sys.platform == 'win32':
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
            pass

    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=HEADLESS)
        context: BrowserContext = await browser.new_context()
        context.set_default_timeout(ACTION_TIMEOUT_MS)

        results: List[Dict[str, Any]] = []
        try:
            done = 0
            success = 0
            failed = 0
            captcha = 0
            scraped = 0
            for idx, w in enumerate(unique_websites, start=1):
                visit_url = str(w.get("contact_url_override") or w.get("url") or "").strip()
                key = canonical_url(visit_url)

                # FIXED: Only skip if ALLOW_RERUNS is False AND already processed (and not inside a campaign)
                if (not ALLOW_RERUNS) and (campaign_id is None) and key and db.already_processed(key):
                    logger.info(f"[BATCH] Skipping already-processed DB URL: {visit_url} (ALLOW_RERUNS={ALLOW_RERUNS})")
                    continue

                r = await process_website(
                    db=db,
                    pool=pool,
                    context=context,
                    website_id=int(w.get("website_id") or idx),
                    url=str(w.get("url") or "").strip(),
                    contact_url_override=w.get("contact_url_override"),
                    mode=mode,
                    field_values=field_values,
                    field_strategies=field_strategies,
                    campaign_id=campaign_id,
                )
                results.append(r)
                done += 1
                st = str(r.get("status") or "").lower()
                if st == "success":
                    success += 1
                elif st == "failed":
                    failed += 1
                elif st == "captcha":
                    captcha += 1
                elif st == "scraped":
                    scraped += 1

                if callable(on_progress):
                    try:
                        on_progress(
                            {
                                "done": done,
                                "total": total_planned,
                                "success": success,
                                "failed": failed,
                                "captcha": captcha,
                                "scraped": scraped,
                                "currentUrl": r.get("url"),
                                "mode": mode,
                            }
                        )
                    except Exception:
                        pass

                logger.info(f"[BATCH] Progress: {idx}/{len(unique_websites)} processed (mode={mode}).")

                if POLITE_DELAY_MS > 0:
                    await asyncio.sleep(POLITE_DELAY_MS / 1000.0)

        finally:
            try:
                await context.close()
            except Exception:
                pass
            try:
                await browser.close()
            except Exception:
                pass

    pool.close()
    db.close()

    summary = {
        "total": len(results),
        "success": sum(1 for r in results if r.get("status") == "success"),
        "failed": sum(1 for r in results if r.get("status") == "failed"),
        "captcha": sum(1 for r in results if r.get("status") == "captcha"),
        "noform": sum(1 for r in results if r.get("status") == "noform"),
        "nofill": sum(1 for r in results if r.get("status") == "nofill"),
        "dryrun": sum(1 for r in results if r.get("status") == "dryrun"),
        "timeout": sum(1 for r in results if r.get("status") == "timeout"),
        "scraped": sum(1 for r in results if r.get("status") == "scraped"),
        "mode": mode,
        "details": results,
    }

    logger.info("=" * 80)
    logger.info("[BATCH] Complete!")
    logger.info(json.dumps(summary, indent=2))
    logger.info("=" * 80)

    return summary

# ---------- Input normalization ----------
def normalize_websites_input(userdata: Union[Dict[str, Any], List[Any], None]) -> List[Dict[str, Any]]:
    if userdata is None:
        return []

    if isinstance(userdata, dict):
        websites = userdata.get("websites") or userdata.get("sites") or userdata.get("data") or userdata.get("urls")
    else:
        websites = userdata

    if websites is None:
        return []

    normalized: List[Dict[str, Any]] = []

    if isinstance(websites, list) and websites and isinstance(websites[0], str):
        for idx, u in enumerate(websites, start=1):
            u = str(u or "").strip()
            if not u:
                continue
            normalized.append({"website_id": idx, "url": u, "contact_url_override": None})
        return normalized

    if isinstance(websites, list):
        for idx, w in enumerate(websites, start=1):
            if not isinstance(w, dict):
                continue
            url = str(w.get("url") or w.get("website") or w.get("link") or "").strip()
            if not url:
                continue
            website_id = int(w.get("website_id") or w.get("websiteId") or w.get("id") or idx)
            contact_override = w.get("contact_url_override") or w.get("contactUrlOverride") or w.get("contacturl")
            normalized.append(
                {
                    "website_id": website_id,
                    "url": url,
                    "contact_url_override": str(contact_override).strip() if contact_override else None,
                }
            )

    return normalized

# ---------- Public wrapper ----------
def fill_all_forms(
    userdata: Optional[Union[Dict[str, Any], List[Any]]] = None,
    max_websites: Optional[int] = None,
    on_progress=None,
    mode: str = "fill",  # "scrape" or "fill"
):
    """
    Main entry point for form filling.
    Args:
        userdata: Website data or list of URLs
        max_websites: Limit number of websites to process
        on_progress: Progress callback
        mode: "scrape" = discover fields only, "fill" = full flow with submit
    """
    websites = normalize_websites_input(userdata)
    if not websites:
        limit = int(max_websites or DEFAULT_BATCH_LIMIT)
        websites = MySQLDB().load_websites_from_mysql(limit=limit)
    elif isinstance(max_websites, int) and max_websites > 0:
        websites = websites[: int(max_websites)]

    field_values: Dict[str, str] = {}
    field_strategies: Dict[str, Dict[str, Any]] = {}
    campaign_id: Optional[int] = None
    if isinstance(userdata, dict):
        campaign_id = userdata.get("campaignid") or userdata.get("campaign_id")
        if isinstance(userdata.get("fieldStrategies"), dict):
            field_strategies = userdata["fieldStrategies"]
        for k in ("name", "fullname", "full_name", "email", "subject", "message", "phone", "company"):
            if userdata.get(k):
                field_values[k] = str(userdata[k])

    coro = run_batch(
        websites=websites,
        on_progress=on_progress,
        mode=mode,
        field_values=field_values,
        field_strategies=field_strategies,
        campaign_id=int(campaign_id) if campaign_id is not None else None,
    )
    try:
        asyncio.get_running_loop()
        return coro
    except RuntimeError:
        return asyncio.run(coro)

def scrape_all_forms(
    userdata: Optional[Union[Dict[str, Any], List[Any]]] = None,
    max_websites: Optional[int] = None,
    on_progress=None,
):
    """
    Phase 1: Discovery only - navigate to contact pages and discover form fields.
    Does NOT fill or submit forms. Use this to scrape form structure first.
    Returns mapping information for each website.
    """
    return fill_all_forms(
        userdata=userdata,
        max_websites=max_websites,
        on_progress=on_progress,
        mode="scrape",
    )

# ---------- CLI ----------
def main() -> None:
    websites = MySQLDB().load_websites_from_mysql(limit=DEFAULT_BATCH_LIMIT)
    asyncio.run(run_batch(websites))

if __name__ == "__main__":
    main()

# Backward-compatible aliases for fastapi_backend.py
fillallforms = fill_all_forms
scrapeallforms = scrape_all_forms
