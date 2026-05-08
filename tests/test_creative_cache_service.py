import pytest

import services.creative_cache_service as creative_cache_service
from services.creative_cache_service import CreativeCacheService


@pytest.mark.asyncio
async def test_refresh_active_creatives_backfills_perf_only_creatives(monkeypatch) -> None:
    queries = []
    saved = []
    fetched = []

    async def fake_pg_query(sql: str, params: tuple):
        queries.append((sql, params))
        return [{"creative_id": "creative-1", "buyer_id": "buyer-1"}]

    class FakeStore:
        async def get_creative(self, creative_id: str):
            assert creative_id == "creative-1"
            return None

        async def save_creatives(self, creatives):
            saved.extend(creatives)

    class FakeClient:
        async def get_creative_by_id(self, creative_id: str, view: str, buyer_id: str):
            fetched.append((creative_id, view, buyer_id))
            return {
                "creativeId": creative_id,
                "creativeName": f"buyers/{buyer_id}/creatives/{creative_id}",
                "accountId": buyer_id,
                "buyerId": buyer_id,
                "format": "HTML",
                "html": {"width": 300, "height": 250},
            }

    monkeypatch.setattr(creative_cache_service, "pg_query", fake_pg_query)
    svc = CreativeCacheService(store=FakeStore())

    async def fake_resolve_live_client(creative):
        assert creative.id == "creative-1"
        assert creative.buyer_id == "buyer-1"
        return FakeClient()

    monkeypatch.setattr(svc, "resolve_live_client", fake_resolve_live_client)

    result = await svc.refresh_active_creatives(
        days=7,
        limit=10,
        include_html_thumbnails=False,
    )

    assert "FROM rtb_daily" in queries[0][0]
    assert fetched == [("creative-1", "FULL", "buyer-1")]
    assert result.scanned == 1
    assert result.refreshed == 1
    assert result.skipped == 0
    assert saved[0].id == "creative-1"
    assert saved[0].buyer_id == "buyer-1"
