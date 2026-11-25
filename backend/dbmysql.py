"""Backward-compatible MySQL connection helper delegating to app.database.connection."""

import os
import mysql.connector

try:
    from app.database.connection import get_connection as _pooled_get_connection
except Exception:
    _pooled_get_connection = None


def _env(name: str, default):
    v = os.getenv(name)
    if v is None:
        return default
    s = str(v).strip()
    return default if s == "" else s


def getconn():
    """Canonical function expected by legacy modules: from dbmysql import getconn."""
    if _pooled_get_connection is not None:
        return _pooled_get_connection()

    return mysql.connector.connect(
        host=_env("MYSQL_HOST", "127.0.0.1"),
        port=int(_env("MYSQL_PORT", 3306)),
        user=_env("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=_env("MYSQL_DATABASE", "form_insights"),
        autocommit=False,
        charset="utf8mb4",
        use_unicode=True,
    )


def get_conn():
    return getconn()
