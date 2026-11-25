"""Website management, scanning, and field inspection routes."""

import csv
import io
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.automation.playwright_manager import managed_browser_context
from app.core.security import extract_domain, validate_target_url
from app.database.connection import db_session
from app.schemas.websites import (
    WebsiteBulkImportRequest,
    WebsiteCreateRequest,
    WebsiteFieldUpdateRequest,
)
from app.services.website_scan_service import (
    get_batch_scan_status,
    start_batch_scan,
    stop_batch_scan,
)
from form_filler import MySQLDB, RandomValuePool, process_website

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["websites"])


@router.get("/websites")
def get_websites_summary():
    """Aggregate website counts for dashboard cards."""
    with db_session(dictionary=True) as (_, cur):
        cur.execute(
            """
            SELECT
              COUNT(*) AS total,
              SUM(CASE WHEN timestamp IS NOT NULL THEN 1 ELSE 0 END) AS visited,
              SUM(CASE WHEN timestamp IS NOT NULL AND form_found = 1 THEN 1 ELSE 0 END) AS formstotal,
              SUM(CASE WHEN timestamp IS NOT NULL AND has_captcha = 1 THEN 1 ELSE 0 END) AS captchatotal,
              SUM(CASE WHEN timestamp IS NOT NULL AND form_found = 0 AND has_captcha = 0 THEN 1 ELSE 0 END) AS deadsites
            FROM websites
            """
        )
        row = cur.fetchone() or {}

        cur.execute(
            """
            SELECT COUNT(*) AS zerofieldsites FROM (
              SELECT w.id
              FROM websites w
              LEFT JOIN raw_fields f ON f.website_id = w.id
              WHERE w.timestamp IS NOT NULL
              GROUP BY w.id
              HAVING COUNT(f.website_id) = 0
            ) AS t
            """
        )
        zf = int((cur.fetchone() or {}).get("zerofieldsites") or 0)

    total = int(row.get("total") or 0)
    visited = int(row.get("visited") or 0)
    formstotal = int(row.get("formstotal") or 0)
    captchatotal = int(row.get("captchatotal") or 0)
    deadsites = int(row.get("deadsites") or 0)

    return {
        "total": total,
        "visited": visited,
        "formstotal": formstotal,
        "captchatotal": captchatotal,
        "deadsites": deadsites,
        "zerofieldsites": zf,
        "formsTotal": formstotal,
        "captchaTotal": captchatotal,
        "deadSites": deadsites,
        "zeroFieldSites": zf,
    }


@router.get("/websites/list")
def list_websites(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=200),
    search: Optional[str] = None,
    scan_status: Optional[str] = None,  # scanned, unscanned
    form_found: Optional[str] = None,   # yes, no
    has_captcha: Optional[str] = None,  # yes, no
):
    """Paginated, filterable website list with field counts."""
    where_clauses: List[str] = []
    params: List[Any] = []

    if search and search.strip():
        where_clauses.append("w.url LIKE %s")
        params.append(f"%{search.strip()}%")

    if scan_status == "scanned":
        where_clauses.append("w.timestamp IS NOT NULL")
    elif scan_status == "unscanned":
        where_clauses.append("w.timestamp IS NULL")

    if form_found == "yes":
        where_clauses.append("w.form_found = 1")
    elif form_found == "no":
        where_clauses.append("w.form_found = 0")

    if has_captcha == "yes":
        where_clauses.append("w.has_captcha = 1")
    elif has_captcha == "no":
        where_clauses.append("w.has_captcha = 0")

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    with db_session(dictionary=True) as (_, cur):
        cur.execute(f"SELECT COUNT(*) AS total FROM websites w {where_sql}", tuple(params))
        total = int((cur.fetchone() or {}).get("total") or 0)

        cur.execute(
            f"""
            SELECT
                w.id,
                w.url,
                w.timestamp,
                w.form_found,
                w.has_captcha,
                w.is_dead,
                w.fields_count
            FROM websites w
            {where_sql}
            ORDER BY w.id DESC
            LIMIT %s OFFSET %s
            """,
            tuple(params + [limit, skip]),
        )
        rows = cur.fetchall() or []

    items = []
    for r in rows:
        items.append(
            {
                "id": int(r["id"]),
                "url": r["url"],
                "domain": extract_domain(r["url"]),
                "scan_status": "scanned" if r["timestamp"] is not None else "pending",
                "form_found": bool(r["form_found"]),
                "has_captcha": bool(r["has_captcha"]),
                "is_dead": bool(r["is_dead"]),
                "fields_count": int(r["fields_count"] or 0),
                "last_scanned": str(r["timestamp"]) if r["timestamp"] else None,
            }
        )

    return {"total": total, "skip": skip, "limit": limit, "items": items}


