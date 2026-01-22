"""Precompute Router - Scheduled refresh and monitoring endpoints."""

from __future__ import annotations

import logging
import os
import sqlite3
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from services.config_precompute import refresh_config_breakdowns
from services.home_precompute import refresh_home_summaries
from services.precompute_utils import normalize_refresh_dates, refresh_window
from services.precompute_validation import run_precompute_validation
from services.rtb_precompute import refresh_rtb_summaries
from storage.database import db_transaction_async

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Precompute"])


class PrecomputeRefreshResponse(BaseModel):
    """Response model for scheduled precompute refresh."""

    success: bool
    start_date: str
    end_date: str
    dates: list[str]
    home_summaries: dict
    config_breakdowns: dict
    rtb_summaries: dict
    validation: dict


class PrecomputeHealthResponse(BaseModel):
    """Response model for precompute health checks."""

    ok: bool
    max_age_hours: int = Field(..., ge=1)
    checked_at: str
    stale_caches: list[str] = Field(default_factory=list)
    missing_caches: list[str] = Field(default_factory=list)
    cache_refresh_times: dict[str, str] = Field(default_factory=dict)


@router.post("/precompute/refresh/scheduled", response_model=PrecomputeRefreshResponse)
async def refresh_precompute_scheduled(request: Request):
    """Trigger scheduled precompute refreshes for Cloud Scheduler or cron."""
    secret = os.getenv("PRECOMPUTE_REFRESH_SECRET")
    header_secret = request.headers.get("X-Precompute-Refresh-Secret")
    if not secret or not header_secret or header_secret != secret:
        raise HTTPException(status_code=403, detail="Invalid scheduler secret")

    refresh_days = int(os.getenv("PRECOMPUTE_REFRESH_DAYS", "2"))
    if refresh_days < 1:
        raise HTTPException(status_code=400, detail="PRECOMPUTE_REFRESH_DAYS must be >= 1")

    date_list = normalize_refresh_dates(days=refresh_days)
    refresh_start, refresh_end = refresh_window(date_list)

    home_result = await refresh_home_summaries(dates=date_list)
    config_result = await refresh_config_breakdowns(dates=date_list)
    rtb_result = await refresh_rtb_summaries(refresh_start, refresh_end)
    validation = await run_precompute_validation(refresh_start, refresh_end)

    return PrecomputeRefreshResponse(
        success=True,
        start_date=refresh_start,
        end_date=refresh_end,
        dates=date_list,
        home_summaries=home_result,
        config_breakdowns=config_result,
        rtb_summaries=rtb_result,
        validation=validation,
    )


@router.get("/precompute/health", response_model=PrecomputeHealthResponse)
async def precompute_health(request: Request):
    """Health check for precompute freshness (for monitoring)."""
    secret = os.getenv("PRECOMPUTE_MONITOR_SECRET")
    header_secret = request.headers.get("X-Precompute-Monitor-Secret")
    if not secret or not header_secret or header_secret != secret:
        raise HTTPException(status_code=403, detail="Invalid monitor secret")

    max_age_hours = int(os.getenv("PRECOMPUTE_REFRESH_MAX_AGE_HOURS", "36"))
    if max_age_hours < 1:
        raise HTTPException(status_code=400, detail="PRECOMPUTE_REFRESH_MAX_AGE_HOURS must be >= 1")

    required_caches = ["home_summaries", "config_breakdowns", "rtb_summaries"]
    cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)

    def _run(conn):
        try:
            rows = conn.execute(
                """
                SELECT cache_name, MAX(refreshed_at) AS refreshed_at
                FROM precompute_refresh_log
                GROUP BY cache_name
                """
            ).fetchall()
        except sqlite3.OperationalError:
            return []

        return [
            {
                "cache_name": row[0],
                "refreshed_at": row[1],
            }
            for row in rows
            if row[0]
        ]

    rows = await db_transaction_async(_run)
    refresh_map = {
        row["cache_name"]: row["refreshed_at"] for row in rows if row.get("refreshed_at")
    }

    stale_caches: list[str] = []
    missing_caches: list[str] = []
    cache_refresh_times: dict[str, str] = {}

    for cache_name in required_caches:
        refreshed_at = refresh_map.get(cache_name)
        if not refreshed_at:
            missing_caches.append(cache_name)
            continue

        try:
            refreshed_dt = datetime.fromisoformat(refreshed_at)
        except ValueError:
            missing_caches.append(cache_name)
            continue

        cache_refresh_times[cache_name] = refreshed_at
        if refreshed_dt < cutoff:
            stale_caches.append(cache_name)

    ok = not stale_caches and not missing_caches
    response = PrecomputeHealthResponse(
        ok=ok,
        max_age_hours=max_age_hours,
        checked_at=datetime.utcnow().isoformat(),
        stale_caches=stale_caches,
        missing_caches=missing_caches,
        cache_refresh_times=cache_refresh_times,
    )

    if not ok:
        logger.warning(
            "Precompute health check failed: stale=%s missing=%s",
            stale_caches,
            missing_caches,
        )
        return JSONResponse(status_code=503, content=response.model_dump())

    return response
