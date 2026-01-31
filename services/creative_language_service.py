"""Creative language detection and geo-mismatch helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException

from services.creative_performance_service import CreativePerformanceService


class CreativeLanguageService:
    """Language detection + geo-mismatch logic for creatives."""

    def _build_language_response(self, creative: Any, success: bool) -> dict[str, Any]:
        return {
            "creative_id": creative.id,
            "detected_language": creative.detected_language,
            "detected_language_code": creative.detected_language_code,
            "language_confidence": creative.language_confidence,
            "language_source": creative.language_source,
            "language_analyzed_at": (
                creative.language_analyzed_at.isoformat()
                if creative.language_analyzed_at
                else None
            ),
            "language_analysis_error": creative.language_analysis_error,
            "success": success,
        }

    async def analyze_language(self, creative: Any, store: Any, force: bool) -> dict[str, Any]:
        """Run language detection for a creative and persist results."""
        if not force and creative.language_analyzed_at:
            return self._build_language_response(
                creative,
                success=creative.detected_language is not None,
            )

        try:
            from api.analysis.language_analyzer import GeminiLanguageAnalyzer
        except ImportError as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Language analyzer not available: {exc}",
            ) from exc

        db_path = getattr(store, "db_path", None)
        analyzer = GeminiLanguageAnalyzer(db_path=db_path)

        if not analyzer.is_configured:
            await store.creative_repository.update_language_detection(
                creative_id=creative.id,
                detected_language=None,
                detected_language_code=None,
                language_confidence=None,
                language_source="gemini",
                language_analysis_error="Gemini API key not configured",
            )
            raise HTTPException(
                status_code=503,
                detail="Gemini API key not configured. Set it in Settings > Connected Accounts.",
            )

        result = await analyzer.analyze_creative(
            creative_id=creative.id,
            raw_data=creative.raw_data,
            creative_format=creative.format,
        )

        await store.creative_repository.update_language_detection(
            creative_id=creative.id,
            detected_language=result.language,
            detected_language_code=result.language_code,
            language_confidence=result.confidence,
            language_source=result.source,
            language_analysis_error=result.error,
        )

        return {
            "creative_id": creative.id,
            "detected_language": result.language,
            "detected_language_code": result.language_code,
            "language_confidence": result.confidence,
            "language_source": result.source,
            "language_analyzed_at": datetime.now().isoformat(),
            "language_analysis_error": result.error,
            "success": result.success,
        }

    async def update_manual_language(
        self, creative: Any, update: Any, store: Any
    ) -> dict[str, Any]:
        """Persist a manual language update for a creative."""
        language_code = update.detected_language_code.lower()
        await store.creative_repository.update_language_detection(
            creative_id=creative.id,
            detected_language=update.detected_language,
            detected_language_code=language_code,
            language_confidence=1.0,
            language_source="manual",
            language_analysis_error=None,
        )
        return {
            "creative_id": creative.id,
            "detected_language": update.detected_language,
            "detected_language_code": language_code,
            "language_confidence": 1.0,
            "language_source": "manual",
            "language_analyzed_at": datetime.now().isoformat(),
            "language_analysis_error": None,
            "success": True,
        }

    async def get_geo_mismatch(self, creative: Any, days: int) -> dict[str, Any]:
        """Check for language/country mismatch for a creative."""
        if not creative.detected_language_code:
            return {
                "has_mismatch": False,
                "alert": None,
                "serving_countries": [],
            }

        service = CreativePerformanceService()
        country_breakdown = await service.get_country_breakdown(creative.id, days)
        if not country_breakdown:
            return {
                "has_mismatch": False,
                "alert": None,
                "serving_countries": [],
            }

        serving_countries = [
            c["country_code"] for c in country_breakdown if c.get("country_code")
        ]

        from utils.language_country_map import get_mismatch_alert

        alert_data = get_mismatch_alert(
            language_code=creative.detected_language_code,
            language_name=creative.detected_language
            or creative.detected_language_code,
            serving_countries=serving_countries,
        )

        if alert_data:
            return {
                "has_mismatch": True,
                "alert": alert_data,
                "serving_countries": serving_countries,
            }

        return {
            "has_mismatch": False,
            "alert": None,
            "serving_countries": serving_countries,
        }