@router.post("/websites")
def create_website(req: WebsiteCreateRequest):
    ok, normalized_url, err = validate_target_url(req.url)
    if not ok:
        raise HTTPException(status_code=400, detail=err)

    with db_session(dictionary=True) as (_, cur):
        cur.execute("SELECT id, url FROM websites WHERE url=%s LIMIT 1", (normalized_url,))
        existing = cur.fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Website already exists")

        cur.execute(
            "INSERT INTO websites (url, form_found, has_captcha, is_dead, timestamp) VALUES (%s, 0, 0, 0, NULL)",
            (normalized_url,),
        )
        wid = int(cur.lastrowid)

    return {"ok": True, "id": wid, "url": normalized_url, "domain": extract_domain(normalized_url)}


@router.post("/websites/bulk")
def bulk_import_websites(req: WebsiteBulkImportRequest):
    added = 0
    duplicates = 0
    invalid: List[Dict[str, str]] = []

    with db_session(dictionary=True) as (_, cur):
        for raw in req.urls:
            ok, normalized, err = validate_target_url(raw)
            if not ok:
                invalid.append({"url": str(raw), "error": err})
                continue

            cur.execute("SELECT id FROM websites WHERE url=%s LIMIT 1", (normalized,))
            if cur.fetchone():
                duplicates += 1
                continue

            cur.execute(
                "INSERT INTO websites (url, form_found, has_captcha, is_dead, timestamp) VALUES (%s, 0, 0, 0, NULL)",
                (normalized,),
            )
            added += 1

    return {"ok": True, "added": added, "duplicates": duplicates, "invalid": invalid}


@router.post("/websites/import-csv")
async def import_websites_csv(file: UploadFile = File(...)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a valid .csv file")

    raw_bytes = await file.read()
    if len(raw_bytes) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="CSV file exceeds 5 MB limit")

    text = raw_bytes.decode("utf-8", errors="ignore")
    reader = csv.reader(io.StringIO(text))
    urls: List[str] = []
    for idx, row in enumerate(reader):
        if not row:
            continue
        cell = (row[0] or "").strip()
        if idx == 0 and cell.lower() in {"url", "website", "websites", "website_url"}:
            continue
        if cell:
            urls.append(cell)

    return bulk_import_websites(WebsiteBulkImportRequest(urls=urls))


@router.get("/websites/export-csv")
def export_websites_csv():
    with db_session(dictionary=True) as (_, cur):
        cur.execute(
            """
            SELECT w.id, w.url, w.form_found, w.has_captcha, w.is_dead, w.timestamp, COUNT(rf.id) AS fields_count
            FROM websites w
            LEFT JOIN raw_fields rf ON rf.website_id = w.id
            GROUP BY w.id
            ORDER BY w.id DESC
            """
        )
        rows = cur.fetchall() or []

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "url", "domain", "form_found", "has_captcha", "is_dead", "fields_count", "last_scanned"])
    for r in rows:
        writer.writerow([
            r["id"],
            r["url"],
            extract_domain(r["url"]),
            bool(r["form_found"]),
            bool(r["has_captcha"]),
            bool(r["is_dead"]),
            r["fields_count"],
            str(r["timestamp"]) if r["timestamp"] else "",
        ])

    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=websites_export.csv"},
    )


