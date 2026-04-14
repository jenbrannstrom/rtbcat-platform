"""Regression tests for creative performance provenance in router helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("fastapi")

from api.routers import performance as performance_router
from api.schemas.performance import BatchPerformanceRequest


class _StubRepo:
    def __init__(self, summaries: dict[str, dict]) -> None:
        self.summaries = summaries

    async def get_creative_summaries(
        self,
        creative_ids: list[str],
        days: int = 30,
        buyer_id_filter: str | None = None,
    ) -> dict[str, dict]:
        del creative_ids, days, buyer_id_filter
        return self.summaries


class _StubStore:
    def __init__(self, creative_id: str = "creative-1", buyer_id: str = "buyer-1") -> None:
        self._creative = SimpleNamespace(id=creative_id, buyer_id=buyer_id)

    async def get_creative(self, creative_id: str):
        assert creative_id == self._creative.id
        return self._creative

    async def get_creative_performance_summary(self, creative_id: str, days: int = 30) -> dict:
        del creative_id, days
        return {}


@pytest.mark.asyncio
async def test_batch_performance_preserves_click_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _StubRepo(
        {
            "creative-1": {
                "total_impressions": 2145062,
                "total_clicks": 0,
                "total_spend_micros": 42000000,
                "avg_cpm_micros": 19579,
                "avg_cpc_micros": None,
                "ctr_percent": None,
                "days_with_data": 7,
                "metric_source": "config_creative_daily",
                "clicks_available": False,
            }
        }
    )
    monkeypatch.setattr(
        performance_router,
        "get_allowed_buyer_ids",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(performance_router, "_get_creative_perf_repo", lambda: repo)

    payload = await performance_router.get_batch_performance(
        BatchPerformanceRequest(creative_ids=["creative-1"], period="7d"),
        store=_StubStore(),
        user=SimpleNamespace(id="user-1"),
    )

    summary = payload.performance["creative-1"]
    assert summary.metric_source == "config_creative_daily"
    assert summary.clicks_available is False
    assert summary.total_clicks == 0


@pytest.mark.asyncio
async def test_batch_performance_keeps_zero_ctr(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = _StubRepo(
        {
            "creative-1": {
                "total_impressions": 5000,
                "total_clicks": 0,
                "total_spend_micros": 2000000,
                "avg_cpm_micros": 400000,
                "avg_cpc_micros": None,
                "ctr_percent": 0.0,
                "days_with_data": 3,
                "metric_source": "rtb_daily",
                "clicks_available": True,
            }
        }
    )
    monkeypatch.setattr(
        performance_router,
        "get_allowed_buyer_ids",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(performance_router, "_get_creative_perf_repo", lambda: repo)

    payload = await performance_router.get_batch_performance(
        BatchPerformanceRequest(creative_ids=["creative-1"], period="7d"),
        store=_StubStore(),
        user=SimpleNamespace(id="user-1"),
    )

    assert payload.performance["creative-1"].ctr_percent == 0.0


@pytest.mark.asyncio
async def test_single_creative_performance_preserves_repo_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _StubRepo(
        {
            "creative-1": {
                "total_impressions": 123,
                "total_clicks": 0,
                "total_spend_micros": 456,
                "avg_cpm_micros": 3707,
                "avg_cpc_micros": None,
                "ctr_percent": 0.0,
                "days_with_data": 2,
                "metric_source": "config_creative_daily",
                "clicks_available": False,
            }
        }
    )
    monkeypatch.setattr(
        performance_router,
        "get_allowed_buyer_ids",
        AsyncMock(return_value=None),
    )
    monkeypatch.setattr(performance_router, "_get_creative_perf_repo", lambda: repo)

    payload = await performance_router.get_creative_performance(
        "creative-1",
        days=7,
        store=_StubStore(),
        user=SimpleNamespace(id="user-1"),
    )

    assert payload.metric_source == "config_creative_daily"
    assert payload.clicks_available is False
    assert payload.ctr_percent == 0.0
