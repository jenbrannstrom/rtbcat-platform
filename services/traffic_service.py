"""Service layer for traffic import."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from storage.postgres_repositories.traffic_repo import TrafficRepository


class TrafficService:
    """Orchestrates traffic import parsing and persistence."""

    def __init__(self, repo: TrafficRepository | None = None) -> None:
        self._repo = repo or TrafficRepository()

    async def insert_rows(self, records: list[dict[str, Any]]) -> int:
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
