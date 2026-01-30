"""Business logic for pretargeting changes."""

from __future__ import annotations

from typing import Any

from storage.postgres_repositories.changes_repo import ChangesRepository


class ChangesService:
    """Service layer for pending changes workflows."""

    def __init__(self, repo: ChangesRepository | None = None) -> None:
        self._repo = repo or ChangesRepository()

    async def create_pending_change(
        self,
        config_id: int,
        billing_id: str,
        change_type: str,
        field_name: str,
        value: str,
        reason: str | None,
        estimated_qps_impact: float | None,
        created_by: str | None,
    ) -> int:
        if not billing_id:
            raise ValueError("billing_id is required")
        if not change_type:
            raise ValueError("change_type is required")
        if not field_name:
            raise ValueError("field_name is required")
        if value is None:
            raise ValueError("value is required")
        return await self._repo.create_pending_change(
            config_id=config_id,
            billing_id=billing_id,
            change_type=change_type,
            field_name=field_name,
            value=value,
            reason=reason,
            estimated_qps_impact=estimated_qps_impact,
            created_by=created_by,
        )

    async def list_pending_changes(
        self, billing_id: str | None, status: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        if not status:
            raise ValueError("status is required")
        return await self._repo.list_pending_changes(
            billing_id=billing_id,
            status=status,
            limit=limit,
        )

    async def get_pending_change(self, change_id: int) -> dict[str, Any] | None:
        if change_id <= 0:
            raise ValueError("change_id must be positive")
        return await self._repo.get_pending_change(change_id)

    async def cancel_pending_change(self, change_id: int) -> int:
        if change_id <= 0:
            raise ValueError("change_id must be positive")
        return await self._repo.cancel_pending_change(change_id)

    async def mark_pending_change_applied(
        self, change_id: int, applied_by: str | None = None
    ) -> int:
        if change_id <= 0:
            raise ValueError("change_id must be positive")
        return await self._repo.mark_pending_change_applied(change_id, applied_by)
