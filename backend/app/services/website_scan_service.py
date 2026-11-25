"""Background batch website scanning service with bounded concurrency and live progress."""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from app.automation.playwright_manager import managed_browser_context
from app.core.config import get_settings
from app.core.security import extract_domain, validate_target_url
from app.database.connection import db_session
from form_filler import MySQLDB, RandomValuePool, process_website

logger = logging.getLogger(__name__)

_scan_state: Dict[str, Any] = {
    "running": False,
    "stop_requested": False,
    "mode": "pending",
    "total": 0,
    "processed": 0,
    "form_found": 0,
    "no_form": 0,
    "captcha": 0,
    "failed": 0,
    "current_url": None,
    "error": None,
}
_scan_task: Optional[asyncio.Task] = None


def get_batch_scan_status() -> Dict[str, Any]:
    return {k: v for k, v in _scan_state.items() if k != "stop_requested"}


def stop_batch_scan() -> Dict[str, Any]:
    if _scan_state["running"]:
        _scan_state["stop_requested"] = True
    return get_batch_scan_status()


async def _run_batch_scan(mode: str, limit: Optional[int], concurrency: int, force: bool = False) -> None:
    try:
        # Never re-scan already-found forms/captcha unless force=True
        if mode == "all" and force:
            where_sql = ""
        elif mode == "pending_and_noform":
            where_sql = "WHERE timestamp IS NULL OR (form_found = 0 AND has_captcha = 0)"
        else:
            where_sql = "WHERE timestamp IS NULL"
        limit_sql = f"LIMIT {int(limit)}" if (limit and limit > 0) else ""

        with db_session(dictionary=True) as (_, cur):
            cur.execute(
                f"SELECT id, url FROM websites {where_sql} ORDER BY id DESC {limit_sql}"
            )
            rows: List[Dict[str, Any]] = cur.fetchall() or []

        _scan_state.update(
            {
                "running": True,
                "stop_requested": False,
                "mode": mode,
                "total": len(rows),
                "processed": 0,
                "form_found": 0,
                "no_form": 0,
                "captcha": 0,
                "failed": 0,
                "current_url": None,
                "error": None,
            }
        )

        if not rows:
            return

        sem = asyncio.Semaphore(max(1, min(10, concurrency)))
        lock = asyncio.Lock()

        async def _is_reachable(url: str) -> bool:
            host = extract_domain(url)
            if host in {"localhost", "127.0.0.1"}:
                return True
            try:
                async with httpx.AsyncClient(timeout=4.0, follow_redirects=True, verify=False) as client:
                    await client.head(url)
                return True
            except (httpx.ConnectError, httpx.ConnectTimeout):
                return False
            except Exception:
                # Any HTTP/TLS/protocol response means host is reachable; let Playwright handle it
                return True

        async with managed_browser_context(block_assets=True) as context:
            async def scan_one(row: Dict[str, Any]) -> None:
                if _scan_state["stop_requested"]:
                    return
                wid = int(row["id"])
                raw_url = str(row["url"] or "").strip()
                ok, norm_url, err = validate_target_url(raw_url)
                if not ok:
                    async with lock:
                        _scan_state["processed"] += 1
                        _scan_state["failed"] += 1
                    return

                async with sem:
                    if _scan_state["stop_requested"]:
                        return
                    _scan_state["current_url"] = norm_url
                    db = MySQLDB()
                    pool = RandomValuePool()
                    try:
                        if not await _is_reachable(norm_url):
                            db.update_website_scan_status(wid, form_found=False, has_captcha=False, is_dead=True)
                            async with lock:
                                _scan_state["processed"] += 1
                                _scan_state["failed"] += 1
                            return

                        res = await process_website(
                            db=db,
                            pool=pool,
                            context=context,
                            website_id=wid,
                            url=norm_url,
                            mode="scrape",
                        )
                        st = str(res.get("status") or "").lower()
                        async with lock:
                            _scan_state["processed"] += 1
                            if st == "scraped":
                                _scan_state["form_found"] += 1
                            elif st == "captcha":
                                _scan_state["captcha"] += 1
                            elif st == "noform":
                                _scan_state["no_form"] += 1
                            else:
                                _scan_state["failed"] += 1
                    except Exception as exc:
                        logger.warning(f"Batch scan error for {norm_url}: {exc}")
                        async with lock:
                            _scan_state["processed"] += 1
                            _scan_state["failed"] += 1
                    finally:
                        pool.close()
                        db.close()

            # Process in chunks of 50 so stop_requested is responsive and memory stays flat
            chunk_size = 50
            for i in range(0, len(rows), chunk_size):
                if _scan_state["stop_requested"]:
                    break
                chunk = rows[i : i + chunk_size]
                await asyncio.gather(*(scan_one(r) for r in chunk))

    except Exception as exc:
        logger.exception(f"Batch scan failed: {exc}")
        _scan_state["error"] = str(exc)
    finally:
        _scan_state["running"] = False
        _scan_state["current_url"] = None


def start_batch_scan(
    mode: str = "pending",
    limit: Optional[int] = None,
    concurrency: Optional[int] = None,
    force: bool = False,
) -> Dict[str, Any]:
    global _scan_task
    if _scan_state["running"] and _scan_task and not _scan_task.done():
        raise ValueError("A batch scan is already running")

    settings = get_settings()
    conc = concurrency if concurrency is not None else settings.concurrency
    _scan_state["running"] = True
    _scan_task = asyncio.create_task(_run_batch_scan(mode=mode, limit=limit, concurrency=conc, force=force))
    return get_batch_scan_status()
