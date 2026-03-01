"""Cache behavior tests for PretargetingService list configs path."""

from __future__ import annotations

import pytest

from services.pretargeting_service import PretargetingService


class _StubPretargetingRepo:
    def __init__(self) -> None:
        self.list_calls = 0
        self.rows: list[dict[str, object]] = [{"billing_id": "1001"}]

    async def list_configs(self, bidder_id: str | None = None) -> list[dict[str, object]]:
        self.list_calls += 1
        return [dict(row) for row in self.rows]

    async def save_config(self, _config: dict[str, object]) -> None:
        return None

    async def update_user_name(self, _billing_id: str, _user_name: str | None) -> int:
        return 1

    async def update_state(self, _billing_id: str, _state: str) -> int:
        return 1


@pytest.mark.asyncio
async def test_list_configs_uses_ttl_cache_per_bidder() -> None:
    PretargetingService.clear_list_configs_cache()
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
    repo = _StubPretargetingRepo()
    service = PretargetingService(repo=repo)

    await service.list_configs(bidder_id="bidder-1")
    assert repo.list_calls == 1

    repo.rows = [{"billing_id": "2002"}]
    await service.save_config({"config_id": "cfg-1", "bidder_id": "bidder-1"})
    refreshed = await service.list_configs(bidder_id="bidder-1")

    assert repo.list_calls == 2
    assert refreshed[0]["billing_id"] == "2002"
