"""Shared utilities for QPS importers and analyzers."""

from __future__ import annotations

import os
import re
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
    """Parse a numeric CSV value, including buyer-currency formatting.

    Authorized Buyers emits the buyer currency symbol in some seats' Spend
    columns (for example Uplivo's EUR seat).  Keep the numeric value verbatim
    while removing presentation-only currency symbols and spacing.
    """
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return float(value)
    try:
        text = str(value).strip().replace(",", "").replace("\u00a0", "")
        text = re.sub(r"^[\s$\u20ac\u00a3\u00a5]+|[\s$\u20ac\u00a3\u00a5]+$", "", text)
        return float(text)
    except (ValueError, TypeError):
        return default
