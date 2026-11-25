"""Campaign lifecycle, state machine, and two-phase execution service."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from app.automation.playwright_manager import managed_browser_context
from app.core.config import get_settings
from app.database.connection import db_session
from form_filler import MySQLDB, RandomValuePool, process_website

try:
    from cluster_raw_fields import cluster_websites
except Exception:
    cluster_websites = None

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {"queued", "running", "scraping", "clustering", "filling"}
VALID_CAMPAIGN_STATES = {"draft", "queued", "running", "paused", "completed", "failed", "cancelled"}

# Track running asyncio tasks by campaign_id to prevent duplicate concurrent runs
_active_tasks: Dict[int, asyncio.Task] = {}
_background_tasks: Set[asyncio.Task] = set()


def is_campaign_active(campaign_id: int) -> bool:
    task = _active_tasks.get(campaign_id)
    return task is not None and not task.done()


def _get_campaign_status(campaign_id: int) -> str:
    with db_session() as (_, cur):
        cur.execute("SELECT status FROM campaigns WHERE id=%s", (campaign_id,))
        row = cur.fetchone()
        return str(row[0]) if row else "unknown"


def _set_campaign_status(campaign_id: int, status: str) -> None:
    with db_session() as (_, cur):
        cur.execute("UPDATE campaigns SET status=%s WHERE id=%s", (status, campaign_id))


def _create_run(campaign_id: int, total: int = 0) -> int:
    with db_session() as (_, cur):
        cur.execute(
            """
            INSERT INTO campaign_runs (campaign_id, status, progress, total, started_at)
            VALUES (%s, 'queued', 0, %s, NOW())
            """,
            (campaign_id, total),
        )
        return int(cur.lastrowid)


def _update_run(run_id: int, **fields: Any) -> None:
    if not fields:
        return
    sets = [f"{k}=%s" for k in fields.keys()]
    vals = list(fields.values()) + [run_id]
    with db_session() as (_, cur):
        cur.execute(f"UPDATE campaign_runs SET {', '.join(sets)} WHERE id=%s", tuple(vals))


def _update_campaign_website(
    cw_id: int,
    status: str,
    submission_id: Optional[int] = None,
    error: Optional[str] = None,
) -> None:
    with db_session() as (_, cur):
        cur.execute(
            """
            UPDATE campaign_websites
            SET status=%s, submission_id=COALESCE(%s, submission_id), error=%s, processed_at=NOW()
            WHERE id=%s
            """,
            (status, submission_id if (submission_id and submission_id > 0) else None, (error or "")[:1000] or None, cw_id),
        )


def _compute_campaign_agg(campaign_id: int) -> Dict[str, Any]:
    """Compute exact progress and counts from campaign_websites records."""
    with db_session(dictionary=True) as (_, cur):
        cur.execute(
            "SELECT status, COUNT(*) AS cnt FROM campaign_websites WHERE campaign_id=%s GROUP BY status",
            (campaign_id,),
        )
        rows = cur.fetchall() or []

    counts: Dict[str, int] = {r["status"]: int(r["cnt"]) for r in rows}
    total = sum(counts.values())
    pending = counts.get("pending", 0) + counts.get("scraping", 0) + counts.get("filling", 0)
    processed = total - pending
    success = counts.get("success", 0)
    failed = counts.get("failed", 0) + counts.get("timeout", 0) + counts.get("nofill", 0)
    captcha = counts.get("captcha", 0)
    noform = counts.get("noform", 0)
    unconfirmed = counts.get("unconfirmed", 0)

    return {
        "total": total,
        "processed": processed,
        "remaining": pending,
        "success": success,
        "failed": failed,
        "captcha": captcha,
        "noform": noform,
        "unconfirmed": unconfirmed,
        "scraped": counts.get("scraped", 0),
    }


def _sync_campaign_summary_counts(campaign_id: int, agg: Dict[str, Any]) -> None:
    with db_session() as (_, cur):
        cur.execute(
            """
            UPDATE campaigns
            SET results_success=%s, results_failed=%s, results_captcha=%s
            WHERE id=%s
            """,
            (agg["success"], agg["failed"], agg["captcha"], campaign_id),
        )


async def _execute_campaign_pipeline(campaign_id: int, run_id: int, resume: bool = False) -> None:
    settings = get_settings()
    try:
        _set_campaign_status(campaign_id, "running")

        with db_session(dictionary=True) as (_, cur):
            cur.execute("SELECT * FROM campaigns WHERE id=%s", (campaign_id,))
            camp = cur.fetchone()
            if not camp:
                raise ValueError(f"Campaign {campaign_id} not found")

            if resume:
                cur.execute(
                    """
                    SELECT id, website_id, website_url, status
                    FROM campaign_websites
                    WHERE campaign_id=%s AND status IN ('pending', 'scraped', 'scraping', 'filling')
                    ORDER BY id ASC
                    """,
                    (campaign_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT id, website_id, website_url, status
                    FROM campaign_websites
                    WHERE campaign_id=%s
                    ORDER BY id ASC
                    """,
                    (campaign_id,),
                )
            targets = cur.fetchall() or []

            cur.execute(
                "SELECT field_concept, strategy, constant_value FROM campaign_field_strategy WHERE campaign_id=%s",
                (campaign_id,),
            )
            strat_rows = cur.fetchall() or []

        max_websites = int(camp.get("max_websites") or len(targets) or 500)
        targets = targets[:max_websites]

        field_strategies: Dict[str, Dict[str, Any]] = {
            r["field_concept"]: {
                "strategy": r["strategy"],
                "value": r["constant_value"],
            }
            for r in strat_rows
        }
        field_values: Dict[str, str] = {}
        if camp.get("sender_name"):
            field_values["fullname"] = camp["sender_name"]
            field_values["full_name"] = camp["sender_name"]
        if camp.get("sender_email"):
            field_values["email"] = camp["sender_email"]
        if camp.get("subject_line"):
            field_values["subject"] = camp["subject_line"]
        if camp.get("message_body"):
            field_values["message"] = camp["message_body"]

        agg = _compute_campaign_agg(campaign_id)
        _update_run(run_id, status="running", progress=agg["processed"], total=agg["total"], results=json.dumps(agg))

        if not targets:
            _update_run(run_id, status="completed", progress=agg["total"], total=agg["total"], results=json.dumps(agg), finished_at=datetime.now())
            _set_campaign_status(campaign_id, "completed")
            _sync_campaign_summary_counts(campaign_id, agg)
            return

        db = MySQLDB()
        pool = RandomValuePool()
        try:
            async with managed_browser_context() as context:
                # Phase 1 & 2 per target inside shared browser context
                scraped_targets: List[Dict[str, Any]] = []

                for t in targets:
                    cur_state = _get_campaign_status(campaign_id)
                    if cur_state in ("paused", "cancelled"):
                        agg = _compute_campaign_agg(campaign_id)
                        _update_run(run_id, status=cur_state, progress=agg["processed"], total=agg["total"], results=json.dumps(agg))
                        return

                    cw_id = int(t["id"])
                    wid = int(t["website_id"] or 0)
                    url = str(t["website_url"] or "").strip()

                    if t.get("status") == "scraped":
                        scraped_targets.append(t)
                        continue

                    _update_campaign_website(cw_id, "scraping")
                    _update_run(run_id, status="scraping", progress=agg["processed"], total=agg["total"], results=json.dumps(agg))

                    sr = await process_website(
                        db=db,
                        pool=pool,
                        context=context,
                        website_id=wid,
                        url=url,
                        mode="scrape",
                        campaign_id=campaign_id,
                    )
                    st = str(sr.get("status") or "failed").lower()
                    _update_campaign_website(cw_id, st, submission_id=sr.get("submission_id"), error=sr.get("error"))

                    if st == "scraped":
                        scraped_targets.append(t)

                    agg = _compute_campaign_agg(campaign_id)
                    _update_run(run_id, status="scraping", progress=agg["processed"], total=agg["total"], results=json.dumps(agg))

                # Optional clustering step
                wids = [int(t["website_id"]) for t in scraped_targets if t.get("website_id")]
                if cluster_websites is not None and wids:
                    try:
                        cluster_websites(wids)
                    except Exception as ce:
                        logger.warning(f"Clustering step warning: {ce}")

                # Phase 2: Fill & Submit for discovered forms
                for t in scraped_targets:
                    cur_state = _get_campaign_status(campaign_id)
                    if cur_state in ("paused", "cancelled"):
                        agg = _compute_campaign_agg(campaign_id)
                        _update_run(run_id, status=cur_state, progress=agg["processed"], total=agg["total"], results=json.dumps(agg))
                        return

                    cw_id = int(t["id"])
                    wid = int(t["website_id"] or 0)
                    url = str(t["website_url"] or "").strip()

                    _update_campaign_website(cw_id, "filling")
                    _update_run(run_id, status="filling", progress=agg["processed"], total=agg["total"], results=json.dumps(agg))

                    fr = await process_website(
                        db=db,
                        pool=pool,
                        context=context,
                        website_id=wid,
                        url=url,
                        mode="fill",
                        field_values=field_values,
                        field_strategies=field_strategies,
                        campaign_id=campaign_id,
                    )
                    st = str(fr.get("status") or "failed").lower()
                    _update_campaign_website(cw_id, st, submission_id=fr.get("submission_id"), error=fr.get("error"))

                    agg = _compute_campaign_agg(campaign_id)
                    _update_run(run_id, status="filling", progress=agg["processed"], total=agg["total"], results=json.dumps(agg))
                    _sync_campaign_summary_counts(campaign_id, agg)

                    if settings.polite_delay_ms > 0:
                        await asyncio.sleep(settings.polite_delay_ms / 1000.0)
        finally:
            pool.close()
            db.close()

        agg = _compute_campaign_agg(campaign_id)
        _sync_campaign_summary_counts(campaign_id, agg)
        _update_run(
            run_id,
            status="completed",
            progress=agg["processed"],
            total=agg["total"],
            results=json.dumps(agg),
            finished_at=datetime.now(),
        )
        _set_campaign_status(campaign_id, "completed")
    except Exception as exc:
        logger.exception(f"Campaign {campaign_id} run {run_id} failed: {exc}")
        try:
            agg = _compute_campaign_agg(campaign_id)
            _update_run(
                run_id,
                status="failed",
                error=str(exc)[:1000],
                progress=agg["processed"],
                total=agg["total"],
                results=json.dumps(agg),
                finished_at=datetime.now(),
            )
            _set_campaign_status(campaign_id, "failed")
        except Exception as inner_exc:
            logger.error(f"Failed to record campaign failure: {inner_exc}")
    finally:
        _active_tasks.pop(campaign_id, None)


