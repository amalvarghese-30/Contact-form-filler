"""Campaign CRUD, execution controls, and legacy fill-all-forms endpoints."""

import asyncio
import json
import logging
import traceback
import uuid
from typing import Any, Dict, List, Optional, Set

from fastapi import APIRouter, HTTPException, Query

from app.core.security import validate_target_url
from app.database.connection import db_session
from app.schemas.campaigns import (
    CampaignCreateRequest,
    CampaignUpdateRequest,
    FillFormsRequest,
)
from app.services.campaign_service import (
    cancel_campaign_run,
    is_campaign_active,
    pause_campaign_run,
    start_campaign_run,
)
from form_filler import fillallforms

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["campaigns"])

_job_statuses: Dict[str, Dict[str, Any]] = {}
_legacy_tasks: Set[asyncio.Task] = set()


def _ensure_websites_exist(urls: List[str]) -> List[tuple[int, str]]:
    """Validate URLs, ensure they exist in websites table, and return (id, normalized_url) pairs."""
    pairs: List[tuple[int, str]] = []
    if not urls:
        return pairs

    with db_session(dictionary=True) as (_, cur):
        for raw in urls:
            ok, normalized, err = validate_target_url(str(raw))
            if not ok:
                raise HTTPException(status_code=400, detail=f"Invalid URL '{raw}': {err}")
            cur.execute("SELECT id FROM websites WHERE url=%s LIMIT 1", (normalized,))
            row = cur.fetchone()
            if row:
                pairs.append((int(row["id"]), normalized))
            else:
                cur.execute(
                    "INSERT INTO websites (url, form_found, has_captcha, is_dead, timestamp) VALUES (%s, 0, 0, 0, NULL)",
                    (normalized,),
                )
                pairs.append((int(cur.lastrowid), normalized))
    return pairs


def _get_last_run(campaign_id: int) -> Optional[Dict[str, Any]]:
    with db_session(dictionary=True) as (_, cur):
        cur.execute(
            """
            SELECT id, status, progress, total, results, error, started_at, finished_at
            FROM campaign_runs
            WHERE campaign_id=%s
            ORDER BY id DESC
            LIMIT 1
            """,
            (campaign_id,),
        )
        r = cur.fetchone()
        if not r:
            return None
        if r.get("results") and isinstance(r["results"], str):
            try:
                r["results"] = json.loads(r["results"])
            except Exception:
                pass
        for dt_key in ("started_at", "finished_at"):
            if r.get(dt_key):
                r[dt_key] = str(r[dt_key])
        return r


@router.post("/campaigns")
def create_campaign(req: CampaignCreateRequest):
    urls = [str(u).strip() for u in (req.websiteIds or []) if str(u).strip()]
    pairs = _ensure_websites_exist(urls)

    with db_session() as (_, cur):
        cur.execute(
            """
            INSERT INTO campaigns
              (name, description, sender_name, sender_email, subject_line, message_body, max_websites, status)
            VALUES
              (%s, %s, %s, %s, %s, %s, %s, 'draft')
            """,
            (
                req.name.strip(),
                req.description,
                req.senderName,
                req.senderEmail,
                req.subjectLine,
                req.messageBody,
                int(req.maxWebsites or 500),
            ),
        )
        campaign_id = int(cur.lastrowid)

        if pairs:
            cur.executemany(
                "INSERT INTO campaign_websites (campaign_id, website_id, website_url, status) VALUES (%s, %s, %s, 'pending')",
                [(campaign_id, wid, url) for wid, url in pairs],
            )

        if req.fieldStrategies:
            strat_rows = []
            for concept, cfg in req.fieldStrategies.items():
                strategy = (cfg.get("strategy") or "constant").strip().lower()
                val = cfg.get("value") if strategy in ("constant", "custom") else None
                strat_rows.append((campaign_id, str(concept), strategy, val))
            if strat_rows:
                cur.executemany(
                    "INSERT INTO campaign_field_strategy (campaign_id, field_concept, strategy, constant_value) VALUES (%s, %s, %s, %s)",
                    strat_rows,
                )

    return {"ok": True, "campaignId": campaign_id}


