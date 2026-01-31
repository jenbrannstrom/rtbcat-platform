"""Service layer for recommendations endpoints."""

from __future__ import annotations

from typing import Any

from analytics.recommendation_engine import RecommendationEngine, Severity


class RecommendationsService:
    """Orchestrates recommendation generation and resolution."""

    def __init__(self, store: Any) -> None:
        self._engine = RecommendationEngine(store)

    async def generate(self, days: int, min_severity: str) -> list[dict[str, Any]]:
        """Generate recommendations with severity filter."""
        severity_map = {
            "low": Severity.LOW,
            "medium": Severity.MEDIUM,
            "high": Severity.HIGH,
            "critical": Severity.CRITICAL,
        }
        min_sev = severity_map.get(min_severity.lower(), Severity.LOW)
        recommendations = await self._engine.generate_recommendations(
            days=days,
            min_severity=min_sev,
        )
        return [rec.to_dict() for rec in recommendations]

    async def summary(self, days: int) -> dict[str, Any]:
        """Return recommendation summary."""
        return await self._engine.get_summary(days=days)

    async def resolve(self, recommendation_id: str, notes: str | None) -> bool:
        """Resolve a recommendation by id."""
        return await self._engine.resolve_recommendation(recommendation_id, notes)

    async def by_type(self, rec_type: str, days: int) -> list[dict[str, Any]]:
        """Return recommendations filtered by type."""
        recommendations = await self._engine.generate_recommendations(
            days=days,
            min_severity=Severity.LOW,
        )
        return [rec.to_dict() for rec in recommendations if rec.type.value == rec_type]
