"""Shared utilities for precompute refresh jobs."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable, Optional, Sequence


DATE_FORMAT = "%Y-%m-%d"
DEFAULT_BUYER_KEY = "__all__"


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
