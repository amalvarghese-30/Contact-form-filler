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
# IMPORTANT: You want real submit, so default is False.
# Set env DRY_RUN=1 only if you explicitly want to disable actual submission.
DRY_RUN = env_bool("DRY_RUN", False)

# IMPORTANT: Allow reruns by default (restart campaign will insert new rows)
# Set env ALLOW_RERUNS=0 to skip already-processed URLs
ALLOW_RERUNS = env_bool("ALLOW_RERUNS", True)

# Time to wait after clicking submit button for network activity to complete
POST_SUBMIT_WAIT_MS = env_int("POST_SUBMIT_WAIT_MS", 10000)  # 10 seconds (increased for better response capture)

# Number of URLs to process concurrently (default: 1 for safety, 2-5 recommended for speed)
CONCURRENT_BROWSERS = env_int("CONCURRENT_BROWSERS", 1)

POLITE_DELAY_MS = env_int("POLITE_DELAY_MS", 300)

# Random pool config
RANDOM_POOL_TABLE = env_str("RANDOM_POOL_TABLE", "random_value_pool")
RANDOM_POOL_RANDOM_SQL = env_str("RANDOM_POOL_RANDOM_SQL", "RAND()")  # MySQL RAND()

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
    return host(a) == host(b)


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
    try:
        await page.wait_for_selector("form, input, textarea, select, iframe", timeout=8000)
    except Exception:
        pass
    try:
        await page.wait_for_timeout(600)
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
        cur = self.conn.cursor()
        cur.execute(
            f"SELECT value FROM {RANDOM_POOL_TABLE} WHERE field_concept=%s ORDER BY {RANDOM_POOL_RANDOM_SQL} LIMIT 1",
            (concept,),
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
        # Note: Unique index is created but duplicate inserts will fail
        # If you want to allow reruns with new rows, you may need to drop this index in DB
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
        self, website_id: int, url: str, normalized_url: str, status: str, filled_fields: int, error: str
    ) -> int:
        cur = self.conn.cursor()
        try:
            cur.execute(
                f"""
                INSERT INTO {FORM_SUBMISSIONS_TABLE}
                  (website_id, url, normalized_url, status, filled_fields, error)
                VALUES
                  (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                  status = VALUES(status),
                  filled_fields = VALUES(filled_fields),
                  error = VALUES(error),
                  created_at = CURRENT_TIMESTAMP
                """,
                (
                    int(website_id or 0),
                    url or "",
                    normalized_url or "",
                    status or "",
                    int(filled_fields or 0),
                    (error or "")[:2000],
                ),
            )
            self.conn.commit()
            submission_id = int(cur.lastrowid or 0)
            logger.info(f"[DB] Saved submission: id={submission_id} website_id={website_id} status={status}")
            return submission_id

        except Exception as e:
            # CRITICAL: don't swallow DB errors silently
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
    b = blob_field(f)
    if norm(f.type) in {"tel", "phone"}:
        return True
    return any(k in b for k in ["phone", "mobile", "tel", "telephone", "whatsapp"])


def looks_like_email(f: FieldMeta) -> bool:
    b = blob_field(f)
    if "email" in norm(f.type):
        return True
    return "email" in b


