"""Tests for /analytics/home/configs window fallback behavior."""

from __future__ import annotations

import pytest

from services.home_analytics_service import HomeAnalyticsService


class StubHomeConfigRepo:
    """Repo stub for home config fallback tests."""

    def __init__(self, rows_by_days: dict[int, list[dict]]) -> None:
        self.rows_by_days = rows_by_days
        self.days_requested: list[int] = []

    async def get_config_rows(self, days: int, _buyer_id: str | None) -> list[dict]:
        self.days_requested.append(days)
        return self.rows_by_days.get(days, [])


@pytest.mark.asyncio
async def test_home_configs_fall_back_to_30d_when_7d_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = StubHomeConfigRepo(
        rows_by_days={
            30: [
                {
                    "billing_id": "cfg-1",
                    "total_reached": 1200,
                    "total_impressions": 300,
                    "total_bids_in_auction": 500,
                    "total_auctions_won": 240,
                }
            ]
        }
    )
    service = HomeAnalyticsService(repo=repo)

    async def stub_status(
        _table_name: str,
        days: int,
        filters: list[str] | None = None,
        params: list[str] | None = None,
    ) -> dict:
        del filters, params
        if days == 7:
            return {"table": "pretarg_daily", "exists": True, "has_rows": False, "row_count": 0}
        if days == 30:
            return {"table": "pretarg_daily", "exists": True, "has_rows": True, "row_count": 12}
        return {"table": "pretarg_daily", "exists": True, "has_rows": False, "row_count": 0}

    monkeypatch.setattr("services.home_analytics_service._get_precompute_status", stub_status)

    payload = await service.get_config_payload(days=7, buyer_id="1487810529")

    assert repo.days_requested == [30]
    assert payload["data_state"] == "degraded"
    assert payload["fallback_applied"] is True
    assert payload["fallback_reason"] == "no_rows_7d_used_30d"
    assert payload["requested_days"] == 7
    assert payload["effective_days"] == 30
    assert len(payload["configs"]) == 1
    assert payload["configs"][0]["billing_id"] == "cfg-1"


@pytest.mark.asyncio
async def test_home_configs_no_fallback_when_7d_has_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    repo = StubHomeConfigRepo(
        rows_by_days={
            7: [
                {
                    "billing_id": "cfg-2",
                    "total_reached": 500,
                    "total_impressions": 125,
                    "total_bids_in_auction": 200,
                    "total_auctions_won": 80,
                }
            ]
        }
    )
    service = HomeAnalyticsService(repo=repo)

    async def stub_status(
        _table_name: str,
        _days: int,
        filters: list[str] | None = None,
        params: list[str] | None = None,
    ) -> dict:
        del filters, params
        return {"table": "pretarg_daily", "exists": True, "has_rows": True, "row_count": 4}

    monkeypatch.setattr("services.home_analytics_service._get_precompute_status", stub_status)

    payload = await service.get_config_payload(days=7, buyer_id="1487810529")

    assert repo.days_requested == [7]
    assert payload["data_state"] == "healthy"
    assert payload["fallback_applied"] is False
    assert payload["fallback_reason"] is None
    assert payload["requested_days"] == 7
    assert payload["effective_days"] == 7
    assert len(payload["configs"]) == 1
    assert payload["configs"][0]["billing_id"] == "cfg-2"
