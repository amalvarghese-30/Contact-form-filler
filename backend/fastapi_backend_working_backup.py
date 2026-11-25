print("RUNNING:", __file__)

# Fix for Windows: Set event loop policy for subprocess support (required for Playwright)
import sys
import asyncio
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI, BackgroundTasks, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime
from typing import Dict, Any, List, Optional


import mysql.connector
import traceback
import csv
import io
import json
import time
import os

print("[1/3] Importing form_filler...")
from form_filler import fillallforms, scrapeallforms
print("[2/3] Importing auto_concept_mapper...")
from auto_concept_mapper import get_concept_details
print("[3/3] Loading optional modules...")

# Optional imports (campaign pipeline)
try:
    from advanced_scraper_mysql import scrape_websites_by_ids as scraper_scrape
except Exception:
    scraper_scrape = None

try:
    from cluster_raw_fields import cluster_websites
except Exception:
    cluster_websites = None

print("[✓] All imports complete!")


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "http://localhost",
        "*",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DBCONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "",
    "database": "form_insights",
}


def getconn():
    return mysql.connector.connect(**DBCONFIG)


# ----- Tables -----
RAW_FIELDS_TABLE = "raw_fields"
WEBSITES_TABLE = "websites"
RANDOM_POOL_TABLE = "random_value_pool"

CAMPAIGNS_TABLE = "campaigns"
CAMPAIGN_WEBSITES_TABLE = "campaign_websites"
CAMPAIGN_FIELD_STRATEGY_TABLE = "campaign_field_strategy"
CAMPAIGN_RUNS_TABLE = "campaign_runs"

# ----- Websites table columns -----
COL_TS = "timestamp"
COL_FORM_FOUND = "form_found"
COL_HAS_CAPTCHA = "has_captcha"
COL_IS_DEAD = "is_dead"

# ----- Raw fields columns -----
COL_RF_WEBSITE_ID = "website_id"
COL_RF_FIELD_NAME = "field_name"
COL_RF_FIELD_TYPE = "field_type"
COL_RF_PLACEHOLDER = "placeholder"
COL_RF_CLUSTER_KEY = "cluster_key"


def ensure_tables():
    conn = getconn()
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {CAMPAIGNS_TABLE} (
              id INT AUTO_INCREMENT PRIMARY KEY,
              name VARCHAR(255) NOT NULL,
              description TEXT NULL,
              sender_name VARCHAR(255) NULL,
              sender_email VARCHAR(255) NULL,
              subject_line VARCHAR(255) NULL,
              message_body TEXT NULL,
              max_websites INT NOT NULL DEFAULT 50,
              status VARCHAR(30) NOT NULL DEFAULT 'draft',
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
            """
        )

        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {CAMPAIGN_WEBSITES_TABLE} (
              id INT AUTO_INCREMENT PRIMARY KEY,
              campaign_id INT NOT NULL,
              website_id INT NOT NULL,
              website_url VARCHAR(2048) NOT NULL,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              INDEX idx_cw_campaign (campaign_id),
              INDEX idx_cw_website (website_id)
            )
            """
        )

        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {CAMPAIGN_FIELD_STRATEGY_TABLE} (
              id INT AUTO_INCREMENT PRIMARY KEY,
              campaign_id INT NOT NULL,
              field_concept VARCHAR(255) NOT NULL,
              strategy VARCHAR(30) NOT NULL DEFAULT 'constant',
              constant_value TEXT NULL,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              INDEX idx_cfs_campaign (campaign_id),
              INDEX idx_cfs_concept (field_concept)
            )
            """
        )

        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {CAMPAIGN_RUNS_TABLE} (
              id INT AUTO_INCREMENT PRIMARY KEY,
              campaign_id INT NOT NULL,
              status VARCHAR(30) NOT NULL DEFAULT 'queued',
              progress INT NOT NULL DEFAULT 0,
              total INT NOT NULL DEFAULT 0,
              results JSON NULL,
              error TEXT NULL,
              started_at TIMESTAMP NULL,
              finished_at TIMESTAMP NULL,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
              INDEX idx_campaign_id (campaign_id)
            )
            """
        )

        conn.commit()
    finally:
        cur.close()
        conn.close()

# ensure_tables() - DISABLED - tables already exist
# If you need to create tables, run this once manually


# ---------------- Models ----------------
class FillFormsRequest(BaseModel):
    userdata: Dict[str, Any] = {}
    maxwebsites: int = 50
    maxWebsites: Optional[int] = None
    userData: Optional[Dict[str, Any]] = None


