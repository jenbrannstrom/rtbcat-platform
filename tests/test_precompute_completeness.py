"""Precompute completeness tests (C-PRE-002 + C-PRE-003).

Environment-independent: uses in-memory stubs that mirror the gap-fill
and Postgres-fallback SQL logic added to home_precompute.py and
config_precompute.py.
"""

from __future__ import annotations

from typing import Any, Optional

import pytest


# ---------------------------------------------------------------------------
# In-memory table stubs
# ---------------------------------------------------------------------------

class StubTables:
    """Simulates Postgres tables for precompute completeness testing."""

    def __init__(self):
        # buyer_seats: list of dicts {buyer_id, bidder_id, active}
        self.buyer_seats: list[dict[str, Any]] = []
        # pretargeting_configs: list of dicts {bidder_id, billing_id, display_name, state}
        self.pretargeting_configs: list[dict[str, Any]] = []
        # home_config_daily: keyed by (metric_date, buyer_account_id, billing_id)
        self.home_config_daily: dict[tuple[str, str, str], dict[str, Any]] = {}
        # config_publisher_daily: keyed by (metric_date, buyer_account_id, billing_id, publisher_id)
        self.config_publisher_daily: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        # rtb_daily: list of row dicts
        self.rtb_daily: list[dict[str, Any]] = []

    # -- Helpers to populate BQ-sourced data (simulates the primary INSERT) --

    def insert_home_config(
        self,
        metric_date: str,
        buyer_account_id: str,
        billing_id: str,
        reached_queries: int = 1000,
        impressions: int = 500,
    ) -> None:
        key = (metric_date, buyer_account_id, billing_id)
        self.home_config_daily[key] = {
            "metric_date": metric_date,
            "buyer_account_id": buyer_account_id,
            "billing_id": billing_id,
            "reached_queries": reached_queries,
            "impressions": impressions,
            "bids_in_auction": 0,
            "auctions_won": 0,
        }

    def insert_config_publisher(
        self,
        metric_date: str,
        buyer_account_id: str,
        billing_id: str,
        publisher_id: str,
        reached_queries: int = 100,
    ) -> None:
        key = (metric_date, buyer_account_id, billing_id, publisher_id)
        self.config_publisher_daily[key] = {
            "metric_date": metric_date,
            "buyer_account_id": buyer_account_id,
            "billing_id": billing_id,
            "publisher_id": publisher_id,
            "publisher_name": f"pub-{publisher_id}",
            "reached_queries": reached_queries,
            "impressions": 50,
            "spend_micros": 0,
        }

    # -- Gap-fill logic (mirrors the SQL in home_precompute.py) --

    def gap_fill_home_config(
        self,
        date_list: list[str],
        buyer_account_id: Optional[str] = None,
    ) -> int:
        """Simulate the INSERT ... ON CONFLICT DO NOTHING gap-fill."""
        count = 0
        active_bidders = {
            bs["bidder_id"]
            for bs in self.buyer_seats
            if bs["active"]
        }
        for pc in self.pretargeting_configs:
            bid = pc["bidder_id"]
            if bid not in active_bidders:
                continue
            if buyer_account_id and bid != buyer_account_id:
                continue
            if pc["state"] != "ACTIVE":
                continue
            billing = pc.get("billing_id")
            if not billing:
                continue
            for d in date_list:
                key = (d, bid, billing)
                if key not in self.home_config_daily:
                    self.home_config_daily[key] = {
                        "metric_date": d,
                        "buyer_account_id": bid,
                        "billing_id": billing,
                        "reached_queries": 0,
                        "impressions": 0,
                        "bids_in_auction": 0,
                        "auctions_won": 0,
                    }
                    count += 1
        return count

    # -- Postgres fallback for config_publisher_daily --

    def fallback_config_publisher(
        self,
        date_list: list[str],
        buyer_account_id: Optional[str] = None,
    ) -> int:
        """Simulate the INSERT ... ON CONFLICT DO NOTHING fallback from rtb_daily."""
        # Group rtb_daily rows by (metric_date, buyer, billing, publisher)
        agg: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        for row in self.rtb_daily:
            md = str(row.get("metric_date", ""))
            if md not in date_list:
                continue
            buyer = row.get("buyer_account_id", "")
            billing = row.get("billing_id", "")
            pub = row.get("publisher_id", "")
            if not buyer or not billing or not pub:
                continue
            if buyer_account_id and buyer != buyer_account_id:
                continue
            key = (md, buyer, billing, pub)
            if key not in agg:
                agg[key] = {
                    "metric_date": md,
                    "buyer_account_id": buyer,
                    "billing_id": billing,
                    "publisher_id": pub,
                    "publisher_name": row.get("publisher_name", ""),
                    "reached_queries": 0,
                    "impressions": 0,
                    "spend_micros": 0,
                }
            agg[key]["reached_queries"] += row.get("reached_queries", 0)
            agg[key]["impressions"] += row.get("impressions", 0)
            agg[key]["spend_micros"] += row.get("spend_micros", 0)

        count = 0
        for key, vals in agg.items():
            if key not in self.config_publisher_daily:
                self.config_publisher_daily[key] = vals
                count += 1
        return count


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_active_buyer(tables: StubTables, buyer_id: str) -> None:
    tables.buyer_seats.append({
        "buyer_id": buyer_id,
        "bidder_id": buyer_id,
        "active": True,
    })


