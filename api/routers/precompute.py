"""Precompute Router - Scheduled refresh and monitoring endpoints."""

from __future__ import annotations

import hmac
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from services.secrets_manager import get_secrets_manager
from services.precompute_queue import enqueue_precompute_job
from services.precompute_service import PrecomputeService
from services.precompute_utils import normalize_refresh_dates, refresh_window
from services.scheduler_guard import require_scheduler_enabled

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Precompute"])


class PrecomputeEnqueueResponse(BaseModel):
    """Response model for the scheduled precompute enqueue."""

    accepted: bool
    job_id: int
    status: str
    deduplicated: bool
    start_date: str
    end_date: str
    dates: list[str]


class PrecomputeHealthResponse(BaseModel):
    """Response model for precompute health checks."""

    ok: bool
    max_age_hours: int = Field(..., ge=1)
    checked_at: str
    stale_caches: list[str] = Field(default_factory=list)
    missing_caches: list[str] = Field(default_factory=list)
    cache_refresh_times: dict[str, str] = Field(default_factory=dict)
    latest_source_metric_date: str | None = None
    serving_metric_dates: dict[str, str | None] = Field(default_factory=dict)
    serving_lag_days: dict[str, int | None] = Field(default_factory=dict)
    max_date_drift_days: int | None = None
    date_parity_ok: bool = False


@router.post(
    "/precompute/refresh/scheduled",
    response_model=PrecomputeEnqueueResponse,
    status_code=202,
)
async def refresh_precompute_scheduled(request: Request) -> PrecomputeEnqueueResponse:
    """Enqueue the scheduled precompute refresh and return immediately.

    A full refresh runs for hours — past Cloud Scheduler's 30-minute attempt
    deadline and the edge proxy timeout — so the work is queued for the
    precompute worker instead of running inline. Scheduler success means
    "accepted"; /precompute/health remains the completion/freshness authority.
    """
    require_scheduler_enabled("CATSCAN_ENABLE_PRECOMPUTE_SCHEDULER")

    secrets_mgr = get_secrets_manager()
    secret = secrets_mgr.get("PRECOMPUTE_REFRESH_SECRET")
    header_secret = request.headers.get("X-Precompute-Refresh-Secret")
    if not secret or not header_secret or not hmac.compare_digest(header_secret, secret):
        raise HTTPException(status_code=403, detail="Invalid scheduler secret")

    refresh_days = secrets_mgr.get_int("PRECOMPUTE_REFRESH_DAYS", 2)
    if refresh_days < 1:
        raise HTTPException(status_code=400, detail="PRECOMPUTE_REFRESH_DAYS must be >= 1")

    date_list = normalize_refresh_dates(days=refresh_days)
    refresh_start, refresh_end = refresh_window(date_list)

    # Cloud Scheduler keeps X-CloudScheduler-ScheduleTime constant across
    # retries of one execution, so retries collapse onto one job. Without the
    # headers, the refresh window itself identifies the night's work.
    scheduler_job = request.headers.get("X-CloudScheduler-JobName")
    schedule_time = request.headers.get("X-CloudScheduler-ScheduleTime")
    if scheduler_job and schedule_time:
        dedupe_key = f"{scheduler_job}:{schedule_time}"
    else:
        dedupe_key = f"scheduler:{refresh_start}:{refresh_end}"

    result = await enqueue_precompute_job(
        source="scheduler",
        start_date=refresh_start,
        end_date=refresh_end,
        dedupe_key=dedupe_key,
        run_validation=True,
    )

    logger.info(
        "Scheduled precompute refresh accepted: job_id=%s deduplicated=%s window=%s..%s",
        result["job_id"],
        result["deduplicated"],
        refresh_start,
        refresh_end,
    )

    return PrecomputeEnqueueResponse(
        accepted=True,
        job_id=result["job_id"],
        status=result["status"],
        deduplicated=result["deduplicated"],
        start_date=refresh_start,
        end_date=refresh_end,
        dates=date_list,
    )


@router.get("/precompute/health", response_model=PrecomputeHealthResponse)
async def precompute_health(request: Request) -> PrecomputeHealthResponse | JSONResponse:
    """Health check for precompute freshness (for monitoring)."""
    secrets_mgr = get_secrets_manager()
    secret = secrets_mgr.get("PRECOMPUTE_MONITOR_SECRET")
    header_secret = request.headers.get("X-Precompute-Monitor-Secret")
    if not secret or not header_secret or not hmac.compare_digest(header_secret, secret):
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
        latest_source_metric_date=status.latest_source_metric_date,
        serving_metric_dates=status.serving_metric_dates,
        serving_lag_days=status.serving_lag_days,
        max_date_drift_days=status.max_date_drift_days,
        date_parity_ok=status.date_parity_ok,
    )

    if not status.ok:
        return JSONResponse(status_code=503, content=response.model_dump())

    return response