class CampaignRequest(BaseModel):
    name: str
    description: Optional[str] = None
    senderName: Optional[str] = None
    senderEmail: Optional[str] = None
    subjectLine: Optional[str] = None
    messageBody: Optional[str] = None
    maxWebsites: int = 50
    websiteIds: List[Any] = []  # URLs
    fieldStrategies: Dict[str, Dict[str, Any]] = {}  # concept -> {strategy,value}


# ---------------- Helpers ----------------
def db_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False)


def ensure_websites_exist(urls: List[str]) -> List[int]:
    if not urls:
        return []

    conn = getconn()
    cur = conn.cursor(dictionary=True)
    try:
        out_ids: List[int] = []
        for u in urls:
            url = str(u).strip()
            if not url:
                continue

            cur.execute(f"SELECT id FROM {WEBSITES_TABLE} WHERE url=%s LIMIT 1", (url,))
            row = cur.fetchone()
            if row:
                out_ids.append(int(row["id"]))
                continue

            cur2 = conn.cursor()
            cur2.execute(
                f"""
                INSERT INTO {WEBSITES_TABLE} (url, {COL_FORM_FOUND}, {COL_HAS_CAPTCHA}, {COL_IS_DEAD}, {COL_TS})
                VALUES (%s, 0, 0, 0, NULL)
                """,
                (url,),
            )
            out_ids.append(int(cur2.lastrowid))
            cur2.close()

        conn.commit()
        return out_ids
    finally:
        cur.close()
        conn.close()


