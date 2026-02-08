"""Shared utilities for QPS importers and analyzers."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

DB_PATH = None  # Legacy SQLite removed — Postgres is the only runtime database


def parse_date(date_str: str) -> str:
    """Parse date from various formats to YYYY-MM-DD."""
    if not date_str:
        return ""
    formats = ["%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d", "%d/%m/%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return date_str


def parse_int(value, default: Optional[int] = 0) -> Optional[int]:
    """Parse integer, returning default for empty/invalid."""
    if value is None or value == "":
        return default
    if isinstance(value, int):
        return value
    try:
        return int(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return default


def parse_float(value, default: Optional[float] = 0.0) -> Optional[float]:
    """Parse float, returning default for empty/invalid."""
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").replace("$", "").strip())
    except (ValueError, TypeError):
        return default