def _add_config(
    tables: StubTables,
    bidder_id: str,
    billing_id: str,
    display_name: str = "",
    state: str = "ACTIVE",
) -> None:
    tables.pretargeting_configs.append({
        "bidder_id": bidder_id,
        "billing_id": billing_id,
        "display_name": display_name or f"Config {billing_id}",
        "state": state,
    })


# ---------------------------------------------------------------------------
# Test 1: Active config with traffic appears from BQ; zero-traffic config
#          appears via gap-fill
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gap_fill_creates_zero_rows_for_active_configs():
    tables = StubTables()
    _setup_active_buyer(tables, "buyer-1")
    _add_config(tables, "buyer-1", "cfg-A")
    _add_config(tables, "buyer-1", "cfg-B")

    # BQ only produced data for cfg-A
    tables.insert_home_config("2026-02-10", "buyer-1", "cfg-A", reached_queries=5000)

    # Gap fill
    filled = tables.gap_fill_home_config(["2026-02-10"])
    assert filled == 1  # cfg-B was missing

    # Both configs now have rows
    assert ("2026-02-10", "buyer-1", "cfg-A") in tables.home_config_daily
    assert ("2026-02-10", "buyer-1", "cfg-B") in tables.home_config_daily

    # cfg-A retains real traffic (ON CONFLICT DO NOTHING)
    assert tables.home_config_daily[("2026-02-10", "buyer-1", "cfg-A")]["reached_queries"] == 5000

    # cfg-B is zero-filled
    assert tables.home_config_daily[("2026-02-10", "buyer-1", "cfg-B")]["reached_queries"] == 0


# ---------------------------------------------------------------------------
# Test 2: Zero-traffic active config is visible (critical per user request)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_zero_traffic_active_config_visible_in_precompute():
    """A config with zero traffic must still appear in home_config_daily
    after gap-fill, making it visible in the dashboard/API."""
    tables = StubTables()
    _setup_active_buyer(tables, "buyer-1")
    _add_config(tables, "buyer-1", "zero-traffic-cfg", "IDN_Banner_Instl")

    # No BQ data at all for this config
    assert len(tables.home_config_daily) == 0

    dates = ["2026-02-08", "2026-02-09", "2026-02-10"]
    filled = tables.gap_fill_home_config(dates)
    assert filled == 3  # one zero-row per date

    for d in dates:
        key = (d, "buyer-1", "zero-traffic-cfg")
        assert key in tables.home_config_daily
        row = tables.home_config_daily[key]
        assert row["reached_queries"] == 0
        assert row["impressions"] == 0
        assert row["buyer_account_id"] == "buyer-1"
        assert row["billing_id"] == "zero-traffic-cfg"


# ---------------------------------------------------------------------------
# Test 3: Publisher fallback fills from rtb_daily when BQ self-join missed
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_publisher_fallback_fills_from_rtb_daily():
    tables = StubTables()
    _setup_active_buyer(tables, "buyer-1")

    # BQ self-join produced nothing (publisher_id sparse in BQ)
    assert len(tables.config_publisher_daily) == 0

    # Local rtb_daily has rows with both billing_id and publisher_id
    tables.rtb_daily.append({
        "metric_date": "2026-02-10",
        "buyer_account_id": "buyer-1",
        "billing_id": "cfg-A",
        "publisher_id": "pub-123",
        "publisher_name": "Publisher 123",
        "reached_queries": 800,
        "impressions": 200,
        "spend_micros": 50000,
    })
    tables.rtb_daily.append({
        "metric_date": "2026-02-10",
        "buyer_account_id": "buyer-1",
        "billing_id": "cfg-A",
        "publisher_id": "pub-456",
        "publisher_name": "Publisher 456",
        "reached_queries": 400,
        "impressions": 100,
        "spend_micros": 25000,
    })

    filled = tables.fallback_config_publisher(["2026-02-10"])
    assert filled == 2

    assert ("2026-02-10", "buyer-1", "cfg-A", "pub-123") in tables.config_publisher_daily
    assert ("2026-02-10", "buyer-1", "cfg-A", "pub-456") in tables.config_publisher_daily
    assert tables.config_publisher_daily[
        ("2026-02-10", "buyer-1", "cfg-A", "pub-123")
    ]["reached_queries"] == 800