def create_run(campaign_id: int) -> int:
    conn = getconn()
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            INSERT INTO {CAMPAIGN_RUNS_TABLE} (campaign_id, status, progress, total, started_at)
            VALUES (%s,%s,%s,%s,NOW())
            """,
            (campaign_id, "running", 0, 0),
        )
        run_id = int(cur.lastrowid)
        conn.commit()
        return run_id
    finally:
        cur.close()
        conn.close()


def update_run(run_id: int, retries: int = 8, delay: float = 0.5, **fields):
    if not fields:
        return

    for attempt in range(retries):
        try:
            conn = getconn()
            cur = conn.cursor()
            try:
                sets = []
                vals = []
                for k, v in fields.items():
                    sets.append(f"{k}=%s")
                    vals.append(v)
                sql = f"UPDATE {CAMPAIGN_RUNS_TABLE} SET {', '.join(sets)} WHERE id=%s"
                vals.append(run_id)
                cur.execute(sql, tuple(vals))
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
            raise


def set_campaign_status(campaign_id: int, status: str):
    conn = getconn()
    cur = conn.cursor()
    try:
        cur.execute(f"UPDATE {CAMPAIGNS_TABLE} SET status=%s WHERE id=%s", (status, campaign_id))
        conn.commit()
    finally:
        cur.close()
        conn.close()


def get_campaign_status_db(campaign_id: int) -> str:
    conn = getconn()
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT status FROM {CAMPAIGNS_TABLE} WHERE id=%s", (campaign_id,))
        row = cur.fetchone()
        return (row[0] if row else "unknown")
    finally:
        cur.close()
        conn.close()


def is_paused(campaign_id: int) -> bool:
    return get_campaign_status_db(campaign_id) == "paused"


def get_last_run(campaign_id: int) -> Optional[Dict[str, Any]]:
    conn = getconn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            f"""
            SELECT id, status, progress, total, results, error, started_at, finished_at
            FROM {CAMPAIGN_RUNS_TABLE}
            WHERE campaign_id=%s
            ORDER BY id DESC
            LIMIT 1
            """,
            (campaign_id,),
        )
        r = cur.fetchone()
        if not r:
            return None

        if r.get("results"):
            try:
                r["results"] = json.loads(r["results"])
            except Exception:
                pass

        return r
    finally:
        cur.close()
        conn.close()


# ---------------- Dashboard endpoints ----------------
@app.get("/api/websites")
def get_websites():
    conn = getconn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(f"SELECT COUNT(*) AS total FROM {WEBSITES_TABLE}")
        total = int(cur.fetchone()["total"])

        cur.execute(f"SELECT COUNT(*) AS visited FROM {WEBSITES_TABLE} WHERE {COL_TS} IS NOT NULL")
        visited = int(cur.fetchone()["visited"])

        cur.execute(
            f"SELECT COUNT(*) AS formstotal FROM {WEBSITES_TABLE} "
            f"WHERE {COL_TS} IS NOT NULL AND {COL_FORM_FOUND} = 1"
        )
        formstotal = int(cur.fetchone()["formstotal"])

        cur.execute(
            f"SELECT COUNT(*) AS captchatotal FROM {WEBSITES_TABLE} "
            f"WHERE {COL_TS} IS NOT NULL AND {COL_HAS_CAPTCHA} = 1"
        )
        captchatotal = int(cur.fetchone()["captchatotal"])

        cur.execute(
            f"""
            SELECT COUNT(*) AS deadsites
            FROM {WEBSITES_TABLE}
            WHERE {COL_TS} IS NOT NULL AND {COL_FORM_FOUND} = 0 AND {COL_HAS_CAPTCHA} = 0
            """
        )
        deadsites = int(cur.fetchone()["deadsites"])

        cur.execute(
            f"""
            SELECT COUNT(*) AS zerofieldsites FROM (
              SELECT w.id
              FROM {WEBSITES_TABLE} w
              LEFT JOIN {RAW_FIELDS_TABLE} f ON f.{COL_RF_WEBSITE_ID} = w.id
              WHERE w.{COL_TS} IS NOT NULL
              GROUP BY w.id
              HAVING COUNT(f.{COL_RF_WEBSITE_ID}) = 0
            ) AS t
            """
        )
        zerofieldsites = int(cur.fetchone()["zerofieldsites"])

        return {
            "total": total,
            "visited": visited,
            "formstotal": formstotal,
            "captchatotal": captchatotal,
            "deadsites": deadsites,
            "zerofieldsites": zerofieldsites,
            "formsTotal": formstotal,
            "captchaTotal": captchatotal,
            "deadSites": deadsites,
            "zeroFieldSites": zerofieldsites,
        }
    finally:
        cur.close()
        conn.close()


@app.get("/api/websites-with-fields")
def get_websites_with_fields(skip: int = 0, limit: int = 10):
    conn = getconn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            f"""
            SELECT w.id, w.url, COUNT(*) AS fieldcount
            FROM {WEBSITES_TABLE} w
            JOIN {RAW_FIELDS_TABLE} f ON w.id = f.{COL_RF_WEBSITE_ID}
            GROUP BY w.id
            ORDER BY w.id DESC
            LIMIT %s OFFSET %s
            """,
            (limit, skip),
        )
        websites = cur.fetchall() or []

        items = []
        cur2 = conn.cursor(dictionary=True)
        for ws in websites:
            cur2.execute(
                f"""
                SELECT
                  {COL_RF_FIELD_NAME} AS fieldname,
                  {COL_RF_FIELD_TYPE} AS fieldtype,
                  {COL_RF_PLACEHOLDER} AS placeholder,
                  {COL_RF_CLUSTER_KEY} AS clusterkey
                FROM {RAW_FIELDS_TABLE}
                WHERE {COL_RF_WEBSITE_ID} = %s
                ORDER BY {COL_RF_FIELD_NAME}
                """,
                (ws["id"],),
            )
            fields = cur2.fetchall() or []
            items.append({"id": ws["id"], "url": ws["url"], "fieldcount": ws["fieldcount"], "fields": fields})
        cur2.close()

        return {"items": items}
    finally:
        cur.close()
        conn.close()


@app.get("/api/field-frequency")
def get_field_frequency():
    conn = getconn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            f"""
            SELECT {COL_RF_FIELD_NAME} AS field, COUNT(*) AS frequency
            FROM {RAW_FIELDS_TABLE}
            WHERE {COL_RF_FIELD_NAME} IS NOT NULL AND TRIM({COL_RF_FIELD_NAME}) <> ''
            GROUP BY {COL_RF_FIELD_NAME}
            ORDER BY frequency DESC
            """
        )
        return {"items": cur.fetchall() or []}
    finally:
        cur.close()
        conn.close()


@app.get("/api/field-mapping")
def get_field_mapping():
    conn = getconn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            f"""
            SELECT COALESCE({COL_RF_CLUSTER_KEY}, 'unknown') AS clusterkey, COUNT(*) AS fieldcount
            FROM {RAW_FIELDS_TABLE}
            GROUP BY COALESCE({COL_RF_CLUSTER_KEY}, 'unknown')
            ORDER BY fieldcount DESC
            """
        )
        return {"items": cur.fetchall() or []}
    finally:
        cur.close()
        conn.close()


@app.get("/api/dead-sites")
def get_dead_sites(skip: int = 0, limit: int = 10):
    conn = getconn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            f"""
            SELECT COUNT(*) AS totaldead
            FROM {WEBSITES_TABLE}
            WHERE {COL_TS} IS NOT NULL AND {COL_FORM_FOUND} = 0 AND {COL_HAS_CAPTCHA} = 0
            """
        )
        totaldead = int(cur.fetchone()["totaldead"])

        cur.execute(
            f"""
            SELECT id, url
            FROM {WEBSITES_TABLE}
            WHERE {COL_TS} IS NOT NULL AND {COL_FORM_FOUND} = 0 AND {COL_HAS_CAPTCHA} = 0
            ORDER BY id DESC
            LIMIT %s OFFSET %s
            """,
            (limit, skip),
        )
        return {"total": totaldead, "items": cur.fetchall() or []}
    finally:
        cur.close()
        conn.close()


@app.get("/api/zero-field-sites")
def get_zero_field_sites(skip: int = 0, limit: int = 10):
    conn = getconn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            f"""
            SELECT COUNT(*) AS totalzero FROM (
              SELECT w.id
              FROM {WEBSITES_TABLE} w
              LEFT JOIN {RAW_FIELDS_TABLE} f ON f.{COL_RF_WEBSITE_ID} = w.id
              WHERE w.{COL_TS} IS NOT NULL
              GROUP BY w.id
              HAVING COUNT(f.{COL_RF_WEBSITE_ID}) = 0
            ) AS t
            """
        )
        totalzero = int(cur.fetchone()["totalzero"])

        cur.execute(
            f"""
            SELECT w.id, w.url
            FROM {WEBSITES_TABLE} w
            LEFT JOIN {RAW_FIELDS_TABLE} f ON f.{COL_RF_WEBSITE_ID} = w.id
            WHERE w.{COL_TS} IS NOT NULL
            GROUP BY w.id
            HAVING COUNT(f.{COL_RF_WEBSITE_ID}) = 0
            ORDER BY w.id DESC
            LIMIT %s OFFSET %s
            """,
            (limit, skip),
        )
        return {"total": totalzero, "items": cur.fetchall() or []}
    finally:
        cur.close()
        conn.close()


# ---------------- Template + Random pool ----------------
@app.get("/api/fill-form-template")
def get_fill_form_template():
    concepts = get_concept_details() or []

    def prev(v: Any) -> str:
        return str(v or "").strip().lower()

    high = [c for c in concepts if prev(c.get("fieldprevalence")) == "high"]
    medium = [c for c in concepts if prev(c.get("fieldprevalence")) == "medium"]
    low = [c for c in concepts if prev(c.get("fieldprevalence")) == "low"]

    if not high and not medium and not low and concepts:
        high = concepts

    return {"commonFields": high, "optionalFields": medium, "rareFields": low}


@app.get("/api/concepts-debug")
def concepts_debug(limit: int = 20):
    concepts = get_concept_details() or []
    return {
        "count": len(concepts),
        "sample": concepts[: max(0, int(limit))],
        "fieldprevalence_values": sorted(list({str(c.get("fieldprevalence")) for c in concepts})),
    }


@app.post("/api/random-values/import-csv")
async def import_random_values_csv(fieldconcept: str = Form(...), csvfile: UploadFile = File(...)):
    try:
        raw = (await csvfile.read()).decode("utf-8", errors="ignore")
        reader = csv.reader(io.StringIO(raw))
        values: List[str] = []
        for row in reader:
            if not row:
                continue
            v = (row[0] or "").strip()
            if v:
                values.append(v)

        conn = getconn()
        cur = conn.cursor()
        try:
            cur.execute(f"DELETE FROM {RANDOM_POOL_TABLE} WHERE field_concept = %s", (fieldconcept,))
            if values:
                cur.executemany(
                    f"INSERT INTO {RANDOM_POOL_TABLE} (field_concept, value) VALUES (%s, %s)",
                    [(fieldconcept, v) for v in values],
                )
            conn.commit()
        finally:
            cur.close()
            conn.close()

        return {"ok": True, "fieldconcept": fieldconcept, "imported": len(values), "filename": csvfile.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/random-values/{fieldconcept}/sample")
def get_random_values_sample(fieldconcept: str, limit: int = 5):
    conn = getconn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            f"SELECT value FROM {RANDOM_POOL_TABLE} WHERE field_concept=%s ORDER BY RAND() LIMIT %s",
            (fieldconcept, int(limit)),
        )
        return {"fieldconcept": fieldconcept, "values": [r["value"] for r in (cur.fetchall() or [])]}
    finally:
        cur.close()
        conn.close()


@app.get("/api/random-values/{fieldconcept}/count")
def get_pool_count(fieldconcept: str):
    conn = getconn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(f"SELECT COUNT(*) AS count FROM {RANDOM_POOL_TABLE} WHERE field_concept=%s", (fieldconcept,))
        row = cur.fetchone()
        return {"fieldconcept": fieldconcept, "count": int(row["count"] if row else 0)}
    finally:
        cur.close()
        conn.close()


# ---------------- Campaign CRUD + run ----------------
@app.post("/api/campaigns")
def create_campaign(req: CampaignRequest):
    urls = [str(u).strip() for u in (req.websiteIds or []) if str(u).strip()]
    website_ids = ensure_websites_exist(urls)

    conn = getconn()
    cur = conn.cursor()
    try:
        cur.execute(
            f"""
            INSERT INTO {CAMPAIGNS_TABLE}
              (name, description, sender_name, sender_email, subject_line, message_body, max_websites, status)
            VALUES
              (%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                req.name,
                req.description,
                req.senderName,
                req.senderEmail,
                req.subjectLine,
                req.messageBody,
                int(req.maxWebsites or 50),
                "draft",
            ),
        )
        campaign_id = int(cur.lastrowid)

        if urls:
            rows = [(campaign_id, int(wid), url) for wid, url in zip(website_ids, urls)]
            cur.executemany(
                f"INSERT INTO {CAMPAIGN_WEBSITES_TABLE} (campaign_id, website_id, website_url) VALUES (%s,%s,%s)",
                rows,
            )

        if req.fieldStrategies:
            strat_rows = []
            for concept, cfg in (req.fieldStrategies or {}).items():
                strategy = (cfg.get("strategy") or "constant").strip()
                constant_value = cfg.get("value")
                if strategy != "constant":
                    constant_value = None
                strat_rows.append((campaign_id, str(concept), strategy, constant_value))

            cur.executemany(
                f"""
                INSERT INTO {CAMPAIGN_FIELD_STRATEGY_TABLE}
                  (campaign_id, field_concept, strategy, constant_value)
                VALUES (%s,%s,%s,%s)
                """,
                strat_rows,
            )

        conn.commit()
        return {"ok": True, "campaignId": campaign_id}
    finally:
        cur.close()
        conn.close()


