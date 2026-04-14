"""Language detection endpoints for creatives."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from api.dependencies import get_store, get_current_user, require_buyer_access
from services.auth_service import User
from services.creative_language_service import CreativeLanguageService

router = APIRouter(tags=["Creatives"])
language_service = CreativeLanguageService()


class LanguageDetectionResponse(BaseModel):
    """Response model for language detection."""
    creative_id: str
    detected_language: Optional[str] = None
    detected_language_code: Optional[str] = None
    language_confidence: Optional[float] = None
    language_source: Optional[str] = None
    language_analyzed_at: Optional[str] = None
    language_analysis_error: Optional[str] = None
    success: bool = False


class GeoMismatchAlert(BaseModel):
    """Response model for geo-language mismatch alert."""
    severity: str
    category: str = "language"
    language: Optional[str] = None
    language_code: Optional[str] = None
    mismatched_countries: list[str] = Field(default_factory=list)
    expected_countries: list[str] = Field(default_factory=list)
    message: str


class GeoMismatchResponse(BaseModel):
    """Response for geo-mismatch check."""
    creative_id: str
    has_mismatch: bool
    alert: Optional[GeoMismatchAlert] = None
    serving_countries: list[str] = Field(default_factory=list)
    detected_currencies: list[str] = Field(default_factory=list)
    language_flag_status: str = "orange"
    language_flag_reason: Optional[str] = None
    language_flag_source: Optional[str] = None
    effective_language_code: Optional[str] = None
    heuristic_language_code: Optional[str] = None
    currency_flag_status: str = "orange"
    currency_flag_reason: Optional[str] = None
    geo_linguistic_status: str = "orange"
    geo_linguistic_reason: Optional[str] = None
    geo_linguistic_decision: Optional[str] = None
    geo_linguistic_completed_at: Optional[str] = None


class ManualLanguageUpdate(BaseModel):
    """Request model for manual language update."""
    detected_language: str = Field(..., min_length=1, description="Language name (e.g., 'German')")
    detected_language_code: str = Field(..., min_length=2, max_length=3, description="ISO 639-1 code (e.g., 'de')")


@router.post("/creatives/{creative_id}/analyze-language", response_model=LanguageDetectionResponse)
async def analyze_creative_language(
    creative_id: str,
    force: bool = Query(False, description="Force re-analysis even if already analyzed"),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
) -> LanguageDetectionResponse:
    """Analyze a creative's content to detect its language."""
    creative = await store.get_creative(creative_id)
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")
    if creative.buyer_id:
        await require_buyer_access(creative.buyer_id, store=store, user=user)

    response = await language_service.analyze_language(
        creative=creative,
        store=store,
        force=force,
    )
    return LanguageDetectionResponse(**response)


@router.put("/creatives/{creative_id}/language", response_model=LanguageDetectionResponse)
async def update_creative_language(
    creative_id: str,
    update: ManualLanguageUpdate,
    store=Depends(get_store),
    user: User = Depends(get_current_user),
) -> LanguageDetectionResponse:
    """Manually update a creative's detected language."""
    creative = await store.get_creative(creative_id)
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")
    if creative.buyer_id:
        await require_buyer_access(creative.buyer_id, store=store, user=user)

    response = await language_service.update_manual_language(
        creative=creative,
        update=update,
        store=store,
    )
    return LanguageDetectionResponse(**response)


@router.get("/creatives/{creative_id}/geo-mismatch", response_model=GeoMismatchResponse)
async def get_creative_geo_mismatch(
    creative_id: str,
    days: int = Query(7, ge=1, le=90, description="Days to look back for serving data"),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
) -> GeoMismatchResponse:
    """Check if a creative's language matches its serving countries."""
    creative = await store.get_creative(creative_id)
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")
    if creative.buyer_id:
        await require_buyer_access(creative.buyer_id, store=store, user=user)

    mismatch = await language_service.get_geo_mismatch(
        creative=creative,
        days=days,
    )

    if mismatch["alert"]:
        return GeoMismatchResponse(
            creative_id=creative_id,
            has_mismatch=mismatch["has_mismatch"],
            alert=GeoMismatchAlert(**mismatch["alert"]),
            serving_countries=mismatch["serving_countries"],
            detected_currencies=mismatch.get("detected_currencies", []),
            language_flag_status=mismatch.get("language_flag_status", "orange"),
            language_flag_reason=mismatch.get("language_flag_reason"),
            language_flag_source=mismatch.get("language_flag_source"),
            effective_language_code=mismatch.get("effective_language_code"),
            heuristic_language_code=mismatch.get("heuristic_language_code"),
            currency_flag_status=mismatch.get("currency_flag_status", "orange"),
            currency_flag_reason=mismatch.get("currency_flag_reason"),
            geo_linguistic_status=mismatch.get("geo_linguistic_status", "orange"),
            geo_linguistic_reason=mismatch.get("geo_linguistic_reason"),
            geo_linguistic_decision=mismatch.get("geo_linguistic_decision"),
            geo_linguistic_completed_at=mismatch.get("geo_linguistic_completed_at"),
        )

    return GeoMismatchResponse(
        creative_id=creative_id,
        has_mismatch=mismatch["has_mismatch"],
        alert=None,
        serving_countries=mismatch["serving_countries"],
        detected_currencies=mismatch.get("detected_currencies", []),
        language_flag_status=mismatch.get("language_flag_status", "orange"),
        language_flag_reason=mismatch.get("language_flag_reason"),
        language_flag_source=mismatch.get("language_flag_source"),
        effective_language_code=mismatch.get("effective_language_code"),
        heuristic_language_code=mismatch.get("heuristic_language_code"),
        currency_flag_status=mismatch.get("currency_flag_status", "orange"),
        currency_flag_reason=mismatch.get("currency_flag_reason"),
        geo_linguistic_status=mismatch.get("geo_linguistic_status", "orange"),
        geo_linguistic_reason=mismatch.get("geo_linguistic_reason"),
        geo_linguistic_decision=mismatch.get("geo_linguistic_decision"),
        geo_linguistic_completed_at=mismatch.get("geo_linguistic_completed_at"),
    )
