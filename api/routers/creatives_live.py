"""Live creative fetch router.

Keeps live-fetch and cache-fallback logic separate from the core creatives router.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.dependencies import get_store, get_current_user, get_config, require_buyer_access
from config import ConfigManager
from services.auth_service import User
from services.creative_cache_service import CreativeCacheService
from services.creatives_service import CreativesService
from storage.adapters import creative_dict_to_storage

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Creatives"])
creatives_service = CreativesService()


class VideoPreview(BaseModel):
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    vast_xml: Optional[str] = None
    duration: Optional[str] = None


class HtmlPreview(BaseModel):
    snippet: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    thumbnail_url: Optional[str] = None


class ImagePreview(BaseModel):
    url: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


class NativePreview(BaseModel):
    headline: Optional[str] = None
    body: Optional[str] = None
    call_to_action: Optional[str] = None
    click_link_url: Optional[str] = None
    image: Optional[ImagePreview] = None
    logo: Optional[ImagePreview] = None


class ThumbnailStatusResponse(BaseModel):
    status: Optional[str] = None
    error_reason: Optional[str] = None
    has_thumbnail: bool = False
    thumbnail_url: Optional[str] = None


class WasteFlagsResponse(BaseModel):
    broken_video: bool = False
    zero_engagement: bool = False


class CreativeResponse(BaseModel):
    id: str
    name: str
    format: str
    account_id: Optional[str] = None
    buyer_id: Optional[str] = None
    approval_status: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    final_url: Optional[str] = None
    display_url: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None
    advertiser_name: Optional[str] = None
    campaign_id: Optional[str] = None
    cluster_id: Optional[str] = None
    seat_name: Optional[str] = None
    country: Optional[str] = None
    video: Optional[VideoPreview] = None
    html: Optional[HtmlPreview] = None
    native: Optional[NativePreview] = None
    thumbnail_status: Optional[ThumbnailStatusResponse] = None
    waste_flags: Optional[WasteFlagsResponse] = None
    app_id: Optional[str] = None
    app_name: Optional[str] = None
    app_store: Optional[str] = None
    is_disapproved: bool = False
    disapproval_reasons: Optional[list] = None
    serving_restrictions: Optional[list] = None
    detected_language: Optional[str] = None
    detected_language_code: Optional[str] = None
    language_confidence: Optional[float] = None
    language_source: Optional[str] = None
    language_analyzed_at: Optional[str] = None
    language_analysis_error: Optional[str] = None


class CreativeLiveResponse(BaseModel):
    creative: CreativeResponse
    source: str
    fetched_at: str
    message: Optional[str] = None


def _convert_thumbnail_status(ts) -> ThumbnailStatusResponse:
    return ThumbnailStatusResponse(
        status=ts.status,
        error_reason=ts.error_reason,
        has_thumbnail=ts.has_thumbnail,
        thumbnail_url=ts.thumbnail_url,
    )


def _convert_waste_flags(wf) -> WasteFlagsResponse:
    return WasteFlagsResponse(
        broken_video=wf.broken_video,
        zero_engagement=wf.zero_engagement,
    )


def _build_creative_response(creative, ctx: Any, creative_id: str, seat_name: Optional[str]) -> CreativeResponse:
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
        utm_source=creative.utm_source,
        utm_medium=creative.utm_medium,
        utm_campaign=creative.utm_campaign,
        utm_content=creative.utm_content,
        utm_term=creative.utm_term,
        advertiser_name=creative.advertiser_name,
        campaign_id=creative.campaign_id,
        cluster_id=creative.cluster_id,
        seat_name=seat_name,
        thumbnail_status=_convert_thumbnail_status(ctx.thumbnail_statuses[creative_id]) if creative_id in ctx.thumbnail_statuses else None,
        waste_flags=_convert_waste_flags(ctx.waste_flags[creative_id]) if creative_id in ctx.waste_flags else None,
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
        **creatives_service.build_preview(
            creative,
            slim=False,
            html_thumbnail_url=ctx.thumbnail_statuses[creative_id].thumbnail_url if creative_id in ctx.thumbnail_statuses else None,
        ),
    )


@router.get("/creatives/{creative_id}/live", response_model=CreativeLiveResponse)
async def get_creative_live(
    creative_id: str,
    days: int = Query(7, ge=1, le=365, description="Timeframe for waste detection"),
    allow_cache_fallback: bool = Query(
        True,
        description="Return cached DB creative when live fetch fails",
    ),
    refresh_cache: bool = Query(
        True,
        description="Persist live creative payload to cache on success",
    ),
    store=Depends(get_store),
    config: ConfigManager = Depends(get_config),
    user: User = Depends(get_current_user),
):
    creative = await store.get_creative(creative_id)
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")
    if creative.buyer_id:
        await require_buyer_access(creative.buyer_id, store=store, user=user)

    ctx = await creatives_service.get_list_context(store, [creative_id], days)
    cache_service = CreativeCacheService(store=store, config=config)

    try:
        client = await cache_service.resolve_live_client(creative)
        live_dict = await client.get_creative_by_id(
            creative_id=creative_id,
            view="FULL",
            buyer_id=creative.buyer_id,
        )
        if not live_dict:
            raise HTTPException(status_code=404, detail="Creative not found in live API")

        live_creative = creative_dict_to_storage(live_dict)
        live_creative.campaign_id = creative.campaign_id
        live_creative.cluster_id = creative.cluster_id
        live_creative.detected_language = creative.detected_language
        live_creative.detected_language_code = creative.detected_language_code
        live_creative.language_confidence = creative.language_confidence
        live_creative.language_source = creative.language_source
        live_creative.language_analyzed_at = creative.language_analyzed_at
        live_creative.language_analysis_error = creative.language_analysis_error

        if refresh_cache:
            await store.save_creatives([live_creative])

        return CreativeLiveResponse(
            creative=_build_creative_response(live_creative, ctx, creative_id, creative.seat_name),
            source="live",
            fetched_at=datetime.utcnow().isoformat(),
        )
    except HTTPException:
        if not allow_cache_fallback:
            raise
        return CreativeLiveResponse(
            creative=_build_creative_response(creative, ctx, creative_id, creative.seat_name),
            source="cache",
            fetched_at=datetime.utcnow().isoformat(),
            message="Live fetch failed; showing cached snapshot.",
        )
    except Exception as e:
        logger.error(f"Live creative fetch failed for {creative_id}: {e}")
        if not allow_cache_fallback:
            raise HTTPException(status_code=500, detail="Live creative fetch failed")
        return CreativeLiveResponse(
            creative=_build_creative_response(creative, ctx, creative_id, creative.seat_name),
            source="cache",
            fetched_at=datetime.utcnow().isoformat(),
            message="Live fetch failed; showing cached snapshot.",
        )
