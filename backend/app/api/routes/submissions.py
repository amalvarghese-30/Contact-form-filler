"""Form submissions audit and CSV export routes."""

import csv
import io
from typing import Any, List, Optional

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.database.connection import db_session

router = APIRouter(prefix="/api", tags=["submissions"])


@router.get("/form-submissions")
def get_form_submissions(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    status: Optional[str] = None,
    campaign_id: Optional[int] = None,
    search: Optional[str] = None,
):
    """Get paginated, filterable form submissions with their HTTP request/response details."""
    where_clauses: List[str] = []
    params: List[Any] = []

    if status and status.strip() and status != "all":
        if status == "pending":
            where_clauses.append("fs.status IN ('unconfirmed', 'pending', 'sent_unverified')")
        else:
            where_clauses.append("fs.status = %s")
            params.append(status.strip())

    if campaign_id is not None:
        where_clauses.append("fs.campaignid = %s")
        params.append(int(campaign_id))

    if search and search.strip():
        where_clauses.append("(fs.url LIKE %s OR fs.error LIKE %s)")
        q = f"%{search.strip()}%"
        params.extend([q, q])

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    with db_session(dictionary=True) as (_, cur):
        cur.execute(f"SELECT COUNT(*) AS total FROM form_submissions fs {where_sql}", tuple(params))
        total = int((cur.fetchone() or {}).get("total") or 0)

        cur.execute(
            f"""
            SELECT
                fs.id,
                fs.website_id,
                fs.url,
                fs.normalized_url,
                fs.status,
                fs.filled_fields,
                fs.error,
                fs.created_at,
                fs.campaignid,
                c.name AS campaign_name,
                fsd.request_url,
                fsd.payload_json,
                fsd.response_json,
                fsd.status_code
            FROM form_submissions fs
            LEFT JOIN campaigns c ON c.id = fs.campaignid
            LEFT JOIN form_submissions_details fsd ON fsd.submission_id = fs.id
            {where_sql}
            ORDER BY fs.id DESC
            LIMIT %s OFFSET %s
            """,
            tuple(params + [limit, skip]),
        )
        submissions = cur.fetchall() or []

    items = []
    for sub in submissions:
        item: Dict[str, Any] = {
            "id": sub["id"],
            "website_id": sub["website_id"],
            "url": sub["url"],
            "status": sub["status"],
            "filled_fields": sub["filled_fields"],
            "error": sub["error"],
            "campaign_id": sub.get("campaignid"),
            "campaign_name": sub.get("campaign_name"),
            "created_at": str(sub["created_at"]) if sub.get("created_at") else None,
        }
        if sub.get("request_url") or sub.get("status_code"):
            item["details"] = {
                "request_url": sub.get("request_url"),
                "status_code": sub.get("status_code"),
                "payload_json": sub.get("payload_json"),
                "response_json": sub.get("response_json"),
            }
        items.append(item)

    return {"total": total, "skip": skip, "limit": limit, "items": items}


@router.get("/form-submissions/export-csv")
def export_submissions_csv(status: Optional[str] = None, campaign_id: Optional[int] = None):
    where_clauses: List[str] = []
    params: List[Any] = []
    if status and status != "all":
        where_clauses.append("fs.status = %s")
        params.append(status)
    if campaign_id is not None:
        where_clauses.append("fs.campaignid = %s")
        params.append(int(campaign_id))
    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

    with db_session(dictionary=True) as (_, cur):
        cur.execute(
            f"""
            SELECT fs.id, fs.url, fs.status, fs.filled_fields, fs.error, fs.campaignid, fs.created_at, fsd.status_code
            FROM form_submissions fs
            LEFT JOIN form_submissions_details fsd ON fsd.submission_id = fs.id
            {where_sql}
            ORDER BY fs.id DESC
            LIMIT 5000
            """,
            tuple(params),
        )
        rows = cur.fetchall() or []

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["id", "url", "status", "filled_fields", "status_code", "campaign_id", "error", "created_at"])
    for r in rows:
        writer.writerow([
            r["id"],
            r["url"],
            r["status"],
            r["filled_fields"],
            r.get("status_code") or "",
            r.get("campaignid") or "",
            (r.get("error") or "")[:300],
            str(r["created_at"]) if r.get("created_at") else "",
        ])
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=submissions_export.csv"},
    )
