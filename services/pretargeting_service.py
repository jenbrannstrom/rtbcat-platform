"""Business logic for pretargeting workflows."""

from __future__ import annotations

from typing import Any

from storage.postgres_repositories.pretargeting_repo import PretargetingRepository


class PretargetingService:
    """Service layer for pretargeting configs + publishers."""

    def __init__(self, repo: PretargetingRepository | None = None) -> None:
        self._repo = repo or PretargetingRepository()

    async def list_configs(self, bidder_id: str | None = None) -> list[dict[str, Any]]:
        return await self._repo.list_configs(bidder_id=bidder_id)

    async def get_config(self, billing_id: str) -> dict[str, Any] | None:
        if not billing_id:
            raise ValueError("billing_id is required")
        return await self._repo.get_config_by_billing_id(billing_id)

    async def save_config(self, config: dict[str, Any]) -> None:
        if not config.get("billing_id"):
            raise ValueError("billing_id is required")
        await self._repo.save_config(config)

    async def update_user_name(self, billing_id: str, user_name: str | None) -> int:
        if not billing_id:
            raise ValueError("billing_id is required")
        return await self._repo.update_user_name(billing_id, user_name)

    async def update_state(self, billing_id: str, state: str) -> int:
        if not billing_id:
            raise ValueError("billing_id is required")
        if not state:
            raise ValueError("state is required")
        return await self._repo.update_state(billing_id, state)

    async def list_history(self, billing_id: str, limit: int = 100) -> list[dict[str, Any]]:
        if not billing_id:
            raise ValueError("billing_id is required")
        return await self._repo.list_history(billing_id, limit=limit)

    async def add_history(
        self,
        config_id: int,
        user_id: str,
        action: str,
        summary: str,
        details: dict[str, Any],
    ) -> int:
        if not user_id:
            raise ValueError("user_id is required")
        return await self._repo.add_history(config_id, user_id, action, summary, details)

    async def list_publishers(
        self, billing_id: str, mode: str | None = None
    ) -> list[dict[str, Any]]:
        if not billing_id:
            raise ValueError("billing_id is required")
        return await self._repo.list_publishers(billing_id, mode=mode)

    async def add_publisher(
        self,
        billing_id: str,
        publisher_id: str,
        mode: str,
        status: str = "active",
        source: str = "manual",
    ) -> int:
        if not billing_id or not publisher_id or not mode:
            raise ValueError("billing_id, publisher_id, and mode are required")
        return await self._repo.add_publisher(
            billing_id=billing_id,
            publisher_id=publisher_id,
            mode=mode,
            status=status,
            source=source,
        )

    async def update_publisher_status(
        self, billing_id: str, publisher_id: str, mode: str, status: str
    ) -> int:
        if not billing_id or not publisher_id or not mode:
            raise ValueError("billing_id, publisher_id, and mode are required")
        return await self._repo.update_publisher_status(
            billing_id=billing_id,
            publisher_id=publisher_id,
            mode=mode,
            status=status,
        )

    async def delete_publisher(self, billing_id: str, publisher_id: str, mode: str) -> int:
        if not billing_id or not publisher_id or not mode:
            raise ValueError("billing_id, publisher_id, and mode are required")
        return await self._repo.delete_publisher(billing_id, publisher_id, mode)

    async def clear_sync_publishers(self, billing_id: str) -> int:
        if not billing_id:
            raise ValueError("billing_id is required")
        return await self._repo.clear_sync_publishers(billing_id)

    async def check_publisher_in_opposite_mode(
        self, billing_id: str, publisher_id: str, mode: str
    ) -> dict[str, Any] | None:
        if not billing_id or not publisher_id or not mode:
            raise ValueError("billing_id, publisher_id, and mode are required")
        return await self._repo.check_publisher_in_opposite_mode(
            billing_id, publisher_id, mode
        )
