"""Pooled MySQL connection management and transaction helpers."""

import logging
from contextlib import contextmanager
from typing import Generator, Optional

import mysql.connector
from mysql.connector import pooling

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_pool: Optional[pooling.MySQLConnectionPool] = None


def _get_pool() -> pooling.MySQLConnectionPool:
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = pooling.MySQLConnectionPool(
            pool_name="form_insights_pool",
            pool_size=settings.mysql_pool_size,
            pool_reset_session=True,
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            database=settings.mysql_database,
            autocommit=False,
            charset="utf8mb4",
            use_unicode=True,
        )
    return _pool


def get_connection():
    """Return a MySQL connection from the pool (or direct connection on pool fallback)."""
    try:
        return _get_pool().get_connection()
    except Exception as e:
        logger.warning(f"Pool get_connection fallback: {e}")
        settings = get_settings()
        return mysql.connector.connect(
            host=settings.mysql_host,
            port=settings.mysql_port,
            user=settings.mysql_user,
            password=settings.mysql_password,
            database=settings.mysql_database,
            autocommit=False,
            charset="utf8mb4",
            use_unicode=True,
        )


@contextmanager
def db_session(dictionary: bool = False) -> Generator:
    """Context manager providing (conn, cursor) with automatic commit/rollback/cleanup."""
    conn = get_connection()
    cur = conn.cursor(dictionary=dictionary)
    try:
        yield conn, cur
        conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            cur.close()
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


def check_db_health() -> bool:
    """Verify MySQL connectivity with SELECT 1."""
    try:
        with db_session() as (_, cur):
            cur.execute("SELECT 1")
            cur.fetchone()
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False
