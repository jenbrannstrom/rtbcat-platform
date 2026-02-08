"""Precompute Router - Scheduled refresh and monitoring endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from services.secrets_manager import get_secrets_manager
from services.config_precompute import refresh_config_breakdowns
from services.home_precompute import refresh_home_summaries
from services.precompute_service import PrecomputeService
from services.precompute_utils import normalize_refresh_dates, refresh_window
from services.precompute_validation import run_precompute_validation
from services.rtb_precompute import refresh_rtb_summaries

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
    secrets_mgr = get_secrets_manager()
    secret = secrets_mgr.get("PRECOMPUTE_REFRESH_SECRET")
    header_secret = request.headers.get("X-Precompute-Refresh-Secret")
    if not secret or not header_secret or header_secret != secret:
        raise HTTPException(status_code=403, detail="Invalid scheduler secret")

    refresh_days = secrets_mgr.get_int("PRECOMPUTE_REFRESH_DAYS", 2)
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
    secrets_mgr = get_secrets_manager()
    secret = secrets_mgr.get("PRECOMPUTE_MONITOR_SECRET")
    header_secret = request.headers.get("X-Precompute-Monitor-Secret")
    if not secret or not header_secret or header_secret != secret:
        raise HTTPException(status_code=403, detail="Invalid monitor secret")

    max_age_hours = secrets_mgr.get_int("PRECOMPUTE_REFRESH_MAX_AGE_HOURS", 36)
    if max_age_hours < 1:
        raise HTTPException(status_code=400, detail="PRECOMPUTE_REFRESH_MAX_AGE_HOURS must be >= 1")

    service = PrecomputeService()
    status = await service.get_health_status(max_age_hours)

    response = PrecomputeHealthResponse(
        ok=status.ok,
        max_age_hours=status.max_age_hours,
        checked_at=status.checked_at,
        stale_caches=status.stale_caches,
        missing_caches=status.missing_caches,
        cache_refresh_times=status.cache_refresh_times,
    )

    if not status.ok:
        return JSONResponse(status_code=503, content=response.model_dump())

    return response
