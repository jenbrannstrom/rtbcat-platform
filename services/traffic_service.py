"""Service layer for traffic import."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import HTTPException

from storage.postgres_repositories.traffic_repo import TrafficRepository


class TrafficService:
    """Orchestrates traffic import parsing and persistence."""

    def __init__(self, repo: TrafficRepository | None = None) -> None:
        self._repo = repo or TrafficRepository()

    async def insert_rows(self, records: list[dict[str, Any]]) -> int:
        """Insert traffic records from CSV import.

        Args:
            records: List of traffic record dicts with canonical_size, raw_size,
                     request_count, date, and buyer_id.

        Returns:
            Number of records inserted.
        """
        if not records:
            raise HTTPException(status_code=400, detail="No valid records found in CSV")

        count = 0
        for record in records:
            await self._repo.upsert_traffic_row(
                canonical_size=record["canonical_size"],
                raw_size=record["raw_size"],
                request_count=record["request_count"],
                date=record["date"],
                buyer_id=record["buyer_id"],
            )
            count += 1
        return count

    async def generate_and_insert_mock_traffic(
        self,
        days: int,
        buyer_id: Optional[str],
        base_daily_requests: int,
        waste_bias: float,
    ) -> int:
        """Generate mock traffic data and insert it.

        Args:
            days: Number of days of traffic to generate.
            buyer_id: Buyer ID to associate with the traffic.
            base_daily_requests: Base daily request volume.
            waste_bias: Bias towards waste traffic (0-1).

        Returns:
            Number of records inserted.
        """
        from analytics import generate_mock_traffic

        traffic_records = generate_mock_traffic(
            days=days,
            buyer_id=buyer_id,
            base_daily_requests=base_daily_requests,
            waste_bias=waste_bias,
        )

        count = 0
        for r in traffic_records:
            await self._repo.upsert_traffic_row(
                canonical_size=r.canonical_size,
                raw_size=r.raw_size,
                request_count=r.request_count,
                date=r.date,
                buyer_id=r.buyer_id,
            )
            count += 1

        return count
