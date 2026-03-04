"""Exception observability fallback tests for AnalyticsService."""

from __future__ import annotations

import logging

import pytest

from services.analytics_service import AnalyticsService


class _FailingCurrentBidderRepo:
    async def get_current_bidder_id(self) -> str | None:
        raise RuntimeError("db unavailable")


class _FailingBillingScopeRepo:
    async def get_bidder_id_for_buyer(self, buyer_id: str) -> str | None:
        del buyer_id
        raise RuntimeError("lookup failed")

    async def get_all_billing_ids(self) -> list[str]:
        return []


@pytest.mark.asyncio
async def test_get_current_bidder_id_logs_warning_on_repo_failure(caplog: pytest.LogCaptureFixture) -> None:
    service = AnalyticsService(repo=_FailingCurrentBidderRepo())

    with caplog.at_level(logging.WARNING):
        result = await service.get_current_bidder_id()

    assert result is None
    assert "Failed to resolve current bidder ID" in caplog.text


@pytest.mark.asyncio
async def test_get_valid_billing_ids_logs_warning_on_repo_failure(caplog: pytest.LogCaptureFixture) -> None:
    service = AnalyticsService(repo=_FailingCurrentBidderRepo())

    with caplog.at_level(logging.WARNING):
        result = await service.get_valid_billing_ids()

    assert result == []
    assert "Failed to resolve valid billing IDs" in caplog.text


@pytest.mark.asyncio
async def test_get_valid_billing_ids_for_buyer_logs_warning_on_repo_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = AnalyticsService(repo=_FailingBillingScopeRepo())

    with caplog.at_level(logging.WARNING):
        result = await service.get_valid_billing_ids_for_buyer("buyer-1")

    assert result == []
    assert "Failed to get billing IDs for buyer scope" in caplog.text
