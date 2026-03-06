"""Cache behavior tests for live RTB endpoints route fetches."""

from __future__ import annotations

import sys
import types

import pytest

# Match suite behavior in lightweight environments.
pytest.importorskip("fastapi")

# Allow importing router module in environments without optional Google deps.
if "collectors" not in sys.modules:
    fake_collectors = types.ModuleType("collectors")
    fake_collectors.EndpointsClient = object
    sys.modules["collectors"] = fake_collectors

from api.routers.settings import endpoints as endpoints_router


class _StubEndpointsService:
    def __init__(self) -> None:
        self.sync_calls = 0

    async def sync_endpoints(self, bidder_id: str, endpoints: list[dict]) -> int:
        self.sync_calls += 1
        return len(endpoints)


@pytest.mark.asyncio
async def test_live_endpoint_fetch_reuses_cache_within_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    endpoints_router._invalidate_live_endpoints_cache()
    monkeypatch.setattr(endpoints_router, "_LIVE_ENDPOINTS_CACHE_TTL_SECONDS", 60.0)

    class _FakeClient:
        calls = 0

        def __init__(self, credentials_path: str | None, account_id: str) -> None:
            self.credentials_path = credentials_path
            self.account_id = account_id

        async def list_endpoints(self) -> list[dict]:
            type(self).calls += 1
            return [
                {
                    "endpointId": "ep-1",
                    "url": "https://bid.example.com",
                    "maximumQps": 100,
                }
            ]

    monkeypatch.setattr(endpoints_router, "EndpointsClient", _FakeClient)
    service = _StubEndpointsService()

    first = await endpoints_router._get_live_endpoints_cached(
        bidder_id="bidder-1",
        creds_path="/tmp/credentials.json",
        endpoint_service=service,
    )
    second = await endpoints_router._get_live_endpoints_cached(
        bidder_id="bidder-1",
        creds_path="/tmp/credentials.json",
        endpoint_service=service,
    )

    assert _FakeClient.calls == 1
    assert service.sync_calls == 1
    assert first == second


@pytest.mark.asyncio
async def test_live_endpoint_cache_is_scoped_per_bidder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    endpoints_router._invalidate_live_endpoints_cache()
    monkeypatch.setattr(endpoints_router, "_LIVE_ENDPOINTS_CACHE_TTL_SECONDS", 60.0)

    class _FakeClient:
        calls = 0

        def __init__(self, credentials_path: str | None, account_id: str) -> None:
            self.account_id = account_id

        async def list_endpoints(self) -> list[dict]:
            type(self).calls += 1
            return [{"endpointId": f"ep-{self.account_id}", "url": "https://bid.example.com"}]

    monkeypatch.setattr(endpoints_router, "EndpointsClient", _FakeClient)
    service = _StubEndpointsService()

    bidder1 = await endpoints_router._get_live_endpoints_cached(
        bidder_id="bidder-1",
        creds_path=None,
        endpoint_service=service,
    )
    bidder2 = await endpoints_router._get_live_endpoints_cached(
        bidder_id="bidder-2",
        creds_path=None,
        endpoint_service=service,
    )

    assert _FakeClient.calls == 2
    assert service.sync_calls == 2
    assert bidder1[0]["endpointId"] == "ep-bidder-1"
    assert bidder2[0]["endpointId"] == "ep-bidder-2"
