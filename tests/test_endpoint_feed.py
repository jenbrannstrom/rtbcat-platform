"""Endpoint observed feed tests (C-EPT-001).

Environment-independent: uses in-memory stubs for EndpointsRepository
so no database connection is required.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import pytest

from services.endpoints_service import EndpointsService


# ---------------------------------------------------------------------------
# Stub EndpointsRepository with in-memory tables
# ---------------------------------------------------------------------------

class StubEndpointsRepo:
    """In-memory stub that simulates rtb_endpoints + rtb_endpoints_current + home_seat_daily."""

    def __init__(self):
        # rtb_endpoints: list of dicts
        self.endpoints: list[dict[str, Any]] = []
        # rtb_endpoints_current: keyed by (bidder_id, endpoint_id)
        self.current: dict[tuple[str, str], dict[str, Any]] = {}
        # home_seat_daily: list of dicts with buyer_account_id, reached_queries, metric_date
        self.seat_daily: list[dict[str, Any]] = []
        # buyer_seats: list of dicts with buyer_id, bidder_id
        self.buyer_seats: list[dict[str, Any]] = []

    async def upsert_endpoints(self, bidder_id: str, endpoints: list[dict[str, Any]]) -> int:
        # Remove old for this bidder
        self.endpoints = [e for e in self.endpoints if e["bidder_id"] != bidder_id]
        for ep in endpoints:
            self.endpoints.append({
                "bidder_id": bidder_id,
                "endpoint_id": str(ep["endpointId"]),
                "url": ep.get("url"),
                "maximum_qps": ep.get("maximumQps"),
                "trading_location": ep.get("tradingLocation"),
                "bid_protocol": ep.get("bidProtocol"),
            })
        return len(endpoints)

    async def list_endpoints(self, bidder_id: str | None = None) -> list[dict[str, Any]]:
        if bidder_id:
            return [e for e in self.endpoints if e["bidder_id"] == bidder_id]
        return list(self.endpoints)

    async def get_current_qps(self, bidder_id: str | None = None) -> float:
        total = 0.0
        for key, row in self.current.items():
            if bidder_id is None or key[0] == bidder_id:
                total += row.get("current_qps", 0)
        return total

    async def refresh_endpoints_current(
        self,
        lookback_days: int = 7,
        bidder_id: Optional[str] = None,
    ) -> int:
        """Simulate the SQL logic: derive QPS from seat_daily, distribute by max_qps."""
        # Build bidder traffic map
        bidder_traffic: dict[str, float] = {}
        for row in self.seat_daily:
            buyer_id = row["buyer_account_id"]
            # Map buyer to bidder via buyer_seats
            mapped_bidder = buyer_id  # fallback
            for bs in self.buyer_seats:
                if bs["buyer_id"] == buyer_id:
                    mapped_bidder = bs["bidder_id"]
                    break
            bidder_traffic.setdefault(mapped_bidder, 0.0)
            bidder_traffic[mapped_bidder] += row.get("reached_queries", 0)

        # Convert to avg QPS (total / days / 86400)
        days_seen: dict[str, set] = {}
        for row in self.seat_daily:
            buyer_id = row["buyer_account_id"]
            mapped_bidder = buyer_id
            for bs in self.buyer_seats:
                if bs["buyer_id"] == buyer_id:
                    mapped_bidder = bs["bidder_id"]
                    break
            days_seen.setdefault(mapped_bidder, set()).add(row.get("metric_date"))

        bidder_qps: dict[str, float] = {}
        for bid, total in bidder_traffic.items():
            n_days = max(len(days_seen.get(bid, set())), 1)
            bidder_qps[bid] = total / n_days / 86400

        # For each configured endpoint, compute proportional QPS
        # First group endpoints by bidder to get totals
        bidder_total_max: dict[str, float] = {}
        for ep in self.endpoints:
            bid = ep["bidder_id"]
            if bidder_id and bid != bidder_id:
                continue
            bidder_total_max.setdefault(bid, 0.0)
            bidder_total_max[bid] += (ep.get("maximum_qps") or 0)

        count = 0
        now = datetime.now(timezone.utc).isoformat()
        for ep in self.endpoints:
            bid = ep["bidder_id"]
            if bidder_id and bid != bidder_id:
                continue
            eid = ep["endpoint_id"]
            total_max = bidder_total_max.get(bid, 0)
            obs = bidder_qps.get(bid, 0)
            if total_max > 0 and obs > 0:
                qps = (ep.get("maximum_qps") or 0) / total_max * obs
            else:
                qps = 0.0
            key = (bid, eid)
            self.current[key] = {
                "bidder_id": bid,
                "endpoint_id": eid,
                "current_qps": qps,
                "observed_at": now,
            }
            count += 1
        return count


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_endpoint(eid: str, max_qps: int, location: str = "US_WEST") -> dict:
    return {
        "endpointId": eid,
        "url": f"https://example.com/{eid}",
        "maximumQps": max_qps,
        "tradingLocation": location,
        "bidProtocol": "OPENRTB_2_5",
    }


# ---------------------------------------------------------------------------
# Test 1: Writer inserts new rows
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_inserts_new_rows():
    repo = StubEndpointsRepo()
    svc = EndpointsService(repo=repo)

    # Setup: 2 endpoints, some traffic
    await svc.sync_endpoints("bidder-1", [
        _make_endpoint("ep-1", 40000),
        _make_endpoint("ep-2", 20000),
    ])
    repo.buyer_seats = [{"buyer_id": "bidder-1", "bidder_id": "bidder-1"}]
    repo.seat_daily = [
        {"buyer_account_id": "bidder-1", "reached_queries": 86400 * 30000, "metric_date": "2026-02-10"},
    ]

    count = await svc.refresh_endpoints_current()
    assert count == 2
    assert len(repo.current) == 2

    # ep-1 gets 40000/60000 * 30000 = 20000 QPS
    ep1 = repo.current[("bidder-1", "ep-1")]
    assert ep1["current_qps"] == pytest.approx(20000.0, rel=0.01)

    # ep-2 gets 20000/60000 * 30000 = 10000 QPS
    ep2 = repo.current[("bidder-1", "ep-2")]
    assert ep2["current_qps"] == pytest.approx(10000.0, rel=0.01)


# ---------------------------------------------------------------------------
# Test 2: Writer updates existing rows idempotently
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_updates_idempotently():
    repo = StubEndpointsRepo()
    svc = EndpointsService(repo=repo)

    await svc.sync_endpoints("bidder-1", [_make_endpoint("ep-1", 50000)])
    repo.buyer_seats = [{"buyer_id": "bidder-1", "bidder_id": "bidder-1"}]
    repo.seat_daily = [
        {"buyer_account_id": "bidder-1", "reached_queries": 86400 * 10000, "metric_date": "2026-02-10"},
    ]

    # First refresh
    await svc.refresh_endpoints_current()
    first_qps = repo.current[("bidder-1", "ep-1")]["current_qps"]
    first_observed = repo.current[("bidder-1", "ep-1")]["observed_at"]
    assert first_qps == pytest.approx(10000.0, rel=0.01)

    # Update traffic data
    repo.seat_daily = [
        {"buyer_account_id": "bidder-1", "reached_queries": 86400 * 25000, "metric_date": "2026-02-10"},
    ]

    # Second refresh: should update, not duplicate
    count = await svc.refresh_endpoints_current()
    assert count == 1  # same endpoint, updated
    assert len(repo.current) == 1  # no duplicate
    assert repo.current[("bidder-1", "ep-1")]["current_qps"] == pytest.approx(25000.0, rel=0.01)


# ---------------------------------------------------------------------------
# Test 3: Handles multiple bidders in one run
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_handles_multiple_bidders():
    repo = StubEndpointsRepo()
    svc = EndpointsService(repo=repo)

    await svc.sync_endpoints("bidder-A", [_make_endpoint("ep-A1", 30000)])
    await svc.sync_endpoints("bidder-B", [
        _make_endpoint("ep-B1", 40000),
        _make_endpoint("ep-B2", 10000),
    ])
    repo.buyer_seats = [
        {"buyer_id": "bidder-A", "bidder_id": "bidder-A"},
        {"buyer_id": "bidder-B", "bidder_id": "bidder-B"},
    ]
    repo.seat_daily = [
        {"buyer_account_id": "bidder-A", "reached_queries": 86400 * 15000, "metric_date": "2026-02-10"},
        {"buyer_account_id": "bidder-B", "reached_queries": 86400 * 50000, "metric_date": "2026-02-10"},
    ]

    count = await svc.refresh_endpoints_current()
    assert count == 3  # 1 + 2 endpoints

    # bidder-A: single endpoint gets all 15000 QPS
    assert repo.current[("bidder-A", "ep-A1")]["current_qps"] == pytest.approx(15000.0, rel=0.01)

    # bidder-B: proportional distribution
    assert repo.current[("bidder-B", "ep-B1")]["current_qps"] == pytest.approx(40000.0, rel=0.01)
    assert repo.current[("bidder-B", "ep-B2")]["current_qps"] == pytest.approx(10000.0, rel=0.01)


# ---------------------------------------------------------------------------
# Test 4: Zero traffic produces rows with current_qps=0
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_zero_traffic_still_creates_rows():
    repo = StubEndpointsRepo()
    svc = EndpointsService(repo=repo)

    await svc.sync_endpoints("bidder-1", [_make_endpoint("ep-1", 30000)])
    repo.buyer_seats = [{"buyer_id": "bidder-1", "bidder_id": "bidder-1"}]
    # No seat_daily data: simulates no traffic

    count = await svc.refresh_endpoints_current()
    assert count == 1
    assert repo.current[("bidder-1", "ep-1")]["current_qps"] == 0.0


# ---------------------------------------------------------------------------
# Test 5: Freshness timestamp set correctly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_sets_observed_at_timestamp():
    repo = StubEndpointsRepo()
    svc = EndpointsService(repo=repo)

    await svc.sync_endpoints("bidder-1", [_make_endpoint("ep-1", 50000)])
    repo.buyer_seats = [{"buyer_id": "bidder-1", "bidder_id": "bidder-1"}]
    repo.seat_daily = [
        {"buyer_account_id": "bidder-1", "reached_queries": 86400 * 5000, "metric_date": "2026-02-10"},
    ]

    await svc.refresh_endpoints_current()
    row = repo.current[("bidder-1", "ep-1")]
    assert row["observed_at"] is not None

    # observed_at should be a recent ISO timestamp
    ts = datetime.fromisoformat(row["observed_at"])
    now = datetime.now(timezone.utc)
    delta = (now - ts).total_seconds()
    assert delta < 5  # within 5 seconds of now
