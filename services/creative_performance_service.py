"""Business logic for creative performance lookups."""

from __future__ import annotations

import logging
from typing import Any

from storage.postgres_repositories.creative_performance_repo import (
    CreativePerformanceRepository,
)

logger = logging.getLogger(__name__)


class CreativePerformanceService:
    """Service layer for creative performance and activity flags."""

    def __init__(self, repo: CreativePerformanceRepository | None = None) -> None:
        self._repo = repo or CreativePerformanceRepository()

    async def get_active_creative_ids(
        self, creative_ids: list[str], days: int
    ) -> set[str]:
        try:
            rows = await self._repo.get_active_creative_ids(creative_ids, days)
            return set(rows)
        except Exception as e:
            logger.debug("Could not filter active creatives: %s", e, exc_info=True)
            return set()

    async def get_waste_flags(
        self,
        creative_ids: list[str],
        thumbnail_statuses: dict[str, dict[str, Any]],
        days: int,
    ) -> dict[str, dict[str, bool]]:
        if not creative_ids:
            return {}

        perf_data: dict[str, dict[str, Any]] = {}
        try:
            rows = await self._repo.get_rtb_daily_perf(creative_ids, days)
            perf_data = {
                row["creative_id"]: {
                    "impressions": row.get("total_impressions") or 0,
                    "clicks": row.get("total_clicks") or 0,
                }
                for row in rows
            }
        except Exception as e:
            logger.debug("Could not fetch performance data: %s", e, exc_info=True)

        result: dict[str, dict[str, bool]] = {}
        for cid in creative_ids:
            ts = thumbnail_statuses.get(cid)
            perf = perf_data.get(cid, {"impressions": 0, "clicks": 0})
            impressions = perf["impressions"] or 0
            clicks = perf["clicks"] or 0

            broken_video = (
                ts is not None
                and ts.get("status") == "failed"
                and impressions > 0
            )
            zero_engagement = impressions > 1000 and clicks == 0

            result[cid] = {
                "broken_video": broken_video,
                "zero_engagement": zero_engagement,
            }

        return result

    async def get_primary_countries(
        self, creative_ids: list[str], days: int
    ) -> dict[str, str]:
        if not creative_ids:
            return {}
        try:
            rows = await self._repo.get_primary_countries(creative_ids, days)
            return {row["creative_id"]: row["geography"] for row in rows}
        except Exception as e:
            logger.debug("Could not fetch country data: %s", e, exc_info=True)
            return {}

    async def get_country_breakdown(
        self, creative_id: str, days: int
    ) -> list[dict[str, Any]]:
        try:
            return await self._repo.get_country_breakdown(creative_id, days)
        except Exception as e:
            logger.debug("Could not fetch country breakdown: %s", e, exc_info=True)
            return []
