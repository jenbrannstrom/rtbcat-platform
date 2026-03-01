"""Cache behavior tests for EndpointsService read paths."""

from __future__ import annotations

import pytest

from services.endpoints_service import EndpointsService


class _StubEndpointsRepo:
    def __init__(self) -> None:
        self.list_calls = 0
        self.current_qps_calls = 0
        self.upsert_calls = 0
        self.refresh_calls = 0
        self.rows: list[dict[str, object]] = [{"endpoint_id": "ep-1", "maximum_qps": 10}]
        self.current_qps_value = 12.5

    async def upsert_endpoints(self, bidder_id: str, endpoints: list[dict[str, object]]) -> int:
        self.upsert_calls += 1
        return len(endpoints)

    async def list_endpoints(self, bidder_id: str | None = None) -> list[dict[str, object]]:
        self.list_calls += 1
        return [dict(row) for row in self.rows]

    async def get_current_qps(self, bidder_id: str | None = None) -> float:
        self.current_qps_calls += 1
        return float(self.current_qps_value)

    async def refresh_endpoints_current(
        self,
        lookback_days: int = 7,
        bidder_id: str | None = None,
    ) -> int:
        self.refresh_calls += 1
        return 1


@pytest.mark.asyncio
async def test_list_endpoints_uses_ttl_cache() -> None:
    EndpointsService.clear_caches()
    repo = _StubEndpointsRepo()
    service = EndpointsService(repo=repo)

    first = await service.list_endpoints("bidder-1")
    first[0]["endpoint_id"] = "mutated-locally"
    second = await service.list_endpoints("bidder-1")

    assert repo.list_calls == 1
    assert second[0]["endpoint_id"] == "ep-1"


@pytest.mark.asyncio
async def test_get_current_qps_uses_ttl_cache() -> None:
    EndpointsService.clear_caches()
    repo = _StubEndpointsRepo()
    service = EndpointsService(repo=repo)

    first = await service.get_current_qps("bidder-1")
    assert first == 12.5
    repo.current_qps_value = 99.0
    second = await service.get_current_qps("bidder-1")

    assert repo.current_qps_calls == 1
    assert second == 12.5


@pytest.mark.asyncio
async def test_sync_endpoints_invalidates_caches() -> None:
    EndpointsService.clear_caches()
    repo = _StubEndpointsRepo()
    service = EndpointsService(repo=repo)

    await service.list_endpoints("bidder-1")
    await service.get_current_qps("bidder-1")
    assert repo.list_calls == 1
    assert repo.current_qps_calls == 1

    repo.rows = [{"endpoint_id": "ep-2", "maximum_qps": 20}]
    repo.current_qps_value = 55.0
    await service.sync_endpoints("bidder-1", [{"endpointId": "ep-2"}])

    rows = await service.list_endpoints("bidder-1")
    qps = await service.get_current_qps("bidder-1")

    assert repo.upsert_calls == 1
    assert repo.list_calls == 2
    assert repo.current_qps_calls == 2
    assert rows[0]["endpoint_id"] == "ep-2"
    assert qps == 55.0


@pytest.mark.asyncio
async def test_refresh_endpoints_current_invalidates_current_qps_cache() -> None:
    EndpointsService.clear_caches()
    repo = _StubEndpointsRepo()
    service = EndpointsService(repo=repo)

    await service.get_current_qps("bidder-1")
    assert repo.current_qps_calls == 1

    repo.current_qps_value = 77.0
    await service.refresh_endpoints_current(lookback_days=7, bidder_id="bidder-1")
    refreshed = await service.get_current_qps("bidder-1")

    assert repo.refresh_calls == 1
    assert repo.current_qps_calls == 2
    assert refreshed == 77.0