# ---------------------------------------------------------------------------
# Test 4: Multi-buyer isolation — no cross-buyer leakage
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_multi_buyer_isolation():
    tables = StubTables()
    _setup_active_buyer(tables, "buyer-A")
    _setup_active_buyer(tables, "buyer-B")
    _add_config(tables, "buyer-A", "cfg-A1")
    _add_config(tables, "buyer-B", "cfg-B1")

    # BQ produced data for buyer-A only
    tables.insert_home_config("2026-02-10", "buyer-A", "cfg-A1", reached_queries=3000)

    # Gap fill scoped to buyer-A only
    filled_a = tables.gap_fill_home_config(["2026-02-10"], buyer_account_id="buyer-A")
    assert filled_a == 0  # buyer-A already has data

    # buyer-B config should NOT be filled when scoped to buyer-A
    assert ("2026-02-10", "buyer-B", "cfg-B1") not in tables.home_config_daily

    # Global gap fill fills buyer-B
    filled_all = tables.gap_fill_home_config(["2026-02-10"])
    assert filled_all == 1  # only buyer-B's cfg-B1
    assert ("2026-02-10", "buyer-B", "cfg-B1") in tables.home_config_daily

    # buyer-A's real data is unchanged
    assert tables.home_config_daily[("2026-02-10", "buyer-A", "cfg-A1")]["reached_queries"] == 3000


# ---------------------------------------------------------------------------
# Test 5: Null/empty billing_id configs are NOT gap-filled
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_null_empty_billing_id_excluded_from_gap_fill():
    tables = StubTables()
    _setup_active_buyer(tables, "buyer-1")
    _add_config(tables, "buyer-1", None, "Null billing config")        # billing_id=None
    _add_config(tables, "buyer-1", "", "Empty billing config")         # billing_id=''
    _add_config(tables, "buyer-1", "valid-cfg", "Valid config")        # normal

    filled = tables.gap_fill_home_config(["2026-02-10"])
    assert filled == 1  # only valid-cfg
    assert ("2026-02-10", "buyer-1", "valid-cfg") in tables.home_config_daily
    # No row with None or '' billing_id
    for key in tables.home_config_daily:
        assert key[2] is not None
        assert key[2] != ""


# ---------------------------------------------------------------------------
# Test 6: Idempotent rerun — no duplicate inflation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_idempotent_rerun_no_duplicates():
    tables = StubTables()
    _setup_active_buyer(tables, "buyer-1")
    _add_config(tables, "buyer-1", "cfg-A")
    _add_config(tables, "buyer-1", "cfg-B")

    tables.insert_home_config("2026-02-10", "buyer-1", "cfg-A", reached_queries=5000)

    # First gap fill
    filled_1 = tables.gap_fill_home_config(["2026-02-10"])
    assert filled_1 == 1
    total_1 = len(tables.home_config_daily)

    # Second gap fill — should be no-op
    filled_2 = tables.gap_fill_home_config(["2026-02-10"])
    assert filled_2 == 0
    assert len(tables.home_config_daily) == total_1

    # cfg-A still has original traffic
    assert tables.home_config_daily[("2026-02-10", "buyer-1", "cfg-A")]["reached_queries"] == 5000


# ---------------------------------------------------------------------------
# Test 7: Inactive buyer configs are NOT gap-filled
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_inactive_buyer_excluded_from_gap_fill():
    tables = StubTables()
    # active buyer
    _setup_active_buyer(tables, "buyer-active")
    _add_config(tables, "buyer-active", "cfg-active")
    # inactive buyer
    tables.buyer_seats.append({
        "buyer_id": "buyer-stale",
        "bidder_id": "buyer-stale",
        "active": False,
    })
    _add_config(tables, "buyer-stale", "cfg-stale")

    filled = tables.gap_fill_home_config(["2026-02-10"])
    assert filled == 1  # only buyer-active's config
    assert ("2026-02-10", "buyer-active", "cfg-active") in tables.home_config_daily
    assert ("2026-02-10", "buyer-stale", "cfg-stale") not in tables.home_config_daily


# ---------------------------------------------------------------------------
# Test 8: Publisher fallback ON CONFLICT DO NOTHING — BQ data wins
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_publisher_fallback_does_not_overwrite_bq_data():
    tables = StubTables()
    _setup_active_buyer(tables, "buyer-1")

    # BQ produced a row
    tables.insert_config_publisher(
        "2026-02-10", "buyer-1", "cfg-A", "pub-123", reached_queries=999
    )

    # Local rtb_daily has a row with the same key but different values
    tables.rtb_daily.append({
        "metric_date": "2026-02-10",
        "buyer_account_id": "buyer-1",
        "billing_id": "cfg-A",
        "publisher_id": "pub-123",
        "publisher_name": "different name",
        "reached_queries": 1,
        "impressions": 1,
        "spend_micros": 1,
    })

    filled = tables.fallback_config_publisher(["2026-02-10"])
    assert filled == 0  # no new row, BQ data preserved

    row = tables.config_publisher_daily[("2026-02-10", "buyer-1", "cfg-A", "pub-123")]
    assert row["reached_queries"] == 999  # BQ value, not rtb_daily value
