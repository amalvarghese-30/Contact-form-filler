"""Health check endpoints."""

from fastapi import APIRouter

from app.core.config import get_settings
from app.database.connection import check_db_health

router = APIRouter(tags=["health"])


@router.get("/health")
@router.get("/api/health")
def health_check():
    settings = get_settings()
    db_ok = check_db_health()
    return {
        "status": "ok" if db_ok else "degraded",
        "app": settings.app_name,
        "environment": settings.app_env,
        "database": "connected" if db_ok else "disconnected",
    }
