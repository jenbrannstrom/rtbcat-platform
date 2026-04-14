"""Creative country breakdown helpers."""

from __future__ import annotations

from typing import Any

from services.creative_performance_service import CreativePerformanceService
from utils.country_codes import get_country_alpha3, get_country_name, normalize_country_code


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
        aggregated: dict[str, dict[str, Any]] = {}
        for country in breakdown:
            raw_code = country.get("country_code")
            if not raw_code:
                continue

            normalized_code = normalize_country_code(raw_code)
            entry = aggregated.setdefault(
                normalized_code,
                {
                    "country_code": normalized_code,
                    "country_name": get_country_name(normalized_code),
                    "country_iso3": get_country_alpha3(normalized_code),
                    "spend_micros": 0,
                    "impressions": 0,
                    "clicks": 0,
                },
            )
            entry["spend_micros"] += country.get("spend_micros", 0) or 0
            entry["impressions"] += country.get("impressions", 0) or 0
            entry["clicks"] += country.get("clicks", 0) or 0

        countries = sorted(
            aggregated.values(),
            key=lambda item: (-item["spend_micros"], item["country_code"]),
        )
        total_spend = sum(country["spend_micros"] for country in countries)

        for country in countries:
            country["spend_percent"] = (
                round(country["spend_micros"] / total_spend * 100, 1)
                if total_spend > 0
                else 0
            )

        return {
            "creative_id": creative_id,
            "countries": countries,
            "total_countries": len(countries),
            "period_days": days,
        }
