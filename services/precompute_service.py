"""Service layer for precompute health checks."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from storage.postgres_repositories.precompute_repo import PrecomputeRepository

logger = logging.getLogger(__name__)


@dataclass
class CacheHealth:
    """Health status for a precompute cache."""

    cache_name: str
    refreshed_at: Optional[str]
    is_stale: bool
    is_missing: bool


@dataclass
class PrecomputeHealthStatus:
    """Overall precompute health status."""

    ok: bool
    max_age_hours: int
    checked_at: str
    stale_caches: list[str]
    missing_caches: list[str]
    cache_refresh_times: dict[str, str]


class PrecomputeService:
    """Orchestrates precompute health checks."""

    REQUIRED_CACHES = ["home_summaries", "config_breakdowns", "rtb_summaries"]

    def __init__(self, repo: PrecomputeRepository | None = None) -> None:
        self._repo = repo or PrecomputeRepository()

    async def get_health_status(self, max_age_hours: int) -> PrecomputeHealthStatus:
        """Check health of all precompute caches.

        Args:
            max_age_hours: Maximum acceptable age for cache data.

        Returns:
            PrecomputeHealthStatus with detailed cache status.
        """
        cutoff = datetime.utcnow() - timedelta(hours=max_age_hours)

        try:
            rows = await self._repo.get_cache_refresh_times()
        except Exception as e:
            logger.error(f"Failed to fetch cache refresh times: {e}")
            rows = []

        refresh_map = {
            row["cache_name"]: row["refreshed_at"]
            for row in rows
            if row.get("refreshed_at")
        }

        stale_caches: list[str] = []
        missing_caches: list[str] = []
        cache_refresh_times: dict[str, str] = {}

        for cache_name in self.REQUIRED_CACHES:
            refreshed_at = refresh_map.get(cache_name)
            if not refreshed_at:
                missing_caches.append(cache_name)
                continue

            try:
                refreshed_dt = datetime.fromisoformat(refreshed_at)
            except ValueError:
                missing_caches.append(cache_name)
                continue

            cache_refresh_times[cache_name] = refreshed_at
            if refreshed_dt < cutoff:
                stale_caches.append(cache_name)

        ok = not stale_caches and not missing_caches

        if not ok:
            logger.warning(
                "Precompute health check failed: stale=%s missing=%s",
                stale_caches,
                missing_caches,
            )

        return PrecomputeHealthStatus(
            ok=ok,
            max_age_hours=max_age_hours,
            checked_at=datetime.utcnow().isoformat(),
            stale_caches=stale_caches,
            missing_caches=missing_caches,
            cache_refresh_times=cache_refresh_times,
        )
