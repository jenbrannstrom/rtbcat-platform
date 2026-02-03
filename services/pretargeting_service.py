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
        if not config.get("config_id"):
            raise ValueError("config_id is required")
        if not config.get("bidder_id"):
            raise ValueError("bidder_id is required")
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

    async def list_history(
        self,
        config_id: str | None = None,
        billing_id: str | None = None,
        days: int = 30,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        return await self._repo.list_history(
            config_id=config_id,
            billing_id=billing_id,
            days=days,
            limit=limit,
        )

    async def add_history(
        self,
        config_id: str,
        bidder_id: str,
        change_type: str,
        field_changed: str | None,
        old_value: str | None,
        new_value: str | None,
        changed_by: str | None,
        change_source: str = "user",
        raw_config_snapshot: dict[str, Any] | None = None,
    ) -> int:
        if not bidder_id:
            raise ValueError("bidder_id is required")
        if not change_type:
            raise ValueError("change_type is required")
        return await self._repo.add_history(
            config_id=config_id,
            bidder_id=bidder_id,
            change_type=change_type,
            field_changed=field_changed,
            old_value=old_value,
            new_value=new_value,
            changed_by=changed_by,
            change_source=change_source,
            raw_config_snapshot=raw_config_snapshot,
        )

    async def list_publishers(
        self, billing_id: str, mode: str | None = None, status: str | None = None
    ) -> list[dict[str, Any]]:
        if not billing_id:
            raise ValueError("billing_id is required")
        return await self._repo.list_publishers(billing_id, mode=mode, status=status)

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

    async def list_pending_publisher_changes(self, billing_id: str) -> list[dict[str, Any]]:
        if not billing_id:
            raise ValueError("billing_id is required")
        return await self._repo.list_pending_publisher_changes(billing_id)

    async def get_publisher_rows(self, billing_id: str, publisher_id: str) -> list[dict[str, Any]]:
        if not billing_id or not publisher_id:
            raise ValueError("billing_id and publisher_id are required")
        return await self._repo.get_publisher_rows(billing_id, publisher_id)