@app.get("/api/campaigns")
def list_campaigns():
    conn = getconn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(
            f"""
            SELECT c.id, c.name, c.status, c.created_at, c.updated_at,
              (SELECT COUNT(*) FROM {CAMPAIGN_WEBSITES_TABLE} cw WHERE cw.campaign_id=c.id) AS targets
            FROM {CAMPAIGNS_TABLE} c
            ORDER BY c.id DESC
            """
        )
        items = cur.fetchall() or []
        return {"items": items}
    finally:
        cur.close()
        conn.close()


@app.get("/api/campaigns/{campaign_id}")
def get_campaign(campaign_id: int):
    conn = getconn()
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute(f"SELECT * FROM {CAMPAIGNS_TABLE} WHERE id=%s", (campaign_id,))
        c = cur.fetchone()
        if not c:
            raise HTTPException(status_code=404, detail="Campaign not found")

        cur.execute(
            f"SELECT website_id, website_url FROM {CAMPAIGN_WEBSITES_TABLE} WHERE campaign_id=%s",
            (campaign_id,),
        )
        c["websites"] = cur.fetchall() or []

        cur.execute(
            f"""
            SELECT field_concept, strategy, constant_value
            FROM {CAMPAIGN_FIELD_STRATEGY_TABLE}
            WHERE campaign_id=%s
            """,
            (campaign_id,),
        )
        c["fieldStrategies"] = cur.fetchall() or []

        c["lastRun"] = get_last_run(campaign_id)
        c["targets"] = len(c["websites"])
        return c
    finally:
        cur.close()
        conn.close()


