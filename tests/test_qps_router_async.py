"""Async execution guards for blocking QPS analyzers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from api.routers.analytics import qps


@pytest.mark.asyncio
async def test_qps_summary_offloads_and_parallelizes_analyzers(monkeypatch) -> None:
    calls: list[tuple[str, int, dict]] = []

    async def resolve_buyer_id(buyer_id, *, store, user):
        return buyer_id

    async def get_billing_ids(buyer_id):
        return ["billing-1"]

    class SizeAnalyzer:
        def __init__(self, _dsn: str):
            pass

        def analyze(self, days: int, **kwargs):
            calls.append(("size", days, kwargs))
            return SimpleNamespace(
                coverage_rate=80.0,
                sizes_with_creatives=8,
                sizes_without_creatives=2,
                wasted_qps=1.5,
                gaps=[],
            )

    class GeoAnalyzer:
        def __init__(self, _dsn: str):
            pass

        def analyze(self, days: int, **kwargs):
            calls.append(("geo", days, kwargs))
            return SimpleNamespace(
                total_geos=4,
                geos_to_exclude=1,
                geos_to_monitor=1,
                estimated_waste_pct=5.0,
                wasted_spend_usd=9.0,
            )

    monkeypatch.setattr(qps, "resolve_buyer_id", resolve_buyer_id)
    monkeypatch.setattr(qps, "get_valid_billing_ids_for_buyer", get_billing_ids)
    monkeypatch.setattr(qps, "SizeCoverageAnalyzer", SizeAnalyzer)
    monkeypatch.setattr(qps, "GeoWasteAnalyzer", GeoAnalyzer)
    monkeypatch.setenv("POSTGRES_SERVING_DSN", "postgresql://unused")

    payload = await qps.get_qps_summary(
        days=90,
        buyer_id="buyer-1",
        store=object(),
        user=object(),
    )

    assert payload["size_coverage"]["coverage_rate_pct"] == 80.0
    assert payload["geo_efficiency"]["geos_analyzed"] == 4
    assert {call[0] for call in calls} == {"size", "geo"}
    assert all(call[1] == 90 for call in calls)
    assert all(call[2]["billing_ids"] == ["billing-1"] for call in calls)
