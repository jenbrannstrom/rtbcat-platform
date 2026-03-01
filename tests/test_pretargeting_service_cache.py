"""Cache behavior tests for PretargetingService list configs path."""

from __future__ import annotations

import pytest

from services.pretargeting_service import PretargetingService


def _clear_service_caches() -> None:
    PretargetingService.clear_list_configs_cache()
    PretargetingService.clear_history_cache()
    PretargetingService.clear_config_cache()
    PretargetingService.clear_publishers_cache()


class _StubPretargetingRepo:
    def __init__(self) -> None:
        self.list_calls = 0
        self.list_by_buyer_calls = 0
        self.list_history_calls = 0
        self.add_history_calls = 0
        self.get_config_calls = 0
        self.list_publishers_calls = 0
        self.add_publisher_calls = 0
        self.update_publisher_status_calls = 0
        self.delete_publisher_calls = 0
        self.clear_sync_publishers_calls = 0
        self.list_pending_publisher_changes_calls = 0
        self.rows: list[dict[str, object]] = [{"billing_id": "1001"}]
        self.history_rows: list[dict[str, object]] = [{"config_id": "cfg-1", "change_type": "update"}]
        self.config_row: dict[str, object] | None = {"billing_id": "1001", "state": "ACTIVE"}
        self.publisher_rows: list[dict[str, object]] = [
            {"billing_id": "1001", "publisher_id": "pub-1", "mode": "WHITELIST", "status": "active"}
        ]
        self.pending_publisher_rows: list[dict[str, object]] = [
            {"billing_id": "1001", "publisher_id": "pub-2", "mode": "BLACKLIST", "status": "pending_add"}
        ]

    async def list_configs(
        self,
        bidder_id: str | None = None,
        limit: int | None = None,
        summary_only: bool = False,
    ) -> list[dict[str, object]]:
        self.list_calls += 1
        return [dict(row) for row in self.rows]

    async def list_configs_for_buyer(
        self,
        buyer_id: str,
        limit: int | None = None,
        summary_only: bool = False,
    ) -> list[dict[str, object]]:
        self.list_by_buyer_calls += 1
        return [dict(row) for row in self.rows]

    async def save_config(self, _config: dict[str, object]) -> None:
        return None

    async def get_config_by_billing_id(self, _billing_id: str) -> dict[str, object] | None:
        self.get_config_calls += 1
        return dict(self.config_row) if self.config_row else None

    async def update_user_name(self, _billing_id: str, _user_name: str | None) -> int:
        return 1

    async def update_state(self, _billing_id: str, _state: str) -> int:
        return 1

    async def list_history(
        self,
        config_id: str | None = None,
        billing_id: str | None = None,
        days: int = 30,
        limit: int = 500,
    ) -> list[dict[str, object]]:
        self.list_history_calls += 1
        return [dict(row) for row in self.history_rows]

    async def add_history(
        self,
        config_id: str,
        bidder_id: str,
        change_type: str,
        field_changed: str | None,
        old_value: str | None,
        new_value: str | None,
        changed_by: str | None,
        change_source: str,
        raw_config_snapshot: dict[str, object] | None = None,
    ) -> int:
        self.add_history_calls += 1
        return 1

    async def list_publishers(
        self,
        billing_id: str,
        mode: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, object]]:
        self.list_publishers_calls += 1
        rows = [row for row in self.publisher_rows if row["billing_id"] == billing_id]
        if mode:
            rows = [row for row in rows if row["mode"] == mode]
        if status:
            rows = [row for row in rows if row["status"] == status]
        return [dict(row) for row in rows]

    async def add_publisher(
        self,
        billing_id: str,
        publisher_id: str,
        mode: str,
        status: str = "active",
        source: str = "manual",
    ) -> int:
        self.add_publisher_calls += 1
        self.publisher_rows.append(
            {
                "billing_id": billing_id,
                "publisher_id": publisher_id,
                "mode": mode,
                "status": status,
                "source": source,
            }
        )
        return 1

    async def update_publisher_status(
        self,
        billing_id: str,
        publisher_id: str,
        mode: str,
        status: str,
    ) -> int:
        self.update_publisher_status_calls += 1
        for row in self.publisher_rows:
            if (
                row["billing_id"] == billing_id
                and row["publisher_id"] == publisher_id
                and row["mode"] == mode
            ):
                row["status"] = status
        return 1

    async def delete_publisher(self, billing_id: str, publisher_id: str, mode: str) -> int:
        self.delete_publisher_calls += 1
        self.publisher_rows = [
            row
            for row in self.publisher_rows
            if not (
                row["billing_id"] == billing_id
                and row["publisher_id"] == publisher_id
                and row["mode"] == mode
            )
        ]
        return 1

    async def clear_sync_publishers(self, billing_id: str) -> int:
        self.clear_sync_publishers_calls += 1
        self.publisher_rows = [
            row
            for row in self.publisher_rows
            if not (row["billing_id"] == billing_id and row.get("source") == "api_sync")
        ]
        return 1

    async def list_pending_publisher_changes(
        self,
        billing_id: str,
    ) -> list[dict[str, object]]:
        self.list_pending_publisher_changes_calls += 1
        return [
            dict(row)
            for row in self.pending_publisher_rows
            if row["billing_id"] == billing_id
        ]