def start_campaign_run(campaign_id: int, resume: bool = False, restart: bool = False) -> int:
    """Start, resume, or restart a campaign while preventing duplicate concurrent runs."""
    if is_campaign_active(campaign_id):
        raise ValueError("Campaign is already running")

    with db_session(dictionary=True) as (_, cur):
        cur.execute("SELECT id, status FROM campaigns WHERE id=%s", (campaign_id,))
        camp = cur.fetchone()
        if not camp:
            raise LookupError("Campaign not found")

        if restart:
            cur.execute(
                "UPDATE campaign_websites SET status='pending', error=NULL, submission_id=NULL, processed_at=NULL WHERE campaign_id=%s",
                (campaign_id,),
            )

        cur.execute("SELECT COUNT(*) AS cnt FROM campaign_websites WHERE campaign_id=%s", (campaign_id,))
        total = int((cur.fetchone() or {}).get("cnt") or 0)

    run_id = _create_run(campaign_id, total=total)
    _set_campaign_status(campaign_id, "queued")

    task = asyncio.create_task(_execute_campaign_pipeline(campaign_id, run_id, resume=resume))
    _active_tasks[campaign_id] = task
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return run_id


def pause_campaign_run(campaign_id: int) -> None:
    _set_campaign_status(campaign_id, "paused")


def cancel_campaign_run(campaign_id: int) -> None:
    _set_campaign_status(campaign_id, "cancelled")
    task = _active_tasks.get(campaign_id)
    if task and not task.done():
        # Pipeline checks status between steps; also update latest run
        with db_session() as (_, cur):
            cur.execute(
                "UPDATE campaign_runs SET status='cancelled', finished_at=NOW() WHERE campaign_id=%s AND status IN ('queued','running','scraping','filling') ORDER BY id DESC LIMIT 1",
                (campaign_id,),
            )