@app.get("/api/campaigns/{campaign_id}/status")
def get_campaign_status(campaign_id: int):
    lr = get_last_run(campaign_id)
    if not lr:
        return {"running": False, "status": "idle", "progress": 0, "total": 0, "results": None}

    return {
        "running": lr["status"] in ("running", "scraping", "clustering", "filling"),
        "status": lr["status"],
        "progress": int(lr.get("progress") or 0),
        "total": int(lr.get("total") or 0),
        "results": lr.get("results"),
        "error": lr.get("error"),
    }


async def run_campaign_pipeline(campaign_id: int, run_id: int):
    """
    Two-phase campaign pipeline:
    
    Phase 1 (Scraping + Mapping): 
        - Navigate to contact pages
        - Discover form fields
        - Normalize field names  
        - Map fields to concepts (email, name, message, etc.)
        - Detect captcha/dead sites
        - No submission - just collects form structure
                        
    Phase 2 (Filling + Submit):  
        - Fill discovered forms with user data
        - Submit forms
        - Collect network responses
    """
    try:
        set_campaign_status(campaign_id, "running")

        # Load campaign + targets
        conn = getconn()
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(f"SELECT * FROM {CAMPAIGNS_TABLE} WHERE id=%s", (campaign_id,))
            camp = cur.fetchone() or {}

            cur.execute(
                f"SELECT website_id, website_url FROM {CAMPAIGN_WEBSITES_TABLE} WHERE campaign_id=%s",
                (campaign_id,),
            )
            targets = cur.fetchall() or []
        finally:
            cur.close()
            conn.close()

        website_ids = [int(t["website_id"]) for t in targets if t.get("website_id") is not None]
        urls = [str(t.get("website_url") or "").strip() for t in targets if str(t.get("website_url") or "").strip()]

        max_websites = int(camp.get("max_websites") or 50)
        planned_urls = urls[:max_websites]
        planned_total = len(planned_urls)

        update_run(run_id, status="running", progress=0, total=planned_total)

        if is_paused(campaign_id):
            update_run(run_id, status="paused", progress=0, total=planned_total)
            return

        # =====================================
        # PHASE 1: SCRAPE (Discover form fields)
        # =====================================
        update_run(run_id, status="scraping", progress=0, total=planned_total)
        
        scrape_results = []
        scraped_count = 0
        agg = {"total": 0, "success": 0, "failed": 0, "captcha": 0, "scraped": 0, "noform": 0}
        
        for idx, url in enumerate(planned_urls):
            if is_paused(campaign_id):
                update_run(run_id, status="paused", progress=scraped_count, total=planned_total)
                return
            
            one_userdata = {"websites": [url]}
            scrape_result = await scrapeallforms(one_userdata, 1)
            
            if isinstance(scrape_result, dict):
                details = scrape_result.get("details") or []
                if details:
                    scrape_results.append(details[0])
                    detail_status = str(details[0].get("status") or "").lower()
                    if detail_status == "captcha":
                        agg["captcha"] += 1
                    elif detail_status == "noform":
                        agg["noform"] += 1
                    elif detail_status == "scraped":
                        agg["scraped"] += 1
            
            scraped_count += 1
            agg["total"] = scraped_count
            update_run(run_id, status="scraping", progress=scraped_count, total=planned_total, results=db_json(agg))

        if is_paused(campaign_id):
            update_run(run_id, status="paused", progress=scraped_count, total=planned_total)
            return

        # ---- CLUSTER (optional) ----
        if cluster_websites is not None and website_ids:
            update_run(run_id, status="clustering", progress=0, total=planned_total)

            def on_cluster_progress(done, total, wid):
                update_run(run_id, status="clustering", progress=min(done, planned_total), total=planned_total)

            try:
                cluster_websites(website_ids, on_progress=on_cluster_progress)
            except TypeError:
                cluster_websites(website_ids)

        if is_paused(campaign_id):
            update_run(run_id, status="paused", progress=0, total=planned_total)
            return

        # ---- Build userdata ----
        base_userdata: Dict[str, Any] = {}
        if camp.get("sender_name"):
            base_userdata["fullname"] = camp["sender_name"]
            base_userdata["name"] = camp["sender_name"]
        if camp.get("sender_email"):
            base_userdata["email"] = camp["sender_email"]
        if camp.get("subject_line"):
            base_userdata["subject"] = camp["subject_line"]
        if camp.get("message_body"):
            base_userdata["message"] = camp["message_body"]

        # =====================================
        # PHASE 2: FILL + SUBMIT
        # =====================================
        update_run(run_id, status="filling", progress=0, total=planned_total)

        done = 0

        # Use scraped results to know which URLs have forms
        urls_with_forms = []
        for sr in scrape_results:
            status = str(sr.get("status") or "").lower()
            if status == "scraped":
                url = sr.get("url") or sr.get("contact_url") or ""
                if url:
                    urls_with_forms.append({
                        "url": url,
                        "mapping": sr.get("mapping") or {},
                        "website_id": sr.get("website_id"),
                    })
            elif status == "noform":
                agg["noform"] += 1
            elif status == "captcha":
                agg["captcha"] += 1

        # Phase 2: Fill and submit only URLs with discovered forms
        for site_info in urls_with_forms:
            if is_paused(campaign_id):
                update_run(run_id, status="paused", progress=done, total=planned_total)
                return

            url = site_info["url"]
            one_userdata = dict(base_userdata)
            one_userdata["websites"] = [url]

            results_one = await fillallforms(one_userdata, 1, mode="fill")

            if isinstance(results_one, dict):
                agg["total"] += int(results_one.get("total") or 0)
                agg["success"] += int(results_one.get("success") or 0)
                agg["failed"] += int(results_one.get("failed") or 0)
                agg["captcha"] += int(results_one.get("captcha") or 0)

            done += 1
            update_run(run_id, status="filling", progress=done, total=len(urls_with_forms), results=db_json(agg))

        # Add the count of sites that were scraped but didn't have forms
        agg["scraped"] = len(scrape_results)
        agg["total"] = len(scrape_results)

        update_run(
            run_id,
            status="completed",
            progress=planned_total,
            total=planned_total,
            results=db_json(agg),
            finished_at=datetime.now(),
        )
        set_campaign_status(campaign_id, "completed")

    except Exception as e:
        traceback.print_exc()
        update_run(
            run_id,
            status="error",
            error=str(e),
            results=db_json({"total": 0, "success": 0, "failed": 0, "captcha": 0, "error": str(e)}),
            finished_at=datetime.now(),
        )
        set_campaign_status(campaign_id, "error")


