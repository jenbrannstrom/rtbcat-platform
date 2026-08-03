"""Service layer for recommendations endpoints."""

from __future__ import annotations

from typing import Any

from analytics.recommendation_engine import RecommendationEngine, Severity


class RecommendationsService:
    """Orchestrates recommendation generation and resolution."""

    def __init__(self, store: Any) -> None:
        self._engine = RecommendationEngine(store)

    async def generate(
        self,
        *,
        buyer_id: str,
        days: int,
        min_severity: str,
    ) -> list[dict[str, Any]]:
        """Generate recommendations with severity filter."""
        severity_map = {
            "low": Severity.LOW,
            "medium": Severity.MEDIUM,
            "high": Severity.HIGH,
            "critical": Severity.CRITICAL,
        }
        min_sev = severity_map.get(min_severity.lower(), Severity.LOW)
        recommendations = await self._engine.generate_recommendations(
            buyer_id=buyer_id,
            days=days,
            min_severity=min_sev,
        )
        return [rec.to_dict() for rec in recommendations]

    async def summary(self, *, buyer_id: str, days: int) -> dict[str, Any]:
        """Return recommendation summary."""
        return await self._engine.get_summary(buyer_id=buyer_id, days=days)

    async def resolve(
        self,
        *,
        buyer_id: str,
        recommendation_id: str,
        notes: str | None,
    ) -> bool:
        """Resolve a recommendation by id."""
        return await self._engine.resolve_recommendation(
            buyer_id=buyer_id,
            rec_id=recommendation_id,
            notes=notes,
        )

    async def by_type(
        self,
        *,
        buyer_id: str,
        rec_type: str,
        days: int,
    ) -> list[dict[str, Any]]:
        """Return recommendations filtered by type."""
        recommendations = await self._engine.generate_recommendations(
            buyer_id=buyer_id,
            days=days,
            min_severity=Severity.LOW,
        )
        return [rec.to_dict() for rec in recommendations if rec.type.value == rec_type]