@router.get("/campaigns")
def list_campaigns(
    search: Optional[str] = None,
    status: Optional[str] = None,
    sort_by: str = Query(default="newest", pattern="^(newest|oldest|name)$"),
):
    where_clauses: List[str] = []
    params: List[Any] = []
    if search and search.strip():
        where_clauses.append("(c.name LIKE %s OR c.description LIKE %s)")
        q = f"%{search.strip()}%"
        params.extend([q, q])
    if status and status.strip() and status != "all":
        where_clauses.append("c.status = %s")
        params.append(status.strip().lower())

    where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
    order_sql = {
        "newest": "c.id DESC",
        "oldest": "c.id ASC",
        "name": "c.name ASC",
    }[sort_by]

    with db_session(dictionary=True) as (_, cur):
        cur.execute(
            f"""
            SELECT
              c.id,
              c.name,
              c.description,
              c.status,
              c.results_success,
              c.results_failed,
              c.results_captcha,
              c.created_at,
              c.updated_at,
              (SELECT COUNT(*) FROM campaign_websites cw WHERE cw.campaign_id=c.id) AS targets,
              (SELECT COUNT(*) FROM campaign_websites cw WHERE cw.campaign_id=c.id AND cw.status NOT IN ('pending','scraping','filling')) AS processed_count
            FROM campaigns c
            {where_sql}
            ORDER BY {order_sql}
            """,
            tuple(params),
        )
        items = cur.fetchall() or []

    for item in items:
        for k in ("created_at", "updated_at"):
            if item.get(k):
                item[k] = str(item[k])
        targets = int(item.get("targets") or 0)
        processed = int(item.get("processed_count") or 0)
        item["targets"] = targets
        item["processed"] = processed
        item["progress_pct"] = round((processed / targets) * 100) if targets > 0 else 0

    return {"items": items}


@router.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: int):
    with db_session(dictionary=True) as (_, cur):
        cur.execute("SELECT * FROM campaigns WHERE id=%s", (campaign_id,))
        c = cur.fetchone()
        if not c:
            raise HTTPException(status_code=404, detail="Campaign not found")

        cur.execute(
            """
            SELECT id, website_id, website_url, status, submission_id, error, processed_at
            FROM campaign_websites
            WHERE campaign_id=%s
            ORDER BY id ASC
            """,
            (campaign_id,),
        )
        websites = cur.fetchall() or []
        for w in websites:
            if w.get("processed_at"):
                w["processed_at"] = str(w["processed_at"])

        cur.execute(
            "SELECT field_concept, strategy, constant_value FROM campaign_field_strategy WHERE campaign_id=%s",
            (campaign_id,),
        )
        c["fieldStrategies"] = cur.fetchall() or []

    for k in ("created_at", "updated_at"):
        if c.get(k):
            c[k] = str(c[k])
    c["websites"] = websites
    c["lastRun"] = _get_last_run(campaign_id)
    c["targets"] = len(websites)
    return c


