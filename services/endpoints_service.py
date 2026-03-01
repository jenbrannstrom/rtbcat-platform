"""Business logic for RTB endpoints."""

from __future__ import annotations

import time
from typing import Any, Optional

from storage.postgres_repositories.endpoints_repo import EndpointsRepository


class EndpointsService:
    """Service layer for RTB endpoint workflows."""

    _CACHE_TTL_SECONDS = 15.0
    _LIST_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
    _CURRENT_QPS_CACHE: dict[str, tuple[float, float]] = {}

    def __init__(self, repo: EndpointsRepository | None = None) -> None:
        self._repo = repo or EndpointsRepository()

    @classmethod
    def _cache_key(cls, bidder_id: str | None) -> str:
        return bidder_id or "__all__"

    @classmethod
    def clear_caches(cls) -> None:
        cls._LIST_CACHE.clear()
        cls._CURRENT_QPS_CACHE.clear()

    @classmethod
    def _invalidate_caches(cls, bidder_id: str | None = None) -> None:
        key = cls._cache_key(bidder_id)
        cls._LIST_CACHE.pop(key, None)
        cls._CURRENT_QPS_CACHE.pop(key, None)
        cls._LIST_CACHE.pop("__all__", None)
        cls._CURRENT_QPS_CACHE.pop("__all__", None)

    async def sync_endpoints(self, bidder_id: str, endpoints: list[dict[str, Any]]) -> int:
        if not bidder_id:
            raise ValueError("bidder_id is required")
        if not endpoints:
            return 0
        updated = await self._repo.upsert_endpoints(bidder_id, endpoints)
        self._invalidate_caches(bidder_id)
        return updated

    async def list_endpoints(self, bidder_id: str | None = None) -> list[dict[str, Any]]:
        cache_key = self._cache_key(bidder_id)
        now = time.monotonic()
        cached = self._LIST_CACHE.get(cache_key)
        if cached and cached[0] > now:
            return [dict(row) for row in cached[1]]

        rows = await self._repo.list_endpoints(bidder_id=bidder_id)
        self._LIST_CACHE[cache_key] = (
            now + self._CACHE_TTL_SECONDS,
            [dict(row) for row in rows],
        )
        return rows

    async def get_current_qps(self, bidder_id: str | None = None) -> float:
        cache_key = self._cache_key(bidder_id)
        now = time.monotonic()
        cached = self._CURRENT_QPS_CACHE.get(cache_key)
        if cached and cached[0] > now:
            return float(cached[1])

        value = await self._repo.get_current_qps(bidder_id=bidder_id)
        normalized = float(value)
        self._CURRENT_QPS_CACHE[cache_key] = (
            now + self._CACHE_TTL_SECONDS,
            normalized,
        )
        return normalized

    async def refresh_endpoints_current(
        self,
        lookback_days: int = 7,
        bidder_id: Optional[str] = None,
    ) -> int:
        """Refresh rtb_endpoints_current from bidstream data."""
        refreshed = await self._repo.refresh_endpoints_current(
            lookback_days=lookback_days,
            bidder_id=bidder_id,
        )
        self._invalidate_caches(bidder_id)
        return refreshed