@router.post("/websites/batch-scan")
async def trigger_batch_scan(
    mode: str = Query(default="pending", pattern="^(pending|pending_and_noform|all)$"),
    limit: Optional[int] = Query(default=None, ge=1, le=50000),
    concurrency: int = Query(default=3, ge=1, le=10),
):
    try:
        return start_batch_scan(mode=mode, limit=limit, concurrency=concurrency)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/websites/batch-scan/status")
def batch_scan_status():
    return get_batch_scan_status()


@router.post("/websites/batch-scan/stop")
def batch_scan_stop():
    return stop_batch_scan()


@router.get("/websites/{website_id}")
def get_website_details(website_id: int):
    with db_session(dictionary=True) as (_, cur):
        cur.execute("SELECT * FROM websites WHERE id=%s", (website_id,))
        site = cur.fetchone()
        if not site:
            raise HTTPException(status_code=404, detail="Website not found")

        cur.execute(
            """
            SELECT id, tag_name, field_id, field_name, field_type, placeholder, cluster_key, cluster_score, clustered_at
            FROM raw_fields
            WHERE website_id=%s
            ORDER BY id ASC
            """,
            (website_id,),
        )
        fields = cur.fetchall() or []

        cur.execute(
            """
            SELECT fs.id, fs.url, fs.status, fs.filled_fields, fs.error, fs.created_at, fs.campaignid,
                   fsd.status_code, fsd.request_url
            FROM form_submissions fs
            LEFT JOIN form_submissions_details fsd ON fsd.submission_id = fs.id
            WHERE fs.website_id=%s
            ORDER BY fs.id DESC
            LIMIT 50
            """,
            (website_id,),
        )
        submissions = cur.fetchall() or []

    for f in fields:
        if f.get("cluster_score") is not None:
            f["cluster_score"] = float(f["cluster_score"])
        if f.get("clustered_at"):
            f["clustered_at"] = str(f["clustered_at"])
    for s in submissions:
        if s.get("created_at"):
            s["created_at"] = str(s["created_at"])

    return {
        "id": int(site["id"]),
        "url": site["url"],
        "domain": extract_domain(site["url"]),
        "scan_status": "scanned" if site["timestamp"] is not None else "pending",
        "form_found": bool(site["form_found"]),
        "has_captcha": bool(site["has_captcha"]),
        "is_dead": bool(site["is_dead"]),
        "last_scanned": str(site["timestamp"]) if site["timestamp"] else None,
        "fields": fields,
        "submissions": submissions,
    }


@router.post("/websites/{website_id}/scan")
async def scan_single_website(website_id: int):
    with db_session(dictionary=True) as (_, cur):
        cur.execute("SELECT id, url FROM websites WHERE id=%s", (website_id,))
        site = cur.fetchone()
        if not site:
            raise HTTPException(status_code=404, detail="Website not found")

    ok, normalized_url, err = validate_target_url(site["url"])
    if not ok:
        raise HTTPException(status_code=400, detail=f"Unsafe or invalid URL: {err}")

    db = MySQLDB()
    pool = RandomValuePool()
    try:
        async with managed_browser_context(block_assets=True) as context:
            result = await process_website(
                db=db,
                pool=pool,
                context=context,
                website_id=int(site["id"]),
                url=normalized_url,
                mode="scrape",
            )
    finally:
        pool.close()
        db.close()

    return {"ok": True, "result": result}


