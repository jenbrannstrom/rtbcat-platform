"""Runtime guards for scheduler-triggered write endpoints."""

from __future__ import annotations

import os

from fastapi import HTTPException


def scheduler_enabled(flag_name: str) -> bool:
    """Return whether a scheduler endpoint is explicitly enabled."""
    return os.getenv(flag_name, "").strip().lower() in {"1", "true", "yes", "on"}


def require_scheduler_enabled(flag_name: str) -> None:
    """Reject scheduler-triggered work unless its ownership flag is enabled."""
    if not scheduler_enabled(flag_name):
        raise HTTPException(
            status_code=503,
            detail=f"Scheduler disabled by {flag_name}",
        )