def looks_like_message(f: FieldMeta) -> bool:
    b = blob_field(f)
    if norm(f.tag) == "textarea":
        return True
    return any(k in b for k in ["message", "comment", "enquiry", "inquiry"])


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
                return t.strip()[:200]
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
                form_scope = f"form:nth-of-type({int(forms_info[0]['idx']) + 1})"
    except Exception:
        form_scope = None

    js = f"""
      () => {{
        const formSel = {json.dumps(form_scope)};
        const scope = formSel ? document.querySelector(formSel) : document;
        if (!scope) return [];
        const els = Array.from(scope.querySelectorAll("input, textarea, select"));
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
          else if (name && formIndex >= 0) selector = `form:nth-of-type(${{formIndex+1}}) ${{tag}}[name='${{name.replace(/'/g,"")}}']`;
          else if (name) selector = `${{tag}}[name='${{name.replace(/'/g,"")}}']`;
          else selector = `${{tag}}:nth-of-type(${{i+1}})`;
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


async def discover_fields(page: Page) -> List[FieldMeta]:
    await dismiss_overlays(page)
    await wait_for_formish_content(page)

    metas = await discover_fields_from_root(page, iframe_selector=None)
    if metas:
        return metas

    for fr in page.frames:
        if fr == page.main_frame:
            continue
        iframe_sel = await iframe_selector_for_frame(page, fr)
        if not iframe_sel:
            continue
        try:
            fm = await discover_fields_from_root(fr, iframe_selector=iframe_sel)
            if fm:
                return fm
        except Exception:
            continue
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
    if cluster == "message" and norm(f.tag) == "textarea":
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
        if best_sel and best_score >= 8:
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

            if cluster == "consent":
                try:
                    await loc.check(timeout=ACTION_TIMEOUT_MS)
                except Exception:
                    await loc.click(timeout=ACTION_TIMEOUT_MS)
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

    def start_submit_window(self, seconds: float = SUBMIT_WINDOW_SECONDS) -> None:
        self.enabled = True
        self.start_ts = time.time()
        self.end_ts = self.start_ts + float(seconds)
        self.requests.clear()
        self.responses.clear()
        logger.info(f"[NETWORK] Submit window started ({int(seconds)}s)")

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
                        payload = {k: v[0] for k, v in parse_qs(payload_raw).items()}
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


async def wait_for_submit_post_response(page: Page, base_url: str, timeout_ms: int = SUBMIT_WAIT_MS) -> Tuple[str, Dict[str, Any], Dict[str, Any], int]:
    base_host = host(base_url)
    allow = {"formspree.io", "getform.io", "api.web3forms.com", "hooks.zapier.com"}

    def predicate(resp) -> bool:
        try:
            req = resp.request
            if req.method != "POST":
                return False
            if is_noise_url(req.url):
                return False
            h = host(req.url)
            return (h == base_host) or h.endswith("." + base_host) or (h in allow)
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
                        payload = {k: v[0] for k, v in parse_qs(raw).items()}
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
CONTACT_HINT_WORDS = ["contact", "contact-us", "contactus", "get in touch", "getintouch", "reach us", "enquiry", "inquiry", "support", "help", "connect"]
COMMON_CONTACT_PATHS = ["contact", "contact-us", "contactus", "get-in-touch", "reach-us", "support", "help", "enquiry", "inquiry"]


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
    async def safe_goto(u: str) -> bool:
        for attempt_url in with_scheme(u):
            try:
                resp = await page.goto(attempt_url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
                if resp is not None and int(resp.status or 0) >= 400:
                    continue
                await post_nav_settle(page)
                await dismiss_overlays(page)
                await wait_for_formish_content(page)
                return True
            except Exception:
                continue
        return False

    if contact_url_override:
        await safe_goto(contact_url_override)
        return page.url

    await safe_goto(base_url)

    anchors: List[Dict[str, str]] = []
    try:
        anchors = await page.eval_on_selector_all(
            "a[href]",
            "(els) => els.map(a => ({href: a.getAttribute('href') || '', abs: a.href || '', text: (a.innerText || a.textContent || '').trim().slice(0,160)}))",
        )
    except Exception:
        anchors = []

    best_href = None
    best_score = -999
    for a in anchors:
        href_abs = (a.get("abs") or "").strip()
        href_raw = (a.get("href") or "").strip()
        href = href_abs or href_raw
        txt = (a.get("text") or "").strip()
        sc = score_contact_link(txt, href)
        if sc > best_score and same_host(href_abs or page.url, base_url):
            best_score = sc
            best_href = href

    if best_href and best_score >= 15:
        target = urljoin(page.url, best_href)
        ok = await safe_goto(target)
        if ok:
            return page.url

    try:
        parsed = urlparse(base_url if urlparse(base_url).scheme else "https://" + base_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
    except Exception:
        origin = base_url.rstrip("/")

    for pth in COMMON_CONTACT_PATHS:
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
async def process_website_inner(
    db: MySQLDB,
    pool: RandomValuePool,
    context: BrowserContext,
    website_id: int,
    url: str,
    contact_url_override: Optional[str],
    mode: str = "fill",  # "scrape" = discover only, "fill" = fill + submit
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
    page.on("request", lambda req: asyncio.create_task(capture.on_request(req)))
    page.on("response", lambda resp: asyncio.create_task(capture.on_response(resp)))

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

        if await detect_captcha_on_page(page):
            status = "captcha"
            error = "Captcha detected on page before filling"
            await maybe_screenshot(page, "captcha_pre", website_id, final_url)
            db.save_submission(website_id, final_url, normalized_url, status, 0, error)
            return {"website_id": website_id, "url": final_url, "status": status, "filled_fields": 0, "error": error, "mapping": {}}

        fields = await discover_fields(page)
        visible_count = sum(1 for f in fields if f.visible)
        logger.info(f"[DISCOVERY] Found {visible_count} visible fields (candidates={len(fields)})")

        log_field_report(fields)

        mapping = build_mapping(fields)
        discovered_mapping = mapping.copy()
        logger.info(f"[MAPPING] Final mapping: {mapping}")

        # ===== SCRAPE MODE: Just discover fields, don't fill/submit =====
        if mode == "scrape":
            if not CONFIDENCE_REQUIRED.issubset(set(mapping.keys())):
                status = "noform"
                error = f"Low confidence mapping. Need {sorted(CONFIDENCE_REQUIRED)} got {sorted(mapping.keys())}"
            else:
                status = "scraped"
                error = ""
            
            logger.info(f"[SCRAPE MODE] Discovered {len(mapping)} mapped fields, not submitting")
            db.save_submission(website_id, final_url, normalized_url, status, 0, error)
            return {
                "website_id": website_id, 
                "url": final_url, 
                "status": status, 
                "filled_fields": 0, 
                "error": error,
                "mapping": discovered_mapping,
                "contact_url": final_url,
            }

        # ===== FILL MODE: Full flow =====
        if not CONFIDENCE_REQUIRED.issubset(set(mapping.keys())):
            status = "noform"
            error = f"Low confidence mapping. Need {sorted(CONFIDENCE_REQUIRED)} got {sorted(mapping.keys())}"
            await maybe_screenshot(page, "noform", website_id, final_url)
            db.save_submission(website_id, final_url, normalized_url, status, 0, error)
            return {"website_id": website_id, "url": final_url, "status": status, "filled_fields": 0, "error": error, "mapping": discovered_mapping}

        mapped_clusters = list(mapping.keys())
        values = pool.values_for_concepts(mapped_clusters)

        filled_fields, fill_errors, filled_report = await fill_fields(page, mapping, values)
        if filled_fields == 0:
            status = "nofill"
            error = "No fields were filled"
            if fill_errors:
                error = " | ".join(fill_errors)[:500]
            await maybe_screenshot(page, "nofill", website_id, final_url)
            db.save_submission(website_id, final_url, normalized_url, status, 0, error)
            return {"website_id": website_id, "url": final_url, "status": status, "filled_fields": 0, "error": error, "mapping": discovered_mapping}

        await dismiss_overlays(page)

        # Start network capture window
        capture.start_submit_window(seconds=SUBMIT_WINDOW_SECONDS)

        # Click submit
        submit_ok, submit_err = await submit_form(page)
        
        # IMPORTANT: Wait for network activity to complete after submit
        if submit_ok and not DRY_RUN:
            logger.info(f"[SUBMIT] Waiting {POST_SUBMIT_WAIT_MS}ms for network activity...")
            await page.wait_for_timeout(POST_SUBMIT_WAIT_MS)
        
        # Try to get the direct response via event listener
        direct_req_url, direct_payload, direct_resp, direct_status_code = await wait_for_submit_post_response(
            page, base_url=final_url, timeout_ms=SUBMIT_WAIT_MS
        )

        # Stop capture after we've waited
        capture.stop_submit_window()

        # Get the base domain for scoring
        base_domain = host(final_url)

        if direct_req_url:
            req_url = direct_req_url
            payload = direct_payload or {}
            resp_data = direct_resp or {}
            status_code = int(direct_status_code or 0)
        else:
            # Use the improved best_submission with domain scoring
            payload2, resp2, status_code2, req_url2 = capture.best_submission(base_domain=base_domain)
            req_url = req_url2 or ""
            payload = payload2 or {}
            resp_data = resp2 or {}
            status_code = int(status_code2 or 0)

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
                else:
                    status = "success"
                    error = msg or "Unknown response; best-effort success"
            elif await success_text_on_page(page):
                status = "success"
                error = ""
            else:
                status = "failed"
                error = "Submit clicked but no POST response captured"

        submission_id = db.save_submission(website_id, final_url, normalized_url, status, filled_fields, error)
        if req_url or payload or resp_data:
            db.save_details(submission_id, req_url, payload, resp_data, status_code)

        return {"website_id": website_id, "url": final_url, "status": status, "filled_fields": filled_fields, "error": error, "mapping": discovered_mapping}

    except Exception as e:
        status = "failed"
        error = str(e)[:500]
        if not normalized_url:
            normalized_url = canonical_url(final_url or url)
        await maybe_screenshot(page, "exception", website_id, final_url or url)
        db.save_submission(website_id, final_url or url, normalized_url, status, filled_fields, error)
        return {"website_id": website_id, "url": final_url or url, "status": status, "filled_fields": filled_fields, "error": error}

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
    mode: str = "fill",  # "scrape" or "fill"
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
            ),
            timeout=PER_WEBSITE_TIMEOUT_SEC,
        )
    except asyncio.TimeoutError:
        normalized = canonical_url(url)
        status = "timeout"
        error = f"Per-website timeout after {PER_WEBSITE_TIMEOUT_SEC}s"
        db.save_submission(website_id, url, normalized, status, 0, error)
        return {"website_id": website_id, "url": url, "status": status, "filled_fields": 0, "error": error, "mapping": {}}


# ---------- Batch runner ----------
async def run_batch(websites: List[Dict[str, Any]], on_progress=None, mode: str = "fill") -> Dict[str, Any]:
    """
    Process a batch of websites.
    
    Args:
        websites: List of website dicts with 'url', 'website_id', optional 'contact_url_override'
        on_progress: Optional callback for progress updates
        mode: "scrape" = discover fields only, "fill" = full flow with submit
    """
    logger.info("=" * 80)
    logger.info(f"[BATCH] Starting. websites={len(websites)} mode={mode} DRY_RUN={DRY_RUN} ALLOW_RERUNS={ALLOW_RERUNS}")
    logger.info("=" * 80)

    db = MySQLDB()
    pool = RandomValuePool()

    seen_in_run = set()
    unique_websites: List[Dict[str, Any]] = []
    for w in websites:
        visit_url = str(w.get("contact_url_override") or w.get("url") or "").strip()
        key = canonical_url(visit_url)
        if not key:
            continue
        if key in seen_in_run:
            logger.info(f"[BATCH] Skipping duplicate in-run URL: {visit_url}")
            continue
        seen_in_run.add(key)
        unique_websites.append(w)

    results: List[Dict[str, Any]] = []

    # CRITICAL Windows fix: Ensure event loop policy is set for this async context
    if sys.platform == 'win32':
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
            pass

    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=HEADLESS)
        context: BrowserContext = await browser.new_context()
        context.set_default_timeout(ACTION_TIMEOUT_MS)

        try:
            total_planned = len(unique_websites)
            done = 0
            success = 0
            failed = 0
            captcha = 0
            scraped = 0

            for idx, w in enumerate(unique_websites, start=1):
                visit_url = str(w.get("contact_url_override") or w.get("url") or "").strip()
                key = canonical_url(visit_url)

                # FIXED: Only skip if ALLOW_RERUNS is False AND already processed
                if (not ALLOW_RERUNS) and key and db.already_processed(key):
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

    return []


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

    coro = run_batch(websites=websites, on_progress=on_progress, mode=mode)
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
