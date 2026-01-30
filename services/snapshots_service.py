"""Business logic for pretargeting snapshots."""

from __future__ import annotations

from typing import Any

from storage.postgres_repositories.snapshots_repo import SnapshotsRepository


class SnapshotsService:
    """Service layer for snapshot workflows."""

    def __init__(self, repo: SnapshotsRepository | None = None) -> None:
        self._repo = repo or SnapshotsRepository()

    async def create_snapshot(
        self,
        user_id: str,
        config_id: int,
        billing_id: str,
        snapshot_data: dict[str, Any],
    ) -> int:
        if not user_id:
            raise ValueError("user_id is required")
        if not billing_id:
            raise ValueError("billing_id is required")
        return await self._repo.create_snapshot(
            user_id=user_id,
            config_id=config_id,
            billing_id=billing_id,
            snapshot_data=snapshot_data,
        )

    async def list_snapshots(
        self,
        billing_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        if not billing_id:
            raise ValueError("billing_id is required")
        return await self._repo.list_snapshots(
            billing_id=billing_id,
            limit=limit,
            offset=offset,
        )

    async def get_snapshot(self, snapshot_id: int) -> dict[str, Any] | None:
        if snapshot_id <= 0:
            raise ValueError("snapshot_id must be positive")
        return await self._repo.get_snapshot_by_id(snapshot_id)
