"""Cache behavior tests for PretargetingService list configs path."""

from __future__ import annotations

import pytest

from services.pretargeting_service import PretargetingService


class _StubPretargetingRepo:
    def __init__(self) -> None:
        self.list_calls = 0
        self.list_by_buyer_calls = 0
        self.list_history_calls = 0
        self.add_history_calls = 0
        self.rows: list[dict[str, object]] = [{"billing_id": "1001"}]
        self.history_rows: list[dict[str, object]] = [{"config_id": "cfg-1", "change_type": "update"}]

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


@pytest.mark.asyncio
async def test_list_configs_uses_ttl_cache_per_bidder() -> None:
    PretargetingService.clear_list_configs_cache()
    PretargetingService.clear_history_cache()
    repo = _StubPretargetingRepo()
    service = PretargetingService(repo=repo)

    first = await service.list_configs(bidder_id="bidder-1")
    first[0]["billing_id"] = "mutated-locally"
    second = await service.list_configs(bidder_id="bidder-1")

    assert repo.list_calls == 1
    assert second[0]["billing_id"] == "1001"


@pytest.mark.asyncio
async def test_save_config_invalidates_list_cache() -> None:
    PretargetingService.clear_list_configs_cache()
    PretargetingService.clear_history_cache()
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
    PretargetingService.clear_list_configs_cache()
    PretargetingService.clear_history_cache()
    repo = _StubPretargetingRepo()
    service = PretargetingService(repo=repo)

    first = await service.list_configs_for_buyer("buyer-1")
    first[0]["billing_id"] = "mutated-locally"
    second = await service.list_configs_for_buyer("buyer-1")

    assert repo.list_by_buyer_calls == 1
    assert second[0]["billing_id"] == "1001"


@pytest.mark.asyncio
async def test_list_configs_cache_is_scoped_by_limit() -> None:
    PretargetingService.clear_list_configs_cache()
    PretargetingService.clear_history_cache()
    repo = _StubPretargetingRepo()
    service = PretargetingService(repo=repo)

    await service.list_configs(bidder_id="bidder-1", limit=100)
    await service.list_configs(bidder_id="bidder-1", limit=200)

    assert repo.list_calls == 2


@pytest.mark.asyncio
async def test_list_configs_cache_is_scoped_by_summary_shape() -> None:
    PretargetingService.clear_list_configs_cache()
    PretargetingService.clear_history_cache()
    repo = _StubPretargetingRepo()
    service = PretargetingService(repo=repo)

    await service.list_configs(bidder_id="bidder-1", limit=100, summary_only=True)
    await service.list_configs(bidder_id="bidder-1", limit=100, summary_only=False)

    assert repo.list_calls == 2


@pytest.mark.asyncio
async def test_save_config_invalidates_buyer_scoped_list_cache() -> None:
    PretargetingService.clear_list_configs_cache()
    PretargetingService.clear_history_cache()
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
    PretargetingService.clear_list_configs_cache()
    PretargetingService.clear_history_cache()
    repo = _StubPretargetingRepo()
    service = PretargetingService(repo=repo)

    first = await service.list_history(config_id="cfg-1", days=30, limit=100)
    first[0]["change_type"] = "mutated-locally"
    second = await service.list_history(config_id="cfg-1", days=30, limit=100)

    assert repo.list_history_calls == 1
    assert second[0]["change_type"] == "update"


@pytest.mark.asyncio
async def test_add_history_invalidates_history_cache() -> None:
    PretargetingService.clear_list_configs_cache()
    PretargetingService.clear_history_cache()
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
