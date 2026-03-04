"""Live creative fetch router."""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_config, get_current_user, get_store, require_buyer_access
from api.schemas.creatives import CreativeLiveResponse
from config import ConfigManager
from services.auth_service import User
from services.creative_cache_service import CreativeCacheService
from services.creative_live_fetch_telemetry_service import CreativeLiveFetchTelemetryService
from services.creative_response_builder import build_creative_response
from services.creatives_service import CreativesService
from storage.adapters import creative_dict_to_storage

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Creatives"])
creatives_service = CreativesService()
telemetry_service = CreativeLiveFetchTelemetryService()


def _error_type_from_exception(exc: Exception) -> str:
    if isinstance(exc, HTTPException):
        if exc.status_code == 404:
            return "not_found"
        if exc.status_code == 403:
            return "forbidden"
        return f"http_{exc.status_code}"
    return "exception"


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
) -> CreativeLiveResponse:
    creative = await store.get_creative(creative_id)
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")
    if creative.buyer_id:
        await require_buyer_access(creative.buyer_id, store=store, user=user)

    ctx = await creatives_service.get_list_context(store, [creative_id], days)
    cache_service = CreativeCacheService(store=store, config=config)
    now = datetime.utcnow()

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
            creative=build_creative_response(
                live_creative,
                ctx,
                creative_id,
                creatives_service,
                slim=False,
                seat_name_override=creative.seat_name,
                source="live",
                fetched_at=now,
            ),
            source="live",
            fetched_at=now.isoformat(),
        )
    except HTTPException as exc:
        if not allow_cache_fallback:
            raise
        error_type = _error_type_from_exception(exc)
        try:
            await telemetry_service.record_fallback(
                creative_id=creative_id,
                buyer_id=creative.buyer_id,
                error_type=error_type,
                error_message=exc.detail if isinstance(exc.detail, str) else str(exc.detail),
            )
        except Exception as telemetry_error:
            logger.warning("Failed to record live fetch fallback telemetry: %s", telemetry_error)
        return CreativeLiveResponse(
            creative=build_creative_response(
                creative,
                ctx,
                creative_id,
                creatives_service,
                slim=False,
                seat_name_override=creative.seat_name,
                source="cache",
                fetched_at=now,
                fallback_reason=error_type,
            ),
            source="cache",
            fetched_at=now.isoformat(),
            message="Live fetch failed; showing cached snapshot.",
        )
    except Exception as e:
        logger.error(f"Live creative fetch failed for {creative_id}: {e}")
        if not allow_cache_fallback:
            raise HTTPException(status_code=500, detail="Live creative fetch failed")
        try:
            await telemetry_service.record_fallback(
                creative_id=creative_id,
                buyer_id=creative.buyer_id,
                error_type="exception",
                error_message=str(e)[:500],
            )
        except Exception as telemetry_error:
            logger.warning("Failed to record live fetch fallback telemetry: %s", telemetry_error)
        return CreativeLiveResponse(
            creative=build_creative_response(
                creative,
                ctx,
                creative_id,
                creatives_service,
                slim=False,
                seat_name_override=creative.seat_name,
                source="cache",
                fetched_at=now,
                fallback_reason="exception",
            ),
            source="cache",
            fetched_at=now.isoformat(),
            message="Live fetch failed; showing cached snapshot.",
        )