# Store background tasks to prevent garbage collection
background_tasks = set()


async def run_campaign_pipeline(campaign_id: int, run_id: int):
    """Two-phase campaign pipeline"""
    try:
        set_campaign_status(campaign_id, "running")
        conn = getconn()
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(f"SELECT * FROM {CAMPAIGNS_TABLE} WHERE id=%s", (campaign_id,))
            camp = cur.fetchone() or {}
            cur.execute(f"SELECT website_id, website_url FROM {CAMPAIGN_WEBSITES_TABLE} WHERE campaign_id=%s", (campaign_id,))
            targets = cur.fetchall() or []
        finally:
            cur.close()
            conn.close()

        urls = [str(t.get("website_url") or "").strip() for t in targets if str(t.get("website_url") or "").strip()]
        max_websites = int(camp.get("max_websites") or 50)
        planned_urls = urls[:max_websites]
        planned_total = len(planned_urls)

        update_run(run_id, status="scraping", progress=0, total=planned_total)
        scrape_results = []
        scraped_count = 0
        agg = {"total": 0, "success": 0, "failed": 0, "captcha": 0, "scraped": 0, "noform": 0}
        
        for url in planned_urls:
            if is_paused(campaign_id):
                update_run(run_id, status="paused", progress=scraped_count, total=planned_total)
                return
            one_userdata = {"websites": [url]}
            scrape_result = await scrapeallforms(one_userdata, 1)
            if isinstance(scrape_result, dict):
                details = scrape_result.get("details") or []
                if details:
                    scrape_results.append(details[0])
                    detail_status = str(details[0].get("status") or "").lower()
                    if detail_status == "captcha":
                        agg["captcha"] += 1
                    elif detail_status == "noform":
                        agg["noform"] += 1
                    elif detail_status == "scraped":
                        agg["scraped"] += 1
            scraped_count += 1
            agg["total"] = scraped_count
            update_run(run_id, status="scraping", progress=scraped_count, total=planned_total, results=db_json(agg))

        base_userdata = {}
        if camp.get("sender_name"):
            base_userdata["name"] = camp["sender_name"]
        if camp.get("sender_email"):
            base_userdata["email"] = camp["sender_email"]
        if camp.get("subject_line"):
            base_userdata["subject"] = camp["subject_line"]
        if camp.get("message_body"):
            base_userdata["message"] = camp["message_body"]

        update_run(run_id, status="filling", progress=0, total=planned_total)
        done = 0
        urls_with_forms = []
        for sr in scrape_results:
            status = str(sr.get("status") or "").lower()
            if status == "scraped":
                url = sr.get("url") or sr.get("contact_url") or ""
                if url:
                    urls_with_forms.append({"url": url})

        for site_info in urls_with_forms:
            if is_paused(campaign_id):
                update_run(run_id, status="paused", progress=done, total=planned_total)
                return
            url = site_info["url"]
            one_userdata = dict(base_userdata)
            one_userdata["websites"] = [url]
            results_one = await fillallforms(one_userdata, 1, mode="fill")
            if isinstance(results_one, dict):
                agg["total"] += int(results_one.get("total") or 0)
                agg["success"] += int(results_one.get("success") or 0)
                agg["failed"] += int(results_one.get("failed") or 0)
                agg["captcha"] += int(results_one.get("captcha") or 0)
            done += 1
            update_run(run_id, status="filling", progress=done, total=len(urls_with_forms), results=db_json(agg))

        agg["scraped"] = len(scrape_results)
        agg["total"] = len(scrape_results)
        update_run(run_id, status="completed", progress=planned_total, total=planned_total, results=db_json(agg), finished_at=datetime.now())
        set_campaign_status(campaign_id, "completed")
    except Exception as e:
        traceback.print_exc()
        update_run(run_id, status="error", error=str(e), results=db_json({"total": 0, "success": 0, "failed": 0, "captcha": 0, "error": str(e)}), finished_at=datetime.now())
        set_campaign_status(campaign_id, "error")


