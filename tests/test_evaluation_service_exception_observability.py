"""Exception observability fallback tests for EvaluationService."""

from __future__ import annotations

import logging

import pytest

from services.evaluation_service import EvaluationService


class _RepoRaisesOnFiltered:
    async def get_filtered_bids_summary(self, days: int):
        del days
        raise RuntimeError("filtered query failed")


class _RepoRaisesOnFunnel:
    async def get_bid_funnel_metrics(self, days: int):
        del days
        raise RuntimeError("funnel query failed")


@pytest.mark.asyncio
async def test_analyze_filtered_bids_logs_warning_and_returns_empty(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = EvaluationService(repo=_RepoRaisesOnFiltered())
    with caplog.at_level(logging.WARNING):
        result = await service._analyze_filtered_bids(days=7)
    assert result == []
    assert "Evaluation service fallback triggered at analyze_filtered_bids" in caplog.text


@pytest.mark.asyncio
async def test_get_filtered_bids_summary_logs_warning_and_returns_empty(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = EvaluationService(repo=_RepoRaisesOnFiltered())
    with caplog.at_level(logging.WARNING):
        result = await service.get_filtered_bids_summary(days=14)
    assert result == []
    assert "Evaluation service fallback triggered at get_filtered_bids_summary" in caplog.text


@pytest.mark.asyncio
async def test_get_bid_funnel_logs_warning_and_returns_zero_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = EvaluationService(repo=_RepoRaisesOnFunnel())
    with caplog.at_level(logging.WARNING):
        result = await service.get_bid_funnel(days=7)
    assert result["bid_requests"] == 0
    assert result["impressions"] == 0
    assert "Evaluation service fallback triggered at get_bid_funnel" in caplog.text