@pytest.mark.asyncio
async def test_list_configs_uses_ttl_cache_per_bidder() -> None:
    _clear_service_caches()
    repo = _StubPretargetingRepo()
    service = PretargetingService(repo=repo)

    first = await service.list_configs(bidder_id="bidder-1")
    first[0]["billing_id"] = "mutated-locally"
    second = await service.list_configs(bidder_id="bidder-1")

    assert repo.list_calls == 1
    assert second[0]["billing_id"] == "1001"


@pytest.mark.asyncio
async def test_save_config_invalidates_list_cache() -> None:
    _clear_service_caches()
    repo = _StubPretargetingRepo()
    service = PretargetingService(repo=repo)

    await service.list_configs(bidder_id="bidder-1")
    assert repo.list_calls == 1

    repo.rows = [{"billing_id": "2002"}]
    await service.save_config({"config_id": "cfg-1", "bidder_id": "bidder-1"})
    refreshed = await service.list_configs(bidder_id="bidder-1")

    assert repo.list_calls == 2
    assert refreshed[0]["billing_id"] == "2002"


@pytest.mark.asyncio
async def test_list_configs_for_buyer_uses_ttl_cache() -> None:
    _clear_service_caches()
    repo = _StubPretargetingRepo()
    service = PretargetingService(repo=repo)

    first = await service.list_configs_for_buyer("buyer-1")
    first[0]["billing_id"] = "mutated-locally"
    second = await service.list_configs_for_buyer("buyer-1")

    assert repo.list_by_buyer_calls == 1
    assert second[0]["billing_id"] == "1001"


@pytest.mark.asyncio
async def test_list_configs_cache_is_scoped_by_limit() -> None:
    _clear_service_caches()
    repo = _StubPretargetingRepo()
    service = PretargetingService(repo=repo)

    await service.list_configs(bidder_id="bidder-1", limit=100)
    await service.list_configs(bidder_id="bidder-1", limit=200)

    assert repo.list_calls == 2


@pytest.mark.asyncio
async def test_list_configs_cache_is_scoped_by_summary_shape() -> None:
    _clear_service_caches()
    repo = _StubPretargetingRepo()
    service = PretargetingService(repo=repo)

    await service.list_configs(bidder_id="bidder-1", limit=100, summary_only=True)
    await service.list_configs(bidder_id="bidder-1", limit=100, summary_only=False)

    assert repo.list_calls == 2


@pytest.mark.asyncio
async def test_save_config_invalidates_buyer_scoped_list_cache() -> None:
    _clear_service_caches()
    repo = _StubPretargetingRepo()
    service = PretargetingService(repo=repo)

    await service.list_configs_for_buyer("buyer-1")
    assert repo.list_by_buyer_calls == 1

    repo.rows = [{"billing_id": "3003"}]
    await service.save_config({"config_id": "cfg-1", "bidder_id": "bidder-1"})
    refreshed = await service.list_configs_for_buyer("buyer-1")

    assert repo.list_by_buyer_calls == 2
    assert refreshed[0]["billing_id"] == "3003"


@pytest.mark.asyncio
async def test_list_history_uses_ttl_cache() -> None:
    _clear_service_caches()
    repo = _StubPretargetingRepo()
    service = PretargetingService(repo=repo)

    first = await service.list_history(config_id="cfg-1", days=30, limit=100)
    first[0]["change_type"] = "mutated-locally"
    second = await service.list_history(config_id="cfg-1", days=30, limit=100)

    assert repo.list_history_calls == 1
    assert second[0]["change_type"] == "update"


@pytest.mark.asyncio
async def test_add_history_invalidates_history_cache() -> None:
    _clear_service_caches()
    repo = _StubPretargetingRepo()
    service = PretargetingService(repo=repo)

    await service.list_history(config_id="cfg-1", days=30, limit=100)
    assert repo.list_history_calls == 1

    repo.history_rows = [{"config_id": "cfg-1", "change_type": "set_maximum_qps"}]
    await service.add_history(
        config_id="cfg-1",
        bidder_id="bidder-1",
        change_type="update",
        field_changed="state",
        old_value="ACTIVE",
        new_value="SUSPENDED",
        changed_by="ui",
    )
    refreshed = await service.list_history(config_id="cfg-1", days=30, limit=100)

    assert repo.add_history_calls == 1
    assert repo.list_history_calls == 2
    assert refreshed[0]["change_type"] == "set_maximum_qps"