async def _run_campaign_with_error_handling(campaign_id: int, run_id: int):
    """Wrapper to catch and log exceptions from campaign pipeline."""
    try:
        await run_campaign_pipeline(campaign_id, run_id)
    except Exception as e:
        print(f"[ERROR] Campaign {campaign_id} run {run_id} failed: {e}")
        traceback.print_exc()
        try:
            update_run(
                run_id,
                status="error",
                error=str(e),
                results=db_json({"total": 0, "success": 0, "failed": 0, "captcha": 0, "error": str(e)}),
                finished_at=datetime.now(),
            )
            set_campaign_status(campaign_id, "error")
        except Exception as e2:
            print(f"[ERROR] Failed to update run status: {e2}")


@app.post("/api/campaigns/{campaign_id}/start")
async def start_campaign(campaign_id: int):
    run_id = create_run(campaign_id)
    
    # Create task and store reference to prevent garbage collection
    task = asyncio.create_task(_run_campaign_with_error_handling(campaign_id, run_id))
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    
    return {"ok": True, "campaignId": campaign_id, "runId": run_id}


@app.post("/api/campaigns/{campaign_id}/restart")
async def restart_campaign(campaign_id: int):
    return await start_campaign(campaign_id)


@app.post("/api/campaigns/{campaign_id}/pause")
def pause_campaign(campaign_id: int):
    set_campaign_status(campaign_id, "paused")
    return {"ok": True, "campaignId": campaign_id, "status": "paused"}


