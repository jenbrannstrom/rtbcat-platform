"""Helpers for legacy list payloads stored as JSON or Postgres array literals."""

from __future__ import annotations

import csv
import json
from typing import Any


def parse_list_payload(value: Any) -> list[Any]:
    """Return a list from JSONB values, JSON strings, or Postgres array literals."""
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, (tuple, set, frozenset)):
        return list(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except Exception:
            if text.startswith("{") and text.endswith("}"):
                return _parse_postgres_array_literal(text)
            return []

        if parsed is None:
            return []
        if isinstance(parsed, dict):
            return []
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, (tuple, set, frozenset)):
            return list(parsed)
        return [parsed]

    try:
        return list(value)
    except TypeError:
        return []


def _parse_postgres_array_literal(value: str) -> list[str]:
    inner = value[1:-1]
    if not inner:
        return []
    reader = csv.reader([inner], delimiter=",", quotechar='"', escapechar="\\")
    return next(reader, [])