@pytest.mark.asyncio
async def test_get_config_uses_ttl_cache() -> None:
    _clear_service_caches()
    repo = _StubPretargetingRepo()
    service = PretargetingService(repo=repo)

    first = await service.get_config("1001")
    first["state"] = "mutated-locally"
    second = await service.get_config("1001")

    assert repo.get_config_calls == 1
    assert second["state"] == "ACTIVE"


@pytest.mark.asyncio
async def test_update_user_name_invalidates_get_config_cache() -> None:
    _clear_service_caches()
    repo = _StubPretargetingRepo()
    service = PretargetingService(repo=repo)

    await service.get_config("1001")
    assert repo.get_config_calls == 1

    repo.config_row = {"billing_id": "1001", "state": "SUSPENDED"}
    await service.update_user_name("1001", "Renamed")
    refreshed = await service.get_config("1001")

    assert repo.get_config_calls == 2
    assert refreshed["state"] == "SUSPENDED"


@pytest.mark.asyncio
async def test_list_publishers_uses_ttl_cache() -> None:
    _clear_service_caches()
    repo = _StubPretargetingRepo()
    service = PretargetingService(repo=repo)

    first = await service.list_publishers("1001")
    first[0]["publisher_id"] = "mutated-locally"
    second = await service.list_publishers("1001")

    assert repo.list_publishers_calls == 1
    assert second[0]["publisher_id"] == "pub-1"


@pytest.mark.asyncio
async def test_add_publisher_invalidates_publishers_cache() -> None:
    _clear_service_caches()
    repo = _StubPretargetingRepo()
    service = PretargetingService(repo=repo)

    await service.list_publishers("1001")
    assert repo.list_publishers_calls == 1

    await service.add_publisher("1001", "pub-3", "WHITELIST")
    refreshed = await service.list_publishers("1001")

    assert repo.add_publisher_calls == 1
    assert repo.list_publishers_calls == 2
    assert any(row["publisher_id"] == "pub-3" for row in refreshed)


@pytest.mark.asyncio
async def test_list_pending_publisher_changes_uses_ttl_cache() -> None:
    _clear_service_caches()
    repo = _StubPretargetingRepo()
    service = PretargetingService(repo=repo)

    first = await service.list_pending_publisher_changes("1001")
    first[0]["publisher_id"] = "mutated-locally"
    second = await service.list_pending_publisher_changes("1001")

    assert repo.list_pending_publisher_changes_calls == 1
    assert second[0]["publisher_id"] == "pub-2"


@pytest.mark.asyncio
async def test_update_publisher_status_invalidates_pending_changes_cache() -> None:
    _clear_service_caches()
    repo = _StubPretargetingRepo()
    service = PretargetingService(repo=repo)

    await service.list_pending_publisher_changes("1001")
    assert repo.list_pending_publisher_changes_calls == 1

    repo.pending_publisher_rows = [
        {"billing_id": "1001", "publisher_id": "pub-9", "mode": "BLACKLIST", "status": "pending_remove"}
    ]
    await service.update_publisher_status("1001", "pub-1", "WHITELIST", "pending_remove")
    refreshed = await service.list_pending_publisher_changes("1001")

    assert repo.update_publisher_status_calls == 1
    assert repo.list_pending_publisher_changes_calls == 2
    assert refreshed[0]["publisher_id"] == "pub-9"


@pytest.mark.asyncio
async def test_check_publisher_in_opposite_mode_reuses_cached_publishers() -> None:
    _clear_service_caches()
    repo = _StubPretargetingRepo()
    service = PretargetingService(repo=repo)

    first = await service.check_publisher_in_opposite_mode("1001", "pub-1", "BLACKLIST")
    second = await service.check_publisher_in_opposite_mode("1001", "pub-1", "BLACKLIST")

    assert repo.list_publishers_calls == 1
    assert first == {"mode": "WHITELIST"}
    assert second == {"mode": "WHITELIST"}


@pytest.mark.asyncio
async def test_get_publisher_rows_reuses_cached_publishers_list() -> None:
    _clear_service_caches()
    repo = _StubPretargetingRepo()
    service = PretargetingService(repo=repo)

    first = await service.get_publisher_rows("1001", "pub-1")
    second = await service.get_publisher_rows("1001", "pub-1")

    assert repo.list_publishers_calls == 1
    assert len(first) == 1
    assert len(second) == 1
    assert first[0]["publisher_id"] == "pub-1"
