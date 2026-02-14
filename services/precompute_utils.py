"""Shared utilities for precompute refresh jobs."""

from __future__ import annotations

import os
import socket
from datetime import datetime, timedelta
from typing import Iterable, Optional, Sequence


DATE_FORMAT = "%Y-%m-%d"
DEFAULT_BUYER_KEY = "__all__"
DEFAULT_TABLE_KEY = "__all__"


def _parse_date(value: str) -> datetime.date:
    return datetime.strptime(value, DATE_FORMAT).date()


def normalize_refresh_dates(
    *,
    dates: Optional[Iterable[str]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    days: Optional[int] = None,
) -> list[str]:
    """Normalize refresh inputs into a sorted list of YYYY-MM-DD strings."""
    parsed_dates: list[datetime.date] = []
    if dates:
        parsed_dates = [_parse_date(value) for value in dates]
    elif days is not None:
        if days < 1:
            raise ValueError("days must be >= 1")
        today = datetime.utcnow().date()
        parsed_dates = [today - timedelta(days=offset) for offset in range(days)]
    elif start_date and end_date:
        start = _parse_date(start_date)
        end = _parse_date(end_date)
        if start > end:
            raise ValueError("start_date must be <= end_date")
        parsed_dates = [start + timedelta(days=offset) for offset in range((end - start).days + 1)]
    else:
        raise ValueError("Provide dates, days, or start_date/end_date to refresh.")

    return [value.isoformat() for value in sorted(parsed_dates)]


def refresh_window(dates: Sequence[str]) -> tuple[str, str]:
    parsed = [_parse_date(value) for value in dates]
    return min(parsed).isoformat(), max(parsed).isoformat()


def ensure_refresh_log_table(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS precompute_refresh_log (
            cache_name TEXT NOT NULL,
            buyer_account_id TEXT NOT NULL,
            refresh_start TEXT,
            refresh_end TEXT,
            refreshed_at TEXT NOT NULL,
            PRIMARY KEY (cache_name, buyer_account_id)
        )
        """
    )


def record_refresh_log(
    conn,
    *,
    cache_name: str,
    buyer_account_id: Optional[str],
    dates: Sequence[str],
) -> None:
    ensure_refresh_log_table(conn)
    refresh_start, refresh_end = refresh_window(dates)
    refreshed_at = datetime.utcnow().isoformat()
    buyer_key = buyer_account_id or DEFAULT_BUYER_KEY
    conn.execute(
        """
        INSERT OR REPLACE INTO precompute_refresh_log (
            cache_name, buyer_account_id, refresh_start, refresh_end, refreshed_at
        ) VALUES (?, ?, ?, ?, ?)
        """,
        (cache_name, buyer_key, refresh_start, refresh_end, refreshed_at),
    )


def ensure_refresh_log_table_postgres(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS precompute_refresh_log (
            cache_name TEXT NOT NULL,
            buyer_account_id TEXT NOT NULL,
            refresh_start TEXT,
            refresh_end TEXT,
            refreshed_at TEXT NOT NULL,
            PRIMARY KEY (cache_name, buyer_account_id)
        )
        """
    )


def record_refresh_log_postgres(
    conn,
    *,
    cache_name: str,
    buyer_account_id: Optional[str],
    dates: Sequence[str],
) -> None:
    ensure_refresh_log_table_postgres(conn)
    refresh_start, refresh_end = refresh_window(dates)
    refreshed_at = datetime.utcnow().isoformat()
    buyer_key = buyer_account_id or DEFAULT_BUYER_KEY
    conn.execute(
        """
        INSERT INTO precompute_refresh_log (
            cache_name, buyer_account_id, refresh_start, refresh_end, refreshed_at
        ) VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (cache_name, buyer_account_id) DO UPDATE SET
            refresh_start = EXCLUDED.refresh_start,
            refresh_end = EXCLUDED.refresh_end,
            refreshed_at = EXCLUDED.refreshed_at
        """,
        (cache_name, buyer_key, refresh_start, refresh_end, refreshed_at),
    )


def ensure_refresh_runs_table_postgres(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS precompute_refresh_runs (
            id BIGSERIAL PRIMARY KEY,
            run_id TEXT NOT NULL,
            cache_name TEXT NOT NULL,
            table_name TEXT NOT NULL,
            buyer_account_id TEXT NOT NULL,
            refresh_start TEXT,
            refresh_end TEXT,
            status TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed')),
            row_count BIGINT NOT NULL DEFAULT 0,
            error_text TEXT,
            host TEXT NOT NULL DEFAULT 'unknown',
            app_version TEXT NOT NULL DEFAULT 'unknown',
            git_sha TEXT NOT NULL DEFAULT 'unknown',
            started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            finished_at TIMESTAMPTZ
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_precompute_runs_started_at "
        "ON precompute_refresh_runs(started_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_precompute_runs_run_id "
        "ON precompute_refresh_runs(run_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_precompute_runs_cache_table_status "
        "ON precompute_refresh_runs(cache_name, table_name, status, started_at DESC)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_precompute_runs_buyer_dates "
        "ON precompute_refresh_runs(buyer_account_id, refresh_start, refresh_end, started_at DESC)"
    )


def _runtime_host() -> str:
    return os.getenv("HOSTNAME") or socket.gethostname() or "unknown"


def _runtime_version() -> tuple[str, str]:
    app_version = os.getenv("APP_VERSION") or "unknown"
    git_sha = os.getenv("GIT_SHA") or "unknown"
    return app_version, git_sha


def record_refresh_run_postgres(
    conn,
    *,
    run_id: str,
    cache_name: str,
    table_name: Optional[str],
    buyer_account_id: Optional[str],
    dates: Sequence[str],
    status: str,
    row_count: int = 0,
    error_text: Optional[str] = None,
    started_at: Optional[str] = None,
    finished_at: Optional[str] = None,
) -> None:
    """Append one immutable precompute run ledger row."""
    ensure_refresh_runs_table_postgres(conn)
    refresh_start, refresh_end = refresh_window(dates)
    buyer_key = buyer_account_id or DEFAULT_BUYER_KEY
    table_key = table_name or DEFAULT_TABLE_KEY
    app_version, git_sha = _runtime_version()
    started_at_value = started_at or datetime.utcnow().isoformat()

    conn.execute(
        """
        INSERT INTO precompute_refresh_runs (
            run_id, cache_name, table_name, buyer_account_id,
            refresh_start, refresh_end, status, row_count, error_text,
            host, app_version, git_sha, started_at, finished_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            run_id,
            cache_name,
            table_key,
            buyer_key,
            refresh_start,
            refresh_end,
            status,
            max(int(row_count), 0),
            error_text,
            _runtime_host(),
            app_version,
            git_sha,
            started_at_value,
            finished_at,
        ),
    )
