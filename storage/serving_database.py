"""Serving database access module for UI queries.

Serving is Postgres-only. SQLite fallback is deprecated and unsupported.
Writes should continue to use storage.database.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Any, Optional

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # pragma: no cover - optional dependency for Postgres
    psycopg = None
    dict_row = None

logger = logging.getLogger(__name__)

POSTGRES_SERVING_DSN_ENV = "POSTGRES_SERVING_DSN"

_serving_postgres_dsn: Optional[str] = os.getenv(POSTGRES_SERVING_DSN_ENV)

_DATE_NOW_REGEX = re.compile(r"date\('now',\s*\?\)", re.IGNORECASE)


def configure_serving_database(dsn: Optional[str] = None) -> None:
    """Configure the Postgres DSN used for serving (read-only) queries."""
    global _serving_postgres_dsn
    _serving_postgres_dsn = dsn or os.getenv(POSTGRES_SERVING_DSN_ENV)
    if _serving_postgres_dsn:
        logger.info("Serving queries configured to use Postgres")
    else:
        logger.error("Serving queries require Postgres; POSTGRES_SERVING_DSN is not set")


def _convert_sqlite_sql(sql: str) -> str:
    sql = _DATE_NOW_REGEX.sub("CURRENT_DATE + %s::interval", sql)
    return sql.replace("?", "%s")


def _ensure_postgres_available() -> None:
    if psycopg is None:
        raise RuntimeError(
            "Postgres serving is configured but psycopg is not installed. "
            "Install psycopg to enable Postgres read routing."
        )


async def _postgres_query(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    _ensure_postgres_available()
    loop = asyncio.get_event_loop()
    converted_sql = _convert_sqlite_sql(sql)

    def _execute() -> list[dict[str, Any]]:
        with psycopg.connect(_serving_postgres_dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(converted_sql, params)
                return cursor.fetchall()

    return await loop.run_in_executor(None, _execute)


async def _postgres_query_one(sql: str, params: tuple = ()) -> Optional[dict[str, Any]]:
    _ensure_postgres_available()
    loop = asyncio.get_event_loop()
    converted_sql = _convert_sqlite_sql(sql)

    def _execute() -> Optional[dict[str, Any]]:
        with psycopg.connect(_serving_postgres_dsn, row_factory=dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(converted_sql, params)
                return cursor.fetchone()

    return await loop.run_in_executor(None, _execute)


async def db_query(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    """Execute a SELECT query against the serving database when available."""
    return await _postgres_query(sql, params)


async def db_query_one(sql: str, params: tuple = ()) -> Optional[dict[str, Any]]:
    """Execute a SELECT query and return the first row or None."""
    return await _postgres_query_one(sql, params)


async def db_execute(sql: str, params: tuple = ()) -> int:
    """Execute an INSERT/UPDATE/DELETE statement. Returns rowcount."""
    _ensure_postgres_available()
    loop = asyncio.get_event_loop()
    converted_sql = _convert_sqlite_sql(sql)

    def _execute() -> int:
        with psycopg.connect(_serving_postgres_dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(converted_sql, params)
                conn.commit()
                return cursor.rowcount

    return await loop.run_in_executor(None, _execute)


async def table_exists(table_name: str) -> bool:
    """Check if a table exists in the serving database."""
    row = await _postgres_query_one(
        "SELECT to_regclass(%s) IS NOT NULL AS exists",
        (table_name,),
    )
    return bool(row and row.get("exists"))
    if not _serving_postgres_dsn:
        raise RuntimeError("POSTGRES_SERVING_DSN must be set for serving queries.")
