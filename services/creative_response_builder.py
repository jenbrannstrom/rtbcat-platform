"""Helpers to build API creative responses consistently across routers."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from api.schemas.creatives import (
    CreativeDataSource,
    CreativeResponse,
)
from api.schemas.common import ThumbnailStatusResponse, WasteFlagsResponse
from services.creative_destination_resolver import resolve_creative_destination_url
from services.creatives_service import CreativesService

logger = logging.getLogger(__name__)


def _to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso(dt: Optional[datetime]) -> Optional[str]:
    value = _to_utc(dt)
    return value.isoformat() if value else None


def get_stale_threshold_hours() -> int:
    raw = os.getenv("CREATIVE_CACHE_STALE_HOURS", "24").strip()
    try:
        value = int(raw)
    except Exception:
        logger.warning(
            "Invalid CREATIVE_CACHE_STALE_HOURS value; using default",
            extra={"env_var": "CREATIVE_CACHE_STALE_HOURS"},
            exc_info=True,
        )
        return 24
    return max(1, value)


def build_data_source(
    source: str,
    cached_at: Optional[datetime],
    fetched_at: Optional[datetime] = None,
    fallback_reason: Optional[str] = None,
    stale_threshold_hours: Optional[int] = None,
) -> CreativeDataSource:
    threshold_hours = stale_threshold_hours or get_stale_threshold_hours()
    cached_utc = _to_utc(cached_at)
    fetched_utc = _to_utc(fetched_at)

    stale_age_hours: Optional[float] = None
    is_stale = False
    if cached_utc is not None:
        age = datetime.now(timezone.utc) - cached_utc
        stale_age_hours = round(age.total_seconds() / 3600, 2)
        is_stale = stale_age_hours > threshold_hours

    return CreativeDataSource(
        source=source,
        cached_at=_iso(cached_at),
        fetched_at=_iso(fetched_at),
        stale_threshold_hours=threshold_hours,
        stale_age_hours=stale_age_hours,
        is_stale=is_stale if source == "cache" else False,
        fallback_reason=fallback_reason,
    )


def convert_thumbnail_status(ts: Any) -> ThumbnailStatusResponse:
    return ThumbnailStatusResponse(
        status=ts.status,
        error_reason=ts.error_reason,
        has_thumbnail=ts.has_thumbnail,
        thumbnail_url=ts.thumbnail_url,
    )


def convert_waste_flags(wf: Any) -> WasteFlagsResponse:
    return WasteFlagsResponse(
        broken_video=wf.broken_video,
        zero_engagement=wf.zero_engagement,
    )


def build_creative_response(
    creative: Any,
    ctx: Any,
    creative_id: str,
    creatives_service: CreativesService,
    *,
    slim: bool,
    seat_name_override: Optional[str] = None,
    source: str = "cache",
    fetched_at: Optional[datetime] = None,
    fallback_reason: Optional[str] = None,
) -> CreativeResponse:
    thumbnail_status = (
        convert_thumbnail_status(ctx.thumbnail_statuses[creative_id])
        if creative_id in ctx.thumbnail_statuses
        else None
    )
    waste_flags = (
        convert_waste_flags(ctx.waste_flags[creative_id])
        if creative_id in ctx.waste_flags
        else None
    )
    html_thumbnail_url = (
        ctx.thumbnail_statuses[creative_id].thumbnail_url
        if creative_id in ctx.thumbnail_statuses
        else None
    )

    return CreativeResponse(
        id=creative.id,
        name=creative.name,
        format=creative.format,
        account_id=creative.account_id,
        buyer_id=creative.buyer_id,
        approval_status=creative.approval_status,
        width=creative.width,
        height=creative.height,
        final_url=creative.final_url,
        display_url=creative.display_url,
        resolved_destination_url=resolve_creative_destination_url(creative),
        utm_source=creative.utm_source,
        utm_medium=creative.utm_medium,
        utm_campaign=creative.utm_campaign,
        utm_content=creative.utm_content,
        utm_term=creative.utm_term,
        advertiser_name=creative.advertiser_name,
        campaign_id=creative.campaign_id,
        cluster_id=creative.cluster_id,
        seat_name=seat_name_override or creative.seat_name,
        country=ctx.country_data.get(creative_id),
        thumbnail_status=thumbnail_status,
        waste_flags=waste_flags,
        app_id=creative.app_id,
        app_name=creative.app_name,
        app_store=creative.app_store,
        is_disapproved=creative.approval_status == "DISAPPROVED",
        disapproval_reasons=creative.disapproval_reasons,
        serving_restrictions=creative.serving_restrictions,
        detected_language=creative.detected_language,
        detected_language_code=creative.detected_language_code,
        language_confidence=creative.language_confidence,
        language_source=creative.language_source,
        language_analyzed_at=creative.language_analyzed_at.isoformat() if creative.language_analyzed_at else None,
        language_analysis_error=creative.language_analysis_error,
        data_source=build_data_source(
            source=source,
            cached_at=creative.updated_at,
            fetched_at=fetched_at,
            fallback_reason=fallback_reason,
        ),
        **creatives_service.build_preview(
            creative,
            slim=slim,
            html_thumbnail_url=html_thumbnail_url,
        ),
    )
