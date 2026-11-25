"""Centralized environment-based configuration for Contact Form Filler."""

import os
from functools import lru_cache
from pathlib import Path
from typing import List

from dotenv import load_dotenv

# Load .env from backend/ or repository root if present
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ROOT_DIR = _BACKEND_DIR.parent
for _env_path in (_BACKEND_DIR / ".env", _ROOT_DIR / ".env"):
    if _env_path.exists():
        load_dotenv(dotenv_path=_env_path, override=False)


def _env_str(name: str, default: str = "") -> str:
    val = os.getenv(name)
    if val is None:
        return default
    stripped = val.strip()
    return stripped if stripped else default


def _env_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if val is None:
        return default
    try:
        return int(val.strip())
    except ValueError:
        return default


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    lowered = val.strip().lower()
    if lowered in {"1", "true", "yes", "on"}:
        return True
    if lowered in {"0", "false", "no", "off"}:
        return False
    return default


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self) -> None:
        self.app_name: str = _env_str("APP_NAME", "Contact Form Filler")
        self.app_env: str = _env_str("APP_ENV", "development")
        self.log_level: str = _env_str("LOG_LEVEL", "INFO").upper()

        self.host: str = _env_str("HOST", "0.0.0.0")
        self.port: int = _env_int("PORT", 8000)

        raw_origins = _env_str(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174,http://localhost:3000,http://127.0.0.1:3000",
        )
        self.cors_origins: List[str] = [
            o.strip() for o in raw_origins.split(",") if o.strip() and o.strip() != "*"
        ]

        # Database
        self.mysql_host: str = _env_str("MYSQL_HOST", "127.0.0.1")
        self.mysql_port: int = _env_int("MYSQL_PORT", 3306)
        self.mysql_user: str = _env_str("MYSQL_USER", "root")
        self.mysql_password: str = os.getenv("MYSQL_PASSWORD", "")
        self.mysql_database: str = _env_str("MYSQL_DATABASE", "form_insights")
        self.mysql_pool_size: int = max(2, min(32, _env_int("MYSQL_POOL_SIZE", 10)))

        # Automation / Playwright
        self.headless: bool = _env_bool("HEADLESS", True)
        self.concurrency: int = max(1, min(10, _env_int("CONCURRENCY", 2)))
        self.per_website_timeout_sec: int = max(10, _env_int("PER_WEBSITE_TIMEOUT_SEC", 60))
        self.action_timeout_ms: int = max(1000, _env_int("ACTION_TIMEOUT_MS", 10000))
        self.post_submit_wait_ms: int = max(500, _env_int("POST_SUBMIT_WAIT_MS", 8000))
        self.submit_wait_ms: int = max(1000, _env_int("SUBMIT_WAIT_MS", 10000))
        self.polite_delay_ms: int = max(0, _env_int("POLITE_DELAY_MS", 500))
        self.max_retries: int = max(0, min(5, _env_int("MAX_RETRIES", 2)))
        self.dry_run: bool = _env_bool("DRY_RUN", False)
        self.allow_reruns: bool = _env_bool("ALLOW_RERUNS", True)

        # Security
        self.allow_localhost_testing: bool = _env_bool("ALLOW_LOCALHOST_TESTING", False)


@lru_cache()
def get_settings() -> Settings:
    return Settings()