@router.put("/campaigns/{campaign_id}")
def update_campaign(campaign_id: int, req: CampaignUpdateRequest):
    with db_session(dictionary=True) as (_, cur):
        cur.execute("SELECT id, status FROM campaigns WHERE id=%s", (campaign_id,))
        c = cur.fetchone()
        if not c:
            raise HTTPException(status_code=404, detail="Campaign not found")
        if c["status"] in ("running", "queued", "scraping", "filling"):
            raise HTTPException(status_code=400, detail="Cannot edit an active campaign")

        updates: List[str] = []
        vals: List[Any] = []
        mapping = {
            "name": req.name,
            "description": req.description,
            "sender_name": req.senderName,
            "sender_email": req.senderEmail,
            "subject_line": req.subjectLine,
            "message_body": req.messageBody,
            "max_websites": req.maxWebsites,
        }
        for col, val in mapping.items():
            if val is not None:
                updates.append(f"{col}=%s")
                vals.append(val)
        if updates:
            cur.execute(f"UPDATE campaigns SET {', '.join(updates)} WHERE id=%s", tuple(vals + [campaign_id]))

        if req.websiteIds is not None:
            urls = [str(u).strip() for u in req.websiteIds if str(u).strip()]
            pairs = _ensure_websites_exist(urls)
            cur.execute("DELETE FROM campaign_websites WHERE campaign_id=%s", (campaign_id,))
            if pairs:
                cur.executemany(
                    "INSERT INTO campaign_websites (campaign_id, website_id, website_url, status) VALUES (%s, %s, %s, 'pending')",
                    [(campaign_id, wid, url) for wid, url in pairs],
                )

        if req.fieldStrategies is not None:
            cur.execute("DELETE FROM campaign_field_strategy WHERE campaign_id=%s", (campaign_id,))
            strat_rows = []
            for concept, cfg in req.fieldStrategies.items():
                strategy = (cfg.get("strategy") or "constant").strip().lower()
                val = cfg.get("value") if strategy in ("constant", "custom") else None
                strat_rows.append((campaign_id, str(concept), strategy, val))
            if strat_rows:
                cur.executemany(
                    "INSERT INTO campaign_field_strategy (campaign_id, field_concept, strategy, constant_value) VALUES (%s, %s, %s, %s)",
                    strat_rows,
                )

    return {"ok": True, "campaignId": campaign_id}


