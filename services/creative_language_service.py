"""Creative language detection and geo-mismatch helpers."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import HTTPException

from config import ConfigManager
from services.creative_cache_service import CreativeCacheService
from services.creative_language_flag_service import build_creative_language_flag_row
from services.config_service import ConfigService
from services.creative_countries_service import CreativeCountriesService
from services.language_ai_config import get_selected_language_ai_provider
from storage.adapters import creative_dict_to_storage
from storage.postgres_repositories.creative_analysis_repo import CreativeAnalysisRepository

logger = logging.getLogger(__name__)


class CreativeLanguageService:
    """Language detection + geo-mismatch logic for creatives."""

    def __init__(
        self,
        analysis_repo: CreativeAnalysisRepository | None = None,
    ) -> None:
        self._analysis_repo = analysis_repo or CreativeAnalysisRepository()

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

    @staticmethod
    def _serialize_timestamp(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

    async def _refresh_live_creative_for_analysis(self, creative: Any, store: Any) -> Any:
        """Best-effort live refresh so language analysis sees the rendered Google payload."""
        if not getattr(creative, "buyer_id", None):
            return creative

        try:
            cache_service = CreativeCacheService(store=store, config=ConfigManager())
            client = await cache_service.resolve_live_client(creative)
            live_dict = await client.get_creative_by_id(
                creative_id=creative.id,
                view="FULL",
                buyer_id=creative.buyer_id,
            )
            if not live_dict:
                return creative

            live_creative = creative_dict_to_storage(live_dict)
            live_creative.campaign_id = getattr(creative, "campaign_id", None)
            live_creative.cluster_id = getattr(creative, "cluster_id", None)
            live_creative.seat_name = getattr(creative, "seat_name", None)
            live_creative.detected_language = getattr(creative, "detected_language", None)
            live_creative.detected_language_code = getattr(creative, "detected_language_code", None)
            live_creative.language_confidence = getattr(creative, "language_confidence", None)
            live_creative.language_source = getattr(creative, "language_source", None)
            live_creative.language_analyzed_at = getattr(creative, "language_analyzed_at", None)
            live_creative.language_analysis_error = getattr(creative, "language_analysis_error", None)

            if hasattr(store, "save_creatives"):
                await store.save_creatives([live_creative])
            return live_creative
        except Exception as exc:
            logger.warning(
                "Live creative refresh failed before language analysis for %s: %s",
                getattr(creative, "id", "unknown"),
                exc,
            )
            return creative

    async def analyze_language(self, creative: Any, store: Any, force: bool) -> dict[str, Any]:
        """Run language detection for a creative and persist results."""
        if not force and creative.language_analyzed_at:
            return self._build_language_response(
                creative,
                success=creative.detected_language is not None,
            )

        try:
            from api.analysis.language_analyzer import LanguageAnalyzer
        except ImportError as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Language analyzer not available: {exc}",
            ) from exc

        db_path = getattr(store, "db_path", None)
        provider = await get_selected_language_ai_provider(store)
        api_key = await ConfigService().get_ai_provider_api_key(store, provider)
        analyzer = LanguageAnalyzer(
            provider=provider,
            api_key=api_key,
            db_path=db_path,
        )

        if not analyzer.is_configured:
            await store.creative_repository.update_language_detection(
                creative_id=creative.id,
                detected_language=None,
                detected_language_code=None,
                language_confidence=None,
                language_source=provider,
                language_analysis_error=f"{provider.capitalize()} API key not configured",
            )
            raise HTTPException(
                status_code=503,
                detail=(
                    f"{provider.capitalize()} API key not configured. "
                    "Set it in Settings > Connected Accounts."
                ),
            )

        analysis_creative = await self._refresh_live_creative_for_analysis(creative, store)
        result = await analyzer.analyze_creative(
            creative_id=analysis_creative.id,
            raw_data=analysis_creative.raw_data,
            creative_format=analysis_creative.format,
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
        countries_service = CreativeCountriesService()
        country_breakdown = await countries_service.get_country_breakdown(creative.id, days)
        serving_countries = [
            c["country_code"] for c in country_breakdown if c.get("country_code")
        ]
        try:
            latest_geo_run = await self._analysis_repo.get_latest_run(creative.id)
        except Exception:
            latest_geo_run = None
        flag_row = build_creative_language_flag_row(
            creative=creative,
            serving_countries=serving_countries,
            latest_geo_run=latest_geo_run,
        )
        normalized_serving_countries = flag_row["serving_countries"]

        alert_data = None
        if flag_row["currency_flag_status"] == "red":
            alert_data = {
                "severity": "error",
                "category": "currency",
                "language": flag_row.get("detected_language"),
                "language_code": flag_row.get("effective_language_code"),
                "mismatched_countries": normalized_serving_countries,
                "expected_countries": [],
                "message": flag_row["currency_flag_reason"],
            }
        elif flag_row["language_flag_status"] in {"orange", "red"}:
            alert_data = {
                "severity": "warning" if flag_row["language_flag_status"] == "orange" else "error",
                "category": "language",
                "language": creative.detected_language or flag_row.get("effective_language_code"),
                "language_code": flag_row.get("effective_language_code"),
                "mismatched_countries": normalized_serving_countries,
                "expected_countries": [],
                "message": flag_row["language_flag_reason"],
            }

        return {
            "has_mismatch": (
                flag_row["language_flag_status"] == "red"
                or flag_row["currency_flag_status"] == "red"
                or flag_row["geo_linguistic_status"] == "red"
            ),
            "alert": alert_data,
            "serving_countries": normalized_serving_countries,
            "detected_currencies": flag_row["detected_currencies"],
            "language_flag_status": flag_row["language_flag_status"],
            "language_flag_reason": flag_row["language_flag_reason"],
            "language_flag_source": flag_row["language_flag_source"],
            "effective_language_code": flag_row.get("effective_language_code"),
            "heuristic_language_code": flag_row.get("heuristic_language_code"),
            "plaintext_language_summary": flag_row.get("plaintext_language_summary"),
            "primary_text_language": flag_row.get("primary_text_language"),
            "primary_text_language_code": flag_row.get("primary_text_language_code"),
            "secondary_text_language": flag_row.get("secondary_text_language"),
            "secondary_text_language_code": flag_row.get("secondary_text_language_code"),
            "secondary_text_sample": flag_row.get("secondary_text_sample"),
            "currency_flag_status": flag_row["currency_flag_status"],
            "currency_flag_reason": flag_row["currency_flag_reason"],
            "geo_linguistic_status": flag_row["geo_linguistic_status"],
            "geo_linguistic_reason": flag_row["geo_linguistic_reason"],
            "geo_linguistic_decision": flag_row.get("geo_linguistic_decision"),
            "geo_linguistic_completed_at": self._serialize_timestamp(
                flag_row.get("geo_linguistic_completed_at")
            ),
        }
