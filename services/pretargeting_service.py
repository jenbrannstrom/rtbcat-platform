"""Business logic for pretargeting workflows."""

from __future__ import annotations

import time
from typing import Any

from storage.postgres_repositories.pretargeting_repo import PretargetingRepository


class PretargetingService:
    """Service layer for pretargeting configs + publishers."""

    _LIST_CONFIGS_CACHE_TTL_SECONDS = 15.0
    _LIST_CONFIGS_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
    _HISTORY_CACHE_TTL_SECONDS = 15.0
    _HISTORY_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
    _CONFIG_CACHE_TTL_SECONDS = 15.0
    _CONFIG_CACHE: dict[str, tuple[float, dict[str, Any] | None]] = {}

    def __init__(self, repo: PretargetingRepository | None = None) -> None:
        self._repo = repo or PretargetingRepository()

    @staticmethod
    def _list_cache_key(
        scope: str,
        limit: int | None = None,
        summary_only: bool = False,
    ) -> str:
        limit_key = "all" if limit is None else str(limit)
        summary_key = "summary" if summary_only else "full"
        return f"{scope}:limit:{limit_key}:shape:{summary_key}"

    @staticmethod
    def _history_cache_key(
        config_id: str | None,
        billing_id: str | None,
        days: int,
        limit: int,
    ) -> str:
        return (
            f"config:{config_id or '__all__'}:"
            f"billing:{billing_id or '__all__'}:"
            f"days:{days}:limit:{limit}"
        )

    async def list_configs(
        self,
        bidder_id: str | None = None,
        limit: int | None = None,
        summary_only: bool = False,
    ) -> list[dict[str, Any]]:
        cache_key = self._list_cache_key(
            bidder_id or "__all__",
            limit=limit,
            summary_only=summary_only,
        )
        now = time.monotonic()
        cached_entry = self._LIST_CONFIGS_CACHE.get(cache_key)
        if cached_entry and cached_entry[0] > now:
            return [dict(row) for row in cached_entry[1]]

        rows = await self._repo.list_configs(
            bidder_id=bidder_id,
            limit=limit,
            summary_only=summary_only,
        )
        self._LIST_CONFIGS_CACHE[cache_key] = (
            now + self._LIST_CONFIGS_CACHE_TTL_SECONDS,
            [dict(row) for row in rows],
        )
        return rows

    async def list_configs_for_buyer(
        self,
        buyer_id: str,
        limit: int | None = None,
        summary_only: bool = False,
    ) -> list[dict[str, Any]]:
        if not buyer_id:
            raise ValueError("buyer_id is required")
        cache_key = self._list_cache_key(
            f"buyer:{buyer_id}",
            limit=limit,
            summary_only=summary_only,
        )
        now = time.monotonic()
        cached_entry = self._LIST_CONFIGS_CACHE.get(cache_key)
        if cached_entry and cached_entry[0] > now:
            return [dict(row) for row in cached_entry[1]]

        rows = await self._repo.list_configs_for_buyer(
            buyer_id=buyer_id,
            limit=limit,
            summary_only=summary_only,
        )
        self._LIST_CONFIGS_CACHE[cache_key] = (
            now + self._LIST_CONFIGS_CACHE_TTL_SECONDS,
            [dict(row) for row in rows],
        )
        return rows

    @classmethod
    def clear_list_configs_cache(cls) -> None:
        cls._LIST_CONFIGS_CACHE.clear()

    @classmethod
    def clear_history_cache(cls) -> None:
        cls._HISTORY_CACHE.clear()

    @classmethod
    def clear_config_cache(cls) -> None:
        cls._CONFIG_CACHE.clear()

    @classmethod
    def _invalidate_list_configs_cache(cls, bidder_id: str | None = None) -> None:
        cls._LIST_CONFIGS_CACHE.clear()

    @classmethod
    def _invalidate_history_cache(cls) -> None:
        cls._HISTORY_CACHE.clear()

    @classmethod
    def _invalidate_config_cache(cls, billing_id: str | None = None) -> None:
        if billing_id is None:
            cls._CONFIG_CACHE.clear()
            return
        cls._CONFIG_CACHE.pop(billing_id, None)

    async def get_config(self, billing_id: str) -> dict[str, Any] | None:
        if not billing_id:
            raise ValueError("billing_id is required")
        now = time.monotonic()
        cached_entry = self._CONFIG_CACHE.get(billing_id)
        if cached_entry and cached_entry[0] > now:
            cached_value = cached_entry[1]
            return dict(cached_value) if cached_value else None

        row = await self._repo.get_config_by_billing_id(billing_id)
        cached_row = dict(row) if row else None
        self._CONFIG_CACHE[billing_id] = (
            now + self._CONFIG_CACHE_TTL_SECONDS,
            cached_row,
        )
        return dict(cached_row) if cached_row else None

    async def save_config(self, config: dict[str, Any]) -> None:
        if not config.get("config_id"):
            raise ValueError("config_id is required")
        if not config.get("bidder_id"):
            raise ValueError("bidder_id is required")
        await self._repo.save_config(config)
        self._invalidate_list_configs_cache(str(config.get("bidder_id")))
        self._invalidate_config_cache(str(config.get("billing_id")) if config.get("billing_id") else None)

    async def update_user_name(self, billing_id: str, user_name: str | None) -> int:
        if not billing_id:
            raise ValueError("billing_id is required")
        updated = await self._repo.update_user_name(billing_id, user_name)
        self._invalidate_list_configs_cache()
        self._invalidate_config_cache(billing_id)
        return updated

    async def update_state(self, billing_id: str, state: str) -> int:
        if not billing_id:
            raise ValueError("billing_id is required")
        if not state:
            raise ValueError("state is required")
        updated = await self._repo.update_state(billing_id, state)
        self._invalidate_list_configs_cache()
        self._invalidate_config_cache(billing_id)
        return updated

    async def list_history(
        self,
        config_id: str | None = None,
        billing_id: str | None = None,
        days: int = 30,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        cache_key = self._history_cache_key(
            config_id=config_id,
            billing_id=billing_id,
            days=days,
            limit=limit,
        )
        now = time.monotonic()
        cached_entry = self._HISTORY_CACHE.get(cache_key)
        if cached_entry and cached_entry[0] > now:
            return [dict(row) for row in cached_entry[1]]

        rows = await self._repo.list_history(
            config_id=config_id,
            billing_id=billing_id,
            days=days,
            limit=limit,
        )
        self._HISTORY_CACHE[cache_key] = (
            now + self._HISTORY_CACHE_TTL_SECONDS,
            [dict(row) for row in rows],
        )
        return rows

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
        history_id = await self._repo.add_history(
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
        self._invalidate_history_cache()
        return history_id

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
