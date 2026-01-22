"""Serving database access module for UI queries.

This module routes read-only queries to Postgres when configured,
falling back to SQLite for non-precomputed tables or when Postgres
is not configured. Writes should continue to use storage.database.
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

from storage.database import db_query as sqlite_db_query, db_query_one as sqlite_db_query_one

logger = logging.getLogger(__name__)

POSTGRES_SERVING_DSN_ENV = "POSTGRES_SERVING_DSN"

_serving_postgres_dsn: Optional[str] = os.getenv(POSTGRES_SERVING_DSN_ENV)

_PRECOMPUTE_TABLES = (
    "home_seat_daily",
    "home_publisher_daily",
    "home_geo_daily",
    "home_config_daily",
    "home_size_daily",
    "rtb_funnel_daily",
    "rtb_publisher_daily",
    "rtb_geo_daily",
    "rtb_app_daily",
    "rtb_app_size_daily",
    "rtb_app_country_daily",
    "rtb_app_creative_daily",
    "config_size_daily",
    "config_geo_daily",
    "config_publisher_daily",
    "config_creative_daily",
    "dim_creative",
    "dim_publisher",
    "dim_country",
    "dim_billing",
    "dim_time",
)

_TABLE_REGEX = [re.compile(rf"\b{re.escape(table)}\b", re.IGNORECASE) for table in _PRECOMPUTE_TABLES]
_DATE_NOW_REGEX = re.compile(r"date\('now',\s*\?\)", re.IGNORECASE)


def configure_serving_database(dsn: Optional[str] = None) -> None:
    """Configure the Postgres DSN used for serving (read-only) queries."""
    global _serving_postgres_dsn
    _serving_postgres_dsn = dsn or os.getenv(POSTGRES_SERVING_DSN_ENV)
    if _serving_postgres_dsn:
        logger.info("Serving queries configured to use Postgres")
    else:
        logger.info("Serving queries using SQLite (Postgres not configured)")


def _should_use_postgres(sql: str) -> bool:
    if not _serving_postgres_dsn:
        return False
    return any(regex.search(sql) for regex in _TABLE_REGEX)


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
    if _should_use_postgres(sql):
        return await _postgres_query(sql, params)
    return await sqlite_db_query(sql, params)


async def db_query_one(sql: str, params: tuple = ()) -> Optional[dict[str, Any]]:
    """Execute a SELECT query and return the first row or None."""
    if _should_use_postgres(sql):
        return await _postgres_query_one(sql, params)
    return await sqlite_db_query_one(sql, params)


async def table_exists(table_name: str) -> bool:
    """Check if a table exists in the serving database (or SQLite fallback)."""
    if _serving_postgres_dsn and table_name in _PRECOMPUTE_TABLES:
        row = await _postgres_query_one(
            "SELECT to_regclass(%s) IS NOT NULL AS exists",
            (table_name,),
        )
        return bool(row and row.get("exists"))

    row = await sqlite_db_query_one(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    )
    return bool(row)
