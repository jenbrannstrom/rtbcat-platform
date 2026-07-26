from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException

from services.agent_stats_service import AgentStatsService


_DEFAULT_BUYER = {
    "buyer_id": "buyer-1",
    "bidder_id": "bidder-1",
    "display_name": "Buyer One",
    "currency_code": "USD",
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
        "complete": False,
        "missing_dates": ["2026-07-02"],
        "latest_complete_date": "2026-07-01",
        "total_impressions": 4200,
        "total_clicks": 17,
        "total_spend_micros": 12_500_000,
    }
    assert payload["warnings"] == ["No RTBcat spend source rows found for 2026-07-02."]
    assert payload["data_source"]["table"] == "rtb_buyer_spend_daily"
    assert payload["buyer"]["currency"] == "USD"
    assert payload["data_source"]["currency"] == "USD"
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
async def test_daily_spend_labels_uplivo_as_eur() -> None:
    buyer = {
        **_DEFAULT_BUYER,
        "buyer_id": "8087233591",
        "display_name": "Tuky internet",
        "currency_code": "eur",
    }
    repo = _StubRepo(buyer=buyer, rows=[_rows_for_two_days()[0]])
    service = AgentStatsService(repo=repo)

    payload = await service.get_daily_spend(
        buyer_id="8087233591",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 1),
    )

    assert payload["buyer"]["currency"] == "EUR"
    assert payload["data_source"]["currency"] == "EUR"
    assert payload["summary"]["total_spend_micros"] == 12_500_000


class _StatsStubRepo(_StubRepo):
    async def get_funnel_totals(self, _buyer_id: str, _days: int):
        return {
            "start_date": date(2026, 7, 1),
            "end_date": date(2026, 7, 13),
            "reached_queries": 1000,
            "impressions": 100,
            "bids": 50,
            "successful_responses": 900,
            "bid_requests": 1000,
            "auctions_won": 10,
        }

    async def get_auction_totals(self, _buyer_id: str, _days: int):
        return {"bids_in_auction": 20, "auctions_won": 10}

    async def get_spend_totals(self, _buyer_id: str, _days: int):
        return {
            "start_date": date(2026, 7, 1),
            "end_date": date(2026, 7, 13),
            "impressions": 100,
            "clicks": 2,
            "spend_micros": 4_159_980_000,
            "app_count": 1,
            "billing_count": 1,
        }

    async def get_top_publishers(self, _buyer_id: str, _days: int, _limit: int):
        return []

    async def get_top_geos(self, _buyer_id: str, _days: int, _limit: int):
        return []

    async def get_top_configs(self, _buyer_id: str, _days: int, _limit: int):
        return []

    async def get_top_apps(self, _buyer_id: str, _days: int, _limit: int):
        return [
            {
                "app_name": "Example",
                "app_id": "example.app",
                "reached_queries": 100,
                "impressions": 100,
                "clicks": 2,
                "spend_micros": 1_500_000,
            }
        ]


@pytest.mark.asyncio
async def test_stats_summary_uses_buyer_currency_and_nulls_usd_aliases_for_eur() -> None:
    buyer = {
        **_DEFAULT_BUYER,
        "buyer_id": "8087233591",
        "display_name": "Tuky internet",
        "currency_code": "EUR",
    }
    service = AgentStatsService(repo=_StatsStubRepo(buyer=buyer))

    payload = await service.get_stats_summary(
        buyer_id="8087233591",
        days=14,
        top_limit=10,
    )

    assert payload["buyer"]["currency"] == "EUR"
    assert payload["totals"]["currency"] == "EUR"
    assert payload["totals"]["spend"] == 4159.98
    assert payload["totals"]["spend_usd"] is None
    assert payload["totals"]["avg_cpm_usd"] is None
    assert payload["top_apps"][0]["currency"] == "EUR"
    assert payload["top_apps"][0]["spend"] == 1.5
    assert payload["top_apps"][0]["spend_usd"] is None
    assert "EUR 4,159.98" in payload["email_summary"]["markdown"]
    assert "$" not in payload["email_summary"]["markdown"]


@pytest.mark.asyncio
async def test_stats_summary_keeps_usd_compatibility_aliases_for_usd_buyer() -> None:
    service = AgentStatsService(repo=_StatsStubRepo())

    payload = await service.get_stats_summary(
        buyer_id="buyer-1",
        days=14,
        top_limit=10,
    )

    assert payload["totals"]["currency"] == "USD"
    assert payload["totals"]["spend"] == 4159.98
    assert payload["totals"]["spend_usd"] == 4159.98
    assert payload["totals"]["avg_cpm_usd"] == payload["totals"]["avg_cpm"]
    assert "USD 4,159.98" in payload["email_summary"]["markdown"]


def _row(metric_date: date, *, present: bool) -> dict:
    return {
        "metric_date": metric_date,
        "impressions": 100 if present else 0,
        "clicks": 1 if present else 0,
        "spend_micros": 1_000_000 if present else 0,
        "source_row_count": 1 if present else 0,
        "app_count": 0,
        "billing_count": 0,
    }


async def _completeness_summary(present_by_day: list[bool]) -> dict:
    rows = [
        _row(date(2026, 7, day + 1), present=present)
        for day, present in enumerate(present_by_day)
    ]
    service = AgentStatsService(repo=_StubRepo(rows=rows))
    payload = await service.get_daily_spend(
        buyer_id="buyer-1",
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, len(present_by_day)),
    )
    return payload["summary"]


@pytest.mark.asyncio
async def test_daily_spend_summary_complete_when_full_range_present() -> None:
    summary = await _completeness_summary([True, True, True])

    assert summary["complete"] is True
    assert summary["missing_dates"] == []
    assert summary["latest_complete_date"] == "2026-07-03"


@pytest.mark.asyncio
async def test_daily_spend_summary_mid_range_hole_stops_latest_complete_date() -> None:
    summary = await _completeness_summary([True, False, True])

    assert summary["complete"] is False
    assert summary["missing_dates"] == ["2026-07-02"]
    assert summary["latest_complete_date"] == "2026-07-01"


@pytest.mark.asyncio
async def test_daily_spend_summary_missing_tail() -> None:
    summary = await _completeness_summary([True, True, False])

    assert summary["complete"] is False
    assert summary["missing_dates"] == ["2026-07-03"]
    assert summary["latest_complete_date"] == "2026-07-02"


@pytest.mark.asyncio
async def test_daily_spend_summary_missing_first_day_has_null_latest_complete_date() -> None:
    summary = await _completeness_summary([False, True, True])

    assert summary["complete"] is False
    assert summary["missing_dates"] == ["2026-07-01"]
    assert summary["latest_complete_date"] is None


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
