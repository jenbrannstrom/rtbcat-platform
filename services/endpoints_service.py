"""Business logic for RTB endpoints."""

from __future__ import annotations

from typing import Any, Optional

from storage.postgres_repositories.endpoints_repo import EndpointsRepository


class EndpointsService:
    """Service layer for RTB endpoint workflows."""

    def __init__(self, repo: EndpointsRepository | None = None) -> None:
        self._repo = repo or EndpointsRepository()

    async def sync_endpoints(self, bidder_id: str, endpoints: list[dict[str, Any]]) -> int:
        if not bidder_id:
            raise ValueError("bidder_id is required")
        if not endpoints:
            return 0
        return await self._repo.upsert_endpoints(bidder_id, endpoints)

    async def list_endpoints(self, bidder_id: str | None = None) -> list[dict[str, Any]]:
        return await self._repo.list_endpoints(bidder_id=bidder_id)

    async def get_current_qps(self, bidder_id: str | None = None) -> float:
        return await self._repo.get_current_qps(bidder_id=bidder_id)

    async def refresh_endpoints_current(
        self,
        lookback_days: int = 7,
        bidder_id: Optional[str] = None,
    ) -> int:
        """Refresh rtb_endpoints_current from bidstream data."""
        return await self._repo.refresh_endpoints_current(
            lookback_days=lookback_days,
            bidder_id=bidder_id,
        )
