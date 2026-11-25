"""Analytics and dashboard overview endpoints computed strictly from database records."""

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

from app.database.connection import db_session

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/overview")
def get_analytics_overview(
    days: int = Query(default=30, ge=1, le=365),
    campaign_id: Optional[int] = None,
):
    """Return real-time dashboard & analytics metrics from MySQL tables."""
    sub_where = ["created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)"]
    sub_params: List[Any] = [days]
    if campaign_id is not None:
        sub_where.append("campaignid = %s")
        sub_params.append(int(campaign_id))
    sub_where_sql = "WHERE " + " AND ".join(sub_where)

    with db_session(dictionary=True) as (_, cur):
        # 1. Website summary
        cur.execute(
            """
            SELECT
              COUNT(*) AS total,
              SUM(CASE WHEN timestamp IS NOT NULL THEN 1 ELSE 0 END) AS scanned,
              SUM(CASE WHEN timestamp IS NOT NULL AND form_found = 1 THEN 1 ELSE 0 END) AS with_forms,
              SUM(CASE WHEN timestamp IS NOT NULL AND form_found = 0 AND has_captcha = 0 THEN 1 ELSE 0 END) AS without_forms,
              SUM(CASE WHEN timestamp IS NOT NULL AND has_captcha = 1 THEN 1 ELSE 0 END) AS captcha
            FROM websites
            """
        )
        w_row = cur.fetchone() or {}

        # 2. Campaign summary
        cur.execute(
            """
            SELECT
              COUNT(*) AS total,
              SUM(CASE WHEN status IN ('queued','running','scraping','clustering','filling') THEN 1 ELSE 0 END) AS active,
              SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS completed
            FROM campaigns
            """
        )
        c_row = cur.fetchone() or {}

        # 3. Submission totals (all-time & filtered)
        cur.execute(
            f"""
            SELECT
              COUNT(*) AS total,
              SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success,
              SUM(CASE WHEN status IN ('failed','timeout','nofill') THEN 1 ELSE 0 END) AS failed,
              SUM(CASE WHEN status = 'captcha' THEN 1 ELSE 0 END) AS captcha,
              SUM(CASE WHEN status IN ('unconfirmed','pending','sent_unverified') THEN 1 ELSE 0 END) AS pending
            FROM form_submissions
            {sub_where_sql}
            """,
            tuple(sub_params),
        )
        s_row = cur.fetchone() or {}

        # 4. Daily submission activity
        cur.execute(
            f"""
            SELECT
              DATE(created_at) AS day,
              COUNT(*) AS total,
              SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS success,
              SUM(CASE WHEN status IN ('failed','timeout','nofill') THEN 1 ELSE 0 END) AS failed,
              SUM(CASE WHEN status = 'captcha' THEN 1 ELSE 0 END) AS captcha
            FROM form_submissions
            {sub_where_sql}
            GROUP BY DATE(created_at)
            ORDER BY day ASC
            """,
            tuple(sub_params),
        )
        daily_activity = [
            {
                "date": str(r["day"]),
                "total": int(r["total"] or 0),
                "success": int(r["success"] or 0),
                "failed": int(r["failed"] or 0),
                "captcha": int(r["captcha"] or 0),
            }
            for r in (cur.fetchall() or [])
        ]

        # 5. Campaign comparison (latest 10)
        cur.execute(
            """
            SELECT
              c.id,
              c.name,
              c.status,
              c.created_at,
              (SELECT COUNT(*) FROM campaign_websites cw WHERE cw.campaign_id = c.id) AS targets,
              c.results_success AS success,
              c.results_failed AS failed,
              c.results_captcha AS captcha
            FROM campaigns c
            ORDER BY c.id DESC
            LIMIT 10
            """
        )
        campaign_perf = [
            {
                "id": int(r["id"]),
                "name": r["name"],
                "status": r["status"],
                "targets": int(r["targets"] or 0),
                "success": int(r["success"] or 0),
                "failed": int(r["failed"] or 0),
                "captcha": int(r["captcha"] or 0),
                "created_at": str(r["created_at"]) if r.get("created_at") else None,
            }
            for r in (cur.fetchall() or [])
        ]

        # 6. Common detected field concepts
        cur.execute(
            """
            SELECT COALESCE(cluster_key, 'unknown') AS concept, COUNT(*) AS count
            FROM raw_fields
            GROUP BY COALESCE(cluster_key, 'unknown')
            ORDER BY count DESC
            LIMIT 12
            """
        )
        field_concepts = [
            {"concept": r["concept"], "count": int(r["count"] or 0)}
            for r in (cur.fetchall() or [])
        ]

        # 7. Error distribution
        cur.execute(
            f"""
            SELECT status, COUNT(*) AS count
            FROM form_submissions
            {sub_where_sql}
            GROUP BY status
            ORDER BY count DESC
            """,
            tuple(sub_params),
        )
        status_distribution = [
            {"status": r["status"] or "unknown", "count": int(r["count"] or 0)}
            for r in (cur.fetchall() or [])
        ]

        # 8. Recent errors
        cur.execute(
            """
            SELECT id, url, status, error, created_at
            FROM form_submissions
            WHERE status IN ('failed','timeout','nofill','captcha') AND error IS NOT NULL AND error <> ''
            ORDER BY id DESC
            LIMIT 8
            """
        )
        recent_errors = [
            {
                "id": int(r["id"]),
                "url": r["url"],
                "status": r["status"],
                "error": r["error"],
                "created_at": str(r["created_at"]) if r.get("created_at") else None,
            }
            for r in (cur.fetchall() or [])
        ]

    total_w = int(w_row.get("total") or 0)
    scanned_w = int(w_row.get("scanned") or 0)
    with_forms = int(w_row.get("with_forms") or 0)
    sub_total = int(s_row.get("total") or 0)
    sub_success = int(s_row.get("success") or 0)
    sub_failed = int(s_row.get("failed") or 0)
    sub_captcha = int(s_row.get("captcha") or 0)

    return {
        "websites": {
            "total": total_w,
            "scanned": scanned_w,
            "with_forms": with_forms,
            "without_forms": int(w_row.get("without_forms") or 0),
            "captcha": int(w_row.get("captcha") or 0),
        },
        "campaigns": {
            "total": int(c_row.get("total") or 0),
            "active": int(c_row.get("active") or 0),
            "completed": int(c_row.get("completed") or 0),
        },
        "submissions": {
            "total": sub_total,
            "success": sub_success,
            "failed": sub_failed,
            "captcha": sub_captcha,
            "pending": int(s_row.get("pending") or 0),
        },
        "rates": {
            "form_discovery_rate": round((with_forms / scanned_w) * 100, 1) if scanned_w else 0.0,
            "submission_success_rate": round((sub_success / sub_total) * 100, 1) if sub_total else 0.0,
            "failure_rate": round((sub_failed / sub_total) * 100, 1) if sub_total else 0.0,
            "captcha_rate": round((sub_captcha / sub_total) * 100, 1) if sub_total else 0.0,
        },
        "daily_activity": daily_activity,
        "campaign_performance": campaign_perf,
        "field_concepts": field_concepts,
        "status_distribution": status_distribution,
        "recent_errors": recent_errors,
    }
