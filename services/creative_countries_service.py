"""Creative country breakdown helpers."""

from __future__ import annotations

from typing import Any

from services.creative_performance_service import CreativePerformanceService
from utils.country_codes import get_country_name, get_country_alpha3


class CreativeCountriesService:
    """Country breakdown formatting for creatives."""

    def __init__(self, perf_service: CreativePerformanceService | None = None) -> None:
        self._perf_service = perf_service or CreativePerformanceService()

    async def get_country_breakdown(
        self, creative_id: str, days: int
    ) -> list[dict[str, Any]]:
        """Get country breakdown with spend/impressions for a creative."""
        return await self._perf_service.get_country_breakdown(creative_id, days)

    async def build_country_metrics(
        self, creative_id: str, days: int
    ) -> dict[str, Any]:
        """Build response payload for creative country metrics."""
        breakdown = await self.get_country_breakdown(creative_id, days)
        total_spend = sum(c.get("spend_micros", 0) or 0 for c in breakdown)

        countries = [
            {
                "country_code": c["country_code"],
                "country_name": get_country_name(c["country_code"]),
                "country_iso3": get_country_alpha3(c["country_code"]),
                "spend_micros": c.get("spend_micros", 0) or 0,
                "impressions": c.get("impressions", 0) or 0,
                "clicks": c.get("clicks", 0) or 0,
                "spend_percent": round(
                    (c.get("spend_micros", 0) or 0) / total_spend * 100, 1
                )
                if total_spend > 0
                else 0,
            }
            for c in breakdown
        ]

        return {
            "creative_id": creative_id,
            "countries": countries,
            "total_countries": len(countries),
            "period_days": days,
        }
