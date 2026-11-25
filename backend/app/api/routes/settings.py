"""Application settings and system status routes."""

from fastapi import APIRouter

from app.core.config import get_settings
from app.database.connection import check_db_health
from app.schemas.settings import AutomationSettingsUpdateRequest

router = APIRouter(prefix="/api", tags=["settings"])


@router.get("/settings")
def get_application_settings():
    settings = get_settings()
    db_ok = check_db_health()
    return {
        "status": {
            "backend": "connected",
            "database": "connected" if db_ok else "disconnected",
            "database_host": settings.mysql_host,
            "database_port": settings.mysql_port,
            "database_name": settings.mysql_database,
        },
        "app": {
            "name": settings.app_name,
            "environment": settings.app_env,
            "log_level": settings.log_level,
            "allow_localhost_testing": settings.allow_localhost_testing,
        },
        "automation": {
            "headless": settings.headless,
            "concurrency": settings.concurrency,
            "per_website_timeout_sec": settings.per_website_timeout_sec,
            "action_timeout_ms": settings.action_timeout_ms,
            "post_submit_wait_ms": settings.post_submit_wait_ms,
            "polite_delay_ms": settings.polite_delay_ms,
            "max_retries": settings.max_retries,
            "dry_run": settings.dry_run,
        },
    }


@router.put("/settings")
def update_application_settings(req: AutomationSettingsUpdateRequest):
    """Update runtime automation settings in memory."""
    settings = get_settings()
    for field in (
        "headless",
        "concurrency",
        "per_website_timeout_sec",
        "action_timeout_ms",
        "post_submit_wait_ms",
        "polite_delay_ms",
        "max_retries",
        "dry_run",
    ):
        val = getattr(req, field)
        if val is not None:
            setattr(settings, field, val)
    return {"ok": True, "automation": get_application_settings()["automation"]}