@router.patch("/websites/{website_id}/fields/{field_id}")
def update_website_field_mapping(website_id: int, field_id: int, req: WebsiteFieldUpdateRequest):
    with db_session() as (_, cur):
        cur.execute(
            "UPDATE raw_fields SET cluster_key=%s, clustered_at=NOW() WHERE id=%s AND website_id=%s",
            (req.cluster_key.strip(), field_id, website_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Field not found for this website")
    return {"ok": True}


@router.delete("/websites/{website_id}")
def delete_website(website_id: int):
    with db_session() as (_, cur):
        cur.execute("DELETE FROM raw_fields WHERE website_id=%s", (website_id,))
        cur.execute("DELETE FROM campaign_websites WHERE website_id=%s", (website_id,))
        cur.execute("DELETE FROM websites WHERE id=%s", (website_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Website not found")
    return {"ok": True}


@router.get("/websites-with-fields")
def get_websites_with_fields(skip: int = 0, limit: int = 10):
    """Optimized query without N+1 problem."""
    with db_session(dictionary=True) as (_, cur):
        cur.execute(
            """
            SELECT w.id, w.url, COUNT(*) AS fieldcount
            FROM websites w
            JOIN raw_fields f ON w.id = f.website_id
            GROUP BY w.id
            ORDER BY w.id DESC
            LIMIT %s OFFSET %s
            """,
            (limit, skip),
        )
        websites = cur.fetchall() or []
        if not websites:
            return {"items": []}

        ids = [int(w["id"]) for w in websites]
        fmt = ",".join(["%s"] * len(ids))
        cur.execute(
            f"""
            SELECT
                website_id,
                field_name AS fieldname,
                field_type AS fieldtype,
                placeholder,
                cluster_key AS clusterkey
            FROM raw_fields
            WHERE website_id IN ({fmt})
            ORDER BY field_name
            """,
            tuple(ids),
        )
        all_fields = cur.fetchall() or []

    by_wid: Dict[int, List[Dict[str, Any]]] = {}
    for f in all_fields:
        wid = int(f.pop("website_id"))
        by_wid.setdefault(wid, []).append(f)

    items = [
        {
            "id": int(w["id"]),
            "url": w["url"],
            "fieldcount": int(w["fieldcount"]),
            "fields": by_wid.get(int(w["id"]), []),
        }
        for w in websites
    ]
    return {"items": items}


@router.get("/dead-sites")
def get_dead_sites(skip: int = 0, limit: int = 10):
    with db_session(dictionary=True) as (_, cur):
        cur.execute(
            "SELECT COUNT(*) AS totaldead FROM websites WHERE timestamp IS NOT NULL AND form_found = 0 AND has_captcha = 0"
        )
        totaldead = int((cur.fetchone() or {}).get("totaldead") or 0)
        cur.execute(
            """
            SELECT id, url
            FROM websites
            WHERE timestamp IS NOT NULL AND form_found = 0 AND has_captcha = 0
            ORDER BY id DESC
            LIMIT %s OFFSET %s
            """,
            (limit, skip),
        )
        return {"total": totaldead, "items": cur.fetchall() or []}


@router.get("/zero-field-sites")
def get_zero_field_sites(skip: int = 0, limit: int = 10):
    with db_session(dictionary=True) as (_, cur):
        cur.execute(
            """
            SELECT COUNT(*) AS totalzero FROM (
              SELECT w.id
              FROM websites w
              LEFT JOIN raw_fields f ON f.website_id = w.id
              WHERE w.timestamp IS NOT NULL
              GROUP BY w.id
              HAVING COUNT(f.website_id) = 0
            ) AS t
            """
        )
        totalzero = int((cur.fetchone() or {}).get("totalzero") or 0)
        cur.execute(
            """
            SELECT w.id, w.url
            FROM websites w
            LEFT JOIN raw_fields f ON f.website_id = w.id
            WHERE w.timestamp IS NOT NULL
            GROUP BY w.id
            HAVING COUNT(f.website_id) = 0
            ORDER BY w.id DESC
            LIMIT %s OFFSET %s
            """,
            (limit, skip),
        )
        return {"total": totalzero, "items": cur.fetchall() or []}
