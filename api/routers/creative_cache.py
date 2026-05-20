"""Creative cache maintenance endpoints (scheduler-safe)."""

from __future__ import annotations

from datetime import datetime, timezone
import hmac

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, Query
from pydantic import BaseModel

from api.dependencies import get_store, get_config
from config import ConfigManager
from services.creative_cache_service import CreativeCacheService
from services.secrets_manager import get_secrets_manager

router = APIRouter(tags=["Creatives"])


class CreativeCacheRefreshResponse(BaseModel):
    success: bool
    started_at: str
    days: int
    limit: int
    include_html_thumbnails: bool
    result: dict


@router.post("/creatives/cache/refresh/scheduled", response_model=CreativeCacheRefreshResponse)
async def refresh_creative_cache_scheduled(
    request: Request,
    background_tasks: BackgroundTasks,
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(500, ge=1, le=5000),
    include_html_thumbnails: bool = Query(True),
    force_html_thumbnail_retry: bool = Query(False),
    background: bool = Query(False, description="Queue the refresh and return immediately"),
    store=Depends(get_store),
    config: ConfigManager = Depends(get_config),
) -> CreativeCacheRefreshResponse:
    """Refresh live creative cache for active creatives during off-hours."""
    secret = get_secrets_manager().get("CREATIVE_CACHE_REFRESH_SECRET")
    header_secret = request.headers.get("X-Creative-Cache-Refresh-Secret")
    if not secret or not header_secret or not hmac.compare_digest(header_secret, secret):
        raise HTTPException(status_code=403, detail="Invalid scheduler secret")

    svc = CreativeCacheService(store=store, config=config)
    if background:
        background_tasks.add_task(
            svc.refresh_active_creatives,
            days=days,
            limit=limit,
            include_html_thumbnails=include_html_thumbnails,
            force_html_thumbnail_retry=force_html_thumbnail_retry,
        )
        result = {
            "queued": True,
            "scanned": 0,
            "refreshed": 0,
            "failed": 0,
            "skipped": 0,
        }
    else:
        refresh_result = await svc.refresh_active_creatives(
            days=days,
            limit=limit,
            include_html_thumbnails=include_html_thumbnails,
            force_html_thumbnail_retry=force_html_thumbnail_retry,
        )
        result = refresh_result.to_dict()

    return CreativeCacheRefreshResponse(
        success=True,
        started_at=datetime.now(timezone.utc).isoformat(),
        days=days,
        limit=limit,
        include_html_thumbnails=include_html_thumbnails,
        result=result,
    )
