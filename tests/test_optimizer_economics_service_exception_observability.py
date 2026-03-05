"""Exception observability fallback tests for OptimizerEconomicsService."""

from __future__ import annotations

import logging
from datetime import date

import pytest

import services.optimizer_economics_service as optimizer_economics_service
from services.optimizer_economics_service import OptimizerEconomicsService


@pytest.mark.asyncio
async def test_fetch_daily_totals_logs_warning_and_returns_empty_on_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def _raise(*_args, **_kwargs):
        raise RuntimeError("daily query failed")

    monkeypatch.setattr(optimizer_economics_service, "pg_query_one_with_timeout", _raise)
    service = OptimizerEconomicsService()

    with caplog.at_level(logging.WARNING):
        result = await service._fetch_daily_totals(
            buyer_id="1111111111",
            start=date(2026, 2, 1),
            end=date(2026, 2, 7),
            billing_id="999999999999",
        )

    assert result == {}
    assert "daily totals query failed" in caplog.text.lower()


@pytest.mark.asyncio
async def test_fetch_quality_totals_logs_warning_and_returns_empty_on_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def _raise(*_args, **_kwargs):
        raise RuntimeError("quality query failed")

    monkeypatch.setattr(optimizer_economics_service, "pg_query_one_with_timeout", _raise)
    service = OptimizerEconomicsService()

    with caplog.at_level(logging.WARNING):
        result = await service._fetch_quality_totals(
            buyer_id="1111111111",
            start=date(2026, 2, 1),
            end=date(2026, 2, 7),
        )

    assert result == {}
    assert "quality totals query failed" in caplog.text.lower()


@pytest.mark.asyncio
async def test_get_assumed_value_logs_trend_fallbacks_and_returns_payload(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def _raise_timeout(*_args, **_kwargs):
        raise RuntimeError("trend query failed")

    async def _first_metric_date(*_args, **_kwargs):
        return {"first_metric_date": None}

    async def _quality_totals(*_args, **_kwargs):
        return {}

    monkeypatch.setattr(optimizer_economics_service, "pg_query_one_with_timeout", _raise_timeout)
    service = OptimizerEconomicsService()
    monkeypatch.setattr(service, "_fetch_first_metric_date", _first_metric_date)
    monkeypatch.setattr(service, "_fetch_quality_totals", _quality_totals)

    with caplog.at_level(logging.WARNING):
        payload = await service.get_assumed_value(
            buyer_id="1111111111",
            start_date="2026-02-01",
            end_date="2026-02-14",
            precomputed_totals={
                "spend_micros": 0,
                "impressions": 0,
                "clicks": 0,
                "reached_queries": 0,
                "bids_in_auction": 0,
                "auctions_won": 0,
            },
        )

    assert payload["buyer_id"] == "1111111111"
    assert "recent spend trend query failed" in caplog.text.lower()
    assert "previous spend trend query failed" in caplog.text.lower()