# ---------------- Backward compatible "fill-all-forms" ----------------
import uuid

# Use job IDs instead of global state to prevent race conditions
job_statuses = {}  # job_id -> status dict


@app.post("/api/fill-all-forms")
async def fill_all_forms_endpoint(request: FillFormsRequest):
    job_id = str(uuid.uuid4())
    
    userdata = request.userdata or request.userData or {}
    maxwebsites = request.maxwebsites or request.maxWebsites or 50
    
    job_statuses[job_id] = {"running": True, "progress": 0, "total": 0, "results": None}
    
    async def runjob():
        try:
            results = await fillallforms(userdata, int(maxwebsites))
            if not isinstance(results, dict):
                results = {"total": 0, "success": 0, "failed": 0, "captcha": 0}
            job_statuses[job_id]["results"] = results
            job_statuses[job_id]["total"] = int(results.get("total") or 0)
            job_statuses[job_id]["progress"] = int(results.get("total") or 0)
        except Exception as e:
            traceback.print_exc()
            job_statuses[job_id]["results"] = {"total": 0, "success": 0, "failed": 0, "captcha": 0, "error": str(e)}
        finally:
            job_statuses[job_id]["running"] = False
    
    # Use asyncio.create_task for async functions (not BackgroundTasks)
    task = asyncio.create_task(runjob())
    background_tasks.add(task)
    task.add_done_callback(background_tasks.discard)
    
    return {"ok": True, "message": "Form filling started", "jobId": job_id}


@app.get("/api/fill-status/{job_id}")
def get_fill_status(job_id: str):
    if job_id not in job_statuses:
        raise HTTPException(status_code=404, detail="Job not found")
    return job_statuses[job_id]


# Backward compatibility: return latest job status
@app.get("/api/fill-status")
def get_fill_status_legacy():
    if not job_statuses:
        return {"running": False, "progress": 0, "total": 0, "results": None}
    # Return the most recent job
    latest_job_id = list(job_statuses.keys())[-1]
    return job_statuses[latest_job_id]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
