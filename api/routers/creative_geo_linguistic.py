"""Geo-linguistic mismatch analysis endpoints for creatives."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.dependencies import get_current_user, get_store, require_buyer_access
from services.auth_service import User
from services.geo_linguistic_service import GeoLinguisticService

router = APIRouter(tags=["Creatives"])
geo_linguistic_service = GeoLinguisticService()


class GeoLinguisticFinding(BaseModel):
    category: str
    severity: str
    description: str
    evidence: str = ""


class EvidenceSummary(BaseModel):
    text_length: int = 0
    image_count: int = 0
    ocr_texts_count: int = 0
    video_frames_count: int = 0
    has_screenshot: bool = False
    currencies_detected: list[str] = []
    cta_phrases: list[str] = []


class GeoLinguisticReportResponse(BaseModel):
    status: str
    run_id: Optional[str] = None
    creative_id: str
    decision: str = "unknown"
    risk_score: float = 0.0
    confidence: float = 0.0
    primary_languages: list[str] = []
    secondary_languages: list[str] = []
    detected_currencies: list[str] = []
    findings: list[GeoLinguisticFinding] = []
    serving_countries: list[str] = []
    evidence_summary: Optional[EvidenceSummary] = None
    evidence: list[dict[str, Any]] = []
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: Optional[str] = None


@router.post(
    "/creatives/{creative_id}/analyze-geo-linguistic",
    response_model=GeoLinguisticReportResponse,
)
async def analyze_geo_linguistic(
    creative_id: str,
    force: bool = Query(False, description="Force re-analysis even if recent analysis exists"),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Trigger geo-linguistic mismatch analysis for a creative."""
    creative = await store.get_creative(creative_id)
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")

    if creative.buyer_id:
        await require_buyer_access(creative.buyer_id, store=store, user=user)

    result = await geo_linguistic_service.analyze_creative(
        creative_id=creative_id,
        store=store,
        force=force,
        triggered_by=user.email,
    )

    return GeoLinguisticReportResponse(creative_id=creative_id, **result)


@router.get(
    "/creatives/{creative_id}/geo-linguistic-report",
    response_model=GeoLinguisticReportResponse,
)
async def get_geo_linguistic_report(
    creative_id: str,
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Get the latest geo-linguistic analysis report for a creative."""
    creative = await store.get_creative(creative_id)
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")

    if creative.buyer_id:
        await require_buyer_access(creative.buyer_id, store=store, user=user)

    report = await geo_linguistic_service.get_report(creative_id)
    if not report:
        raise HTTPException(
            status_code=404,
            detail="No geo-linguistic analysis found for this creative",
        )

    return GeoLinguisticReportResponse(**report)
