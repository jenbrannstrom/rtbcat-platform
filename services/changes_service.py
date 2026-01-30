"""Business logic for pretargeting changes."""

from __future__ import annotations

from typing import Any

from storage.postgres_repositories.changes_repo import ChangesRepository


class ChangesService:
    """Service layer for pending changes workflows."""

    def __init__(self, repo: ChangesRepository | None = None) -> None:
        self._repo = repo or ChangesRepository()

    async def create_change(
        self,
        config_id: int,
        billing_id: str,
        action_type: str,
        payload: dict[str, Any],
        created_by: str,
    ) -> int:
        if not billing_id:
            raise ValueError("billing_id is required")
        if not action_type:
            raise ValueError("action_type is required")
        if not created_by:
            raise ValueError("created_by is required")
        return await self._repo.create_change(
            config_id=config_id,
            billing_id=billing_id,
            action_type=action_type,
            payload=payload,
            created_by=created_by,
        )

    async def list_changes(
        self, billing_id: str, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        if not billing_id:
            raise ValueError("billing_id is required")
        return await self._repo.list_changes(
            billing_id=billing_id,
            limit=limit,
            offset=offset,
        )

    async def get_change(self, change_id: int) -> dict[str, Any] | None:
        if change_id <= 0:
            raise ValueError("change_id must be positive")
        return await self._repo.get_change(change_id)

    async def update_status(self, change_id: int, status: str) -> int:
        if change_id <= 0:
            raise ValueError("change_id must be positive")
        if not status:
            raise ValueError("status is required")
        return await self._repo.update_change_status(change_id, status)

    async def delete_change(self, change_id: int) -> int:
        if change_id <= 0:
            raise ValueError("change_id must be positive")
        return await self._repo.delete_change(change_id)
