from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException

from services.agent_stats_service import AgentStatsService


_DEFAULT_BUYER = {
    "buyer_id": "buyer-1",
    "bidder_id": "bidder-1",
    "display_name": "Buyer One",
    "active": True,
    "last_synced": None,
}


class _StubRepo:
    def __init__(self, buyer: dict | None = _DEFAULT_BUYER, rows: list[dict] | None = None) -> None:
        self.buyer = buyer
        self.rows = rows or []
        self.row_calls: list[tuple] = []

    async def get_buyer(self, buyer_id: str):
        return self.buyer

    async def get_daily_spend_rows(self, buyer_id: str, start_date: date, end_date: date):
        self.row_calls.append((buyer_id, start_date, end_date))
        return self.rows


def _rows_for_two_days() -> list[dict]:
    return [
        {
            "metric_date": date(2026, 7, 1),
            "impressions": 4200,
            "clicks": 17,
            "spend_micros": 12_500_000,
            "source_row_count": 3,
            "app_count": 2,
            "billing_count": 1,
        },
        {
            "metric_date": date(2026, 7, 2),
            "impressions": 0,
            "clicks": 0,
            "spend_micros": 0,
            "source_row_count": 0,
            "app_count": 0,
            "billing_count": 0,
        },
    ]


@pytest.mark.asyncio
async def test_daily_spend_distinguishes_missing_from_present_and_totals() -> None:
    repo = _StubRepo(rows=_rows_for_two_days())
    service = AgentStatsService(repo=repo)

    payload = await service.get_daily_spend(
        buyer_id="buyer-1",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 2),
    )

    assert payload["period"] == {"start_date": "2026-07-01", "end_date": "2026-07-02", "days": 2}
    assert [row["source_status"] for row in payload["rows"]] == ["present", "missing"]
    assert payload["rows"][0]["buyer_account_id"] == "buyer-1"
    assert payload["rows"][0]["clicks"] == 17
    assert payload["summary"] == {
        "requested_days": 2,
        "days_with_source_rows": 1,
        "total_impressions": 4200,
        "total_clicks": 17,
        "total_spend_micros": 12_500_000,
    }
    assert payload["warnings"] == ["No RTBcat spend source rows found for 2026-07-02."]
    assert payload["data_source"]["table"] == "rtb_app_daily"
    assert repo.row_calls == [("buyer-1", date(2026, 7, 1), date(2026, 7, 2))]


@pytest.mark.asyncio
async def test_daily_spend_include_empty_false_drops_missing_days() -> None:
    repo = _StubRepo(rows=_rows_for_two_days())
    service = AgentStatsService(repo=repo)

    payload = await service.get_daily_spend(
        buyer_id="buyer-1",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 2),
        include_empty=False,
    )

    assert [row["metric_date"] for row in payload["rows"]] == ["2026-07-01"]
    # Missing days stay visible in summary/warnings even when rows are dropped.
    assert payload["summary"]["days_with_source_rows"] == 1
    assert payload["warnings"] == ["No RTBcat spend source rows found for 2026-07-02."]


@pytest.mark.asyncio
async def test_daily_spend_rejects_end_before_start() -> None:
    service = AgentStatsService(repo=_StubRepo())

    with pytest.raises(HTTPException) as exc_info:
        await service.get_daily_spend(
            buyer_id="buyer-1",
            start_date=date(2026, 7, 2),
            end_date=date(2026, 7, 1),
        )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_daily_spend_rejects_ranges_over_90_days() -> None:
    service = AgentStatsService(repo=_StubRepo())

    with pytest.raises(HTTPException) as exc_info:
        await service.get_daily_spend(
            buyer_id="buyer-1",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 4, 30),
        )

    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_daily_spend_unknown_buyer_returns_404() -> None:
    service = AgentStatsService(repo=_StubRepo(buyer=None))

    with pytest.raises(HTTPException) as exc_info:
        await service.get_daily_spend(
            buyer_id="nope",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 1),
        )

    assert exc_info.value.status_code == 404
