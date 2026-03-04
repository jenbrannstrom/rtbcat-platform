"""Exception observability fallback tests for CreativePerformanceService."""

from __future__ import annotations

import logging

import pytest

from services.creative_performance_service import CreativePerformanceService


class _FailingRepo:
    async def get_active_creative_ids(self, creative_ids: list[str], days: int):
        del creative_ids, days
        raise RuntimeError("active ids failed")

    async def get_rtb_daily_perf(self, creative_ids: list[str], days: int):
        del creative_ids, days
        raise RuntimeError("perf failed")

    async def get_primary_countries(self, creative_ids: list[str], days: int):
        del creative_ids, days
        raise RuntimeError("countries failed")

    async def get_country_breakdown(self, creative_id: str, days: int):
        del creative_id, days
        raise RuntimeError("breakdown failed")


@pytest.mark.asyncio
async def test_get_active_creative_ids_logs_and_falls_back(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = CreativePerformanceService(repo=_FailingRepo())
    with caplog.at_level(logging.DEBUG):
        result = await service.get_active_creative_ids(["cr-1"], 7)
    assert result == set()
    assert "Could not filter active creatives" in caplog.text


@pytest.mark.asyncio
async def test_get_waste_flags_logs_and_falls_back(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = CreativePerformanceService(repo=_FailingRepo())
    with caplog.at_level(logging.DEBUG):
        result = await service.get_waste_flags(
            creative_ids=["cr-1"],
            thumbnail_statuses={},
            days=7,
        )
    assert result["cr-1"]["broken_video"] is False
    assert result["cr-1"]["zero_engagement"] is False
    assert "Could not fetch performance data" in caplog.text


@pytest.mark.asyncio
async def test_get_primary_countries_logs_and_falls_back(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = CreativePerformanceService(repo=_FailingRepo())
    with caplog.at_level(logging.DEBUG):
        result = await service.get_primary_countries(["cr-1"], 7)
    assert result == {}
    assert "Could not fetch country data" in caplog.text


@pytest.mark.asyncio
async def test_get_country_breakdown_logs_and_falls_back(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = CreativePerformanceService(repo=_FailingRepo())
    with caplog.at_level(logging.DEBUG):
        result = await service.get_country_breakdown("cr-1", 7)
    assert result == []
    assert "Could not fetch country breakdown" in caplog.text
