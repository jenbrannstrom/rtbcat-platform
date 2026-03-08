"""Geo-linguistic mismatch analysis pipeline orchestrator.

Coordinates evidence collection, LLM analysis, and result persistence
for creative geo-language mismatch detection.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from services.creative_countries_service import CreativeCountriesService
from services.creative_evidence_service import CreativeEvidenceService
from services.config_service import ConfigService
from services.language_ai_config import get_selected_language_ai_provider
from storage.postgres_repositories.creative_analysis_repo import CreativeAnalysisRepository

logger = logging.getLogger(__name__)


class GeoLinguisticService:
    """Pipeline orchestrator for geo-linguistic mismatch analysis."""

    def __init__(
        self,
        repo: Optional[CreativeAnalysisRepository] = None,
        countries_service: Optional[CreativeCountriesService] = None,
        evidence_service: Optional[CreativeEvidenceService] = None,
    ) -> None:
        self.repo = repo or CreativeAnalysisRepository()
        self.countries_service = countries_service or CreativeCountriesService()
        self.evidence_service = evidence_service or CreativeEvidenceService()

    async def analyze_creative(
        self,
        creative_id: str,
        store: Any,
        force: bool = False,
        triggered_by: Optional[str] = None,
        days: int = 7,
    ) -> dict[str, Any]:
        """Run the full geo-linguistic analysis pipeline for a creative.

        Steps:
          1. Check if we should skip (recent analysis exists)
          2. Create run record
          3. Fetch creative + serving countries
          4. Collect evidence
          5. Run provider-backed analysis
          6. Persist result + evidence refs
          7. Return response dict
        """
        # 1. Skip check
        if not force:
            should_skip = await self.repo.should_skip_analysis(creative_id)
            if should_skip:
                latest = await self.repo.get_latest_run(creative_id)
                if latest:
                    return self._format_run(latest)
                # Fall through if no run found

        # 2. Create run record
        run_id = str(uuid.uuid4())
        await self.repo.create_run(
            run_id=run_id,
            creative_id=creative_id,
            triggered_by=triggered_by,
            force_rerun=force,
        )

        try:
            # 3. Fetch creative
            creative = await store.get_creative(creative_id)
            if not creative:
                await self.repo.update_run_status(
                    run_id, "failed", error_message="Creative not found"
                )
                return {"status": "failed", "error_message": "Creative not found"}

            # Get serving countries
            country_breakdown = await self.countries_service.get_country_breakdown(
                creative_id, days
            )
            serving_countries = [
                c["country_code"]
                for c in country_breakdown
                if c.get("country_code")
            ]

            provider = await get_selected_language_ai_provider(store)
            api_key = await ConfigService().get_ai_provider_api_key(store, provider)

            # 4. Collect evidence
            raw_data = creative.raw_data if hasattr(creative, "raw_data") else {}
            creative_format = creative.format if hasattr(creative, "format") else "HTML"

            evidence = self.evidence_service.collect_evidence(
                creative_id=creative_id,
                raw_data=raw_data or {},
                creative_format=creative_format,
                ai_provider=provider,
                ai_api_key=api_key,
            )

            # 5. Run language/currency mismatch analysis with selected provider
            from api.analysis.geo_language_mismatch_analyzer import (
                GeoLinguisticAnalyzer,
            )

            analyzer = GeoLinguisticAnalyzer(provider=provider, api_key=api_key)
            if not analyzer.is_configured:
                await self.repo.update_run_status(
                    run_id,
                    "failed",
                    error_message=f"{provider.capitalize()} API not configured",
                )
                return {
                    "status": "failed",
                    "error_message": f"{provider.capitalize()} API not configured",
                }

            # Combine image paths for multimodal analysis
            image_paths = evidence.video_frames[:]
            if evidence.screenshot_path:
                image_paths.insert(0, evidence.screenshot_path)

            advertiser_name = ""
            if hasattr(creative, "raw_data") and creative.raw_data:
                advertiser_name = creative.raw_data.get("advertiserName", "")

            analysis_result = analyzer.analyze(
                serving_countries=serving_countries,
                text_content=evidence.text_content,
                ocr_texts=evidence.ocr_texts,
                image_paths=image_paths if image_paths else None,
                creative_metadata={
                    "format": creative_format,
                    "advertiser_name": advertiser_name,
                },
            )

            # 6. Persist result + evidence refs
            result_dict = analysis_result.to_dict()
            result_dict["provider"] = provider
            result_dict["serving_countries"] = serving_countries
            result_dict["evidence_summary"] = {
                "text_length": len(evidence.text_content),
                "image_count": len(evidence.image_urls),
                "ocr_texts_count": len(evidence.ocr_texts),
                "video_frames_count": len(evidence.video_frames),
                "has_screenshot": evidence.screenshot_path is not None,
                "currencies_detected": evidence.currencies,
                "cta_phrases": evidence.cta_phrases,
            }

            status = "completed" if analysis_result.success else "failed"
            await self.repo.update_run_status(
                run_id=run_id,
                status=status,
                result=result_dict,
                error_message=analysis_result.error,
            )

            # Store evidence references
            if evidence.screenshot_path:
                await self.repo.add_evidence(
                    evidence_id=str(uuid.uuid4()),
                    run_id=run_id,
                    evidence_type="screenshot",
                    file_path=evidence.screenshot_path,
                )
            for frame_path in evidence.video_frames:
                await self.repo.add_evidence(
                    evidence_id=str(uuid.uuid4()),
                    run_id=run_id,
                    evidence_type="video_frame",
                    file_path=frame_path,
                )

            # 7. Return response
            return {
                "status": status,
                "run_id": run_id,
                "creative_id": creative_id,
                **result_dict,
            }

        except Exception as e:
            logger.exception("Geo-linguistic analysis failed for %s", creative_id)
            await self.repo.update_run_status(
                run_id, "failed", error_message=str(e)
            )
            return {"status": "failed", "error_message": str(e)}

    async def get_report(self, creative_id: str) -> Optional[dict[str, Any]]:
        """Get the latest completed analysis report for a creative."""
        run = await self.repo.get_latest_run(creative_id)
        if not run:
            return None

        result = self._format_run(run)

        # Attach evidence
        evidence = await self.repo.get_evidence_for_run(run["id"])
        result["evidence"] = evidence

        return result

    def _format_run(self, run: dict[str, Any]) -> dict[str, Any]:
        """Format a run record into a response dict."""
        result_data = run.get("result") or {}
        return {
            "status": run["status"],
            "run_id": run["id"],
            "creative_id": run["creative_id"],
            "decision": result_data.get("decision", "unknown"),
            "risk_score": result_data.get("risk_score", 0.0),
            "confidence": result_data.get("confidence", 0.0),
            "primary_languages": result_data.get("primary_languages", []),
            "secondary_languages": result_data.get("secondary_languages", []),
            "detected_currencies": result_data.get("detected_currencies", []),
            "findings": result_data.get("findings", []),
            "serving_countries": result_data.get("serving_countries", []),
            "evidence_summary": result_data.get("evidence_summary"),
            "error_message": run.get("error_message"),
            "started_at": run.get("started_at"),
            "completed_at": run.get("completed_at"),
            "created_at": run.get("created_at"),
        }
