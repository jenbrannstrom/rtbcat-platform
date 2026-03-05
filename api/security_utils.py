"""Security helper utilities shared across API routers."""

from __future__ import annotations

import secrets


def has_valid_scheduler_secret(expected: str | None, provided: str | None) -> bool:
    """Validate shared secret header values using constant-time compare.

    Returns False for missing or malformed values instead of raising.
    """
    if not expected or not provided:
        return False
    try:
        return secrets.compare_digest(provided, expected)
    except TypeError:
        return False