@router.delete("/campaigns/{campaign_id}")
def delete_campaign(campaign_id: int):
    if is_campaign_active(campaign_id):
        raise HTTPException(status_code=409, detail="Stop or cancel the running campaign before deleting")

    with db_session() as (_, cur):
        cur.execute("DELETE FROM campaign_websites WHERE campaign_id=%s", (campaign_id,))
        cur.execute("DELETE FROM campaign_field_strategy WHERE campaign_id=%s", (campaign_id,))
        cur.execute("DELETE FROM campaign_runs WHERE campaign_id=%s", (campaign_id,))
        cur.execute("DELETE FROM campaigns WHERE id=%s", (campaign_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Campaign not found")
    return {"ok": True}


@router.post("/campaigns/{campaign_id}/duplicate")
def duplicate_campaign(campaign_id: int):
    with db_session(dictionary=True) as (_, cur):
        cur.execute("SELECT * FROM campaigns WHERE id=%s", (campaign_id,))
        orig = cur.fetchone()
        if not orig:
            raise HTTPException(status_code=404, detail="Campaign not found")

        cur.execute(
            """
            INSERT INTO campaigns (name, description, sender_name, sender_email, subject_line, message_body, max_websites, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'draft')
            """,
            (
                f"{orig['name']} (Copy)",
                orig.get("description"),
                orig.get("sender_name"),
                orig.get("sender_email"),
                orig.get("subject_line"),
                orig.get("message_body"),
                orig.get("max_websites") or 500,
            ),
        )
        new_id = int(cur.lastrowid)

        cur.execute("SELECT website_id, website_url FROM campaign_websites WHERE campaign_id=%s", (campaign_id,))
        wrows = cur.fetchall() or []
        if wrows:
            cur.executemany(
                "INSERT INTO campaign_websites (campaign_id, website_id, website_url, status) VALUES (%s, %s, %s, 'pending')",
                [(new_id, w["website_id"], w["website_url"]) for w in wrows],
            )

        cur.execute("SELECT field_concept, strategy, constant_value FROM campaign_field_strategy WHERE campaign_id=%s", (campaign_id,))
        srows = cur.fetchall() or []
        if srows:
            cur.executemany(
                "INSERT INTO campaign_field_strategy (campaign_id, field_concept, strategy, constant_value) VALUES (%s, %s, %s, %s)",
                [(new_id, s["field_concept"], s["strategy"], s["constant_value"]) for s in srows],
            )

    return {"ok": True, "campaignId": new_id}


@router.get("/campaigns/{campaign_id}/status")
def get_campaign_status(campaign_id: int):
    lr = _get_last_run(campaign_id)
    with db_session(dictionary=True) as (_, cur):
        cur.execute("SELECT status FROM campaigns WHERE id=%s", (campaign_id,))
        camp = cur.fetchone()
        if not camp:
            raise HTTPException(status_code=404, detail="Campaign not found")

        cur.execute(
            """
            SELECT id, website_id, website_url, status, submission_id, error, processed_at
            FROM campaign_websites
            WHERE campaign_id=%s
            ORDER BY id ASC
            """,
            (campaign_id,),
        )
        websites = cur.fetchall() or []
        for w in websites:
            if w.get("processed_at"):
                w["processed_at"] = str(w["processed_at"])

    if not lr:
        return {
            "running": False,
            "status": camp["status"] or "draft",
            "progress": 0,
            "total": len(websites),
            "results": None,
            "websites": websites,
        }

    return {
        "running": is_campaign_active(campaign_id) or lr["status"] in ("queued", "running", "scraping", "clustering", "filling"),
        "status": lr["status"],
        "campaignStatus": camp["status"],
        "progress": int(lr.get("progress") or 0),
        "total": int(lr.get("total") or len(websites)),
        "results": lr.get("results"),
        "error": lr.get("error"),
        "websites": websites,
    }


@router.post("/campaigns/{campaign_id}/start")
async def start_campaign(campaign_id: int):
    try:
        run_id = start_campaign_run(campaign_id, resume=False, restart=False)
        return {"ok": True, "campaignId": campaign_id, "runId": run_id}
    except LookupError:
        raise HTTPException(status_code=404, detail="Campaign not found")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/campaigns/{campaign_id}/resume")
async def resume_campaign(campaign_id: int):
    try:
        run_id = start_campaign_run(campaign_id, resume=True, restart=False)
        return {"ok": True, "campaignId": campaign_id, "runId": run_id}
    except LookupError:
        raise HTTPException(status_code=404, detail="Campaign not found")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/campaigns/{campaign_id}/restart")
async def restart_campaign(campaign_id: int):
    try:
        run_id = start_campaign_run(campaign_id, resume=False, restart=True)
        return {"ok": True, "campaignId": campaign_id, "runId": run_id}
    except LookupError:
        raise HTTPException(status_code=404, detail="Campaign not found")
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/campaigns/{campaign_id}/pause")
def pause_campaign(campaign_id: int):
    pause_campaign_run(campaign_id)
    return {"ok": True, "campaignId": campaign_id, "status": "paused"}


@router.post("/campaigns/{campaign_id}/cancel")
def cancel_campaign(campaign_id: int):
    cancel_campaign_run(campaign_id)
    return {"ok": True, "campaignId": campaign_id, "status": "cancelled"}


# ---------------- Legacy ad-hoc fill-all-forms ----------------
@router.post("/fill-all-forms")
async def fill_all_forms_endpoint(request: FillFormsRequest):
    job_id = str(uuid.uuid4())
    userdata = request.userdata or request.userData or {}
    maxwebsites = request.maxwebsites or request.maxWebsites or 50

    _job_statuses[job_id] = {"running": True, "progress": 0, "total": 0, "results": None}

    async def runjob():
        try:
            results = await fillallforms(userdata, int(maxwebsites))
            if not isinstance(results, dict):
                results = {"total": 0, "success": 0, "failed": 0, "captcha": 0}
            _job_statuses[job_id]["results"] = results
            _job_statuses[job_id]["total"] = int(results.get("total") or 0)
            _job_statuses[job_id]["progress"] = int(results.get("total") or 0)
        except Exception as e:
            traceback.print_exc()
            _job_statuses[job_id]["results"] = {"total": 0, "success": 0, "failed": 0, "captcha": 0, "error": str(e)}
        finally:
            _job_statuses[job_id]["running"] = False

    task = asyncio.create_task(runjob())
    _legacy_tasks.add(task)
    task.add_done_callback(_legacy_tasks.discard)

    return {"ok": True, "message": "Form filling started", "jobId": job_id}


@router.get("/fill-status/{job_id}")
def get_fill_status(job_id: str):
    if job_id not in _job_statuses:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_statuses[job_id]


@router.get("/fill-status")
def get_fill_status_legacy():
    if not _job_statuses:
        return {"running": False, "progress": 0, "total": 0, "results": None}
    latest_job_id = list(_job_statuses.keys())[-1]
    return _job_statuses[latest_job_id]
