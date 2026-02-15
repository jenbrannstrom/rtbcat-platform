"""Contract check runner tests (environment-independent).

Uses unittest.mock to patch pg_query, so no database connection is needed.
Tests verify the check logic, status assignment, and exit-code semantics.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

# Import the check functions under test.
from scripts.contracts_check import (
    CheckResult,
    check_ept_001,
    check_ing_001,
    check_ing_002,
    check_pre_002,
    check_pre_003,
    run_all_checks,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _buyers(*ids: str) -> list[dict[str, Any]]:
    return [{"buyer_id": bid, "bidder_id": bid} for bid in ids]


def _mock_pg(responses: dict[str, list[dict]]) -> AsyncMock:
    """Build an AsyncMock for pg_query that dispatches on SQL substrings.

    ``responses`` maps a substring of the SQL statement to the list of dicts
    that pg_query should return when that substring is found in the query.
    Matching is first-match.
    """

    async def _side_effect(sql: str, params: tuple = ()) -> list[dict]:
        for key, val in responses.items():
            if key in sql:
                return val
        return []

    mock = AsyncMock(side_effect=_side_effect)
    return mock


PG_QUERY = "scripts.contracts_check.pg_query"


# ---------------------------------------------------------------------------
# Test 1: All contracts pass
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_all_pass():
    """When all DB state is healthy, every check returns PASS."""
    responses = {
        # C-ING-001: has runs, none stuck
        "FROM ingestion_runs WHERE finished_at IS NULL": [{"cnt": 0}],
        "FROM ingestion_runs": [{"cnt": 42}],
        # C-ING-002: all buyers have imports
        "FROM import_history": [{"cnt": 5}],
        # C-EPT-001: endpoints exist, all current (specific key first!)
        "LEFT JOIN rtb_endpoints_current": [],  # no gaps
        "FROM rtb_endpoints": [{"cnt": 3}],
        # C-PRE-002: no gap
        "FROM pretargeting_configs": [{"configured_active": 10, "observed_precompute": 10, "gap": 0}],
        # C-PRE-003: buyer has pretarg data AND publisher data
        "FROM pretarg_daily WHERE buyer_account_id": [{"cnt": 50}],
        "FROM pretarg_publisher_daily": [{"cnt": 30}],
    }

    with patch(PG_QUERY, new=_mock_pg(responses)):
        results = [
            await check_ing_001(7),
            await check_ing_002(7, _buyers("b1")),
            await check_ept_001(),
            await check_pre_002(7, _buyers("b1")),
            await check_pre_003(7, _buyers("b1")),
        ]

    for r in results:
        assert r.status == "PASS", f"{r.contract_id} expected PASS, got {r.status}: {r.message}"


# ---------------------------------------------------------------------------
# Test 2: C-EPT-001 gap detected
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ept_001_gap_failure():
    """Endpoints exist but some are missing from rtb_endpoints_current."""
    responses = {
        # More specific key must come first (first-match dispatch).
        "LEFT JOIN rtb_endpoints_current": [
            {"bidder_id": "b1", "endpoint_id": "ep-1", "observed_at": None},
            {"bidder_id": "b1", "endpoint_id": "ep-2", "observed_at": None},
        ],
        "FROM rtb_endpoints": [{"cnt": 3}],
    }

    with patch(PG_QUERY, new=_mock_pg(responses)):
        result = await check_ept_001()

    assert result.status == "FAIL"
    assert result.details["missing"] == 2
    assert result.contract_id == "C-EPT-001"


# ---------------------------------------------------------------------------
# Test 3: C-PRE-002 missing active config
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pre_002_missing_config():
    """An ACTIVE config has no row in home_config_daily."""
    responses = {
        "FROM pretargeting_configs": [
            {"configured_active": 10, "observed_precompute": 8, "gap": 2}
        ],
    }

    with patch(PG_QUERY, new=_mock_pg(responses)):
        result = await check_pre_002(7, _buyers("b1"))

    assert result.status == "FAIL"
    assert result.details["total_gap"] == 2
    assert "b1" in result.details["buyer_gaps"]


# ---------------------------------------------------------------------------
# Test 4: C-PRE-003 justified exception → WARN (non-strict)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pre_003_justified_exception_warn():
    """Buyer has pretarg data but no publisher data, and no publisher_id in
    rtb_daily → justified exception → WARN in non-strict mode."""
    responses = {
        "FROM pretarg_daily WHERE buyer_account_id": [{"cnt": 50}],
        "FROM pretarg_publisher_daily": [{"cnt": 0}],
        "FROM rtb_daily": [{"with_pub": 0}],
    }

    with patch(PG_QUERY, new=_mock_pg(responses)):
        result = await check_pre_003(7, _buyers("buyer-X"), strict=False)

    assert result.status == "WARN"
    assert "buyer-X" in result.details["justified_exceptions"]
    assert result.details["missing"] == []


# ---------------------------------------------------------------------------
# Test 5: C-PRE-003 justified exception → FAIL under --strict
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pre_003_strict_fail():
    """Same justified exception as above, but --strict promotes WARN to FAIL."""
    responses = {
        "FROM pretarg_daily WHERE buyer_account_id": [{"cnt": 50}],
        "FROM pretarg_publisher_daily": [{"cnt": 0}],
        "FROM rtb_daily": [{"with_pub": 0}],
    }

    with patch(PG_QUERY, new=_mock_pg(responses)):
        result = await check_pre_003(7, _buyers("buyer-X"), strict=True)

    assert result.status == "FAIL"
    assert "buyer-X" in result.details["justified_exceptions"]


# ---------------------------------------------------------------------------
# Test 6: No active buyers → DISCOVERY FAIL
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_active_buyers():
    """When buyer_seats has no active rows, run_all_checks returns a
    DISCOVERY FAIL and no individual contract is checked."""
    responses = {
        "FROM buyer_seats": [],
    }

    with patch(PG_QUERY, new=_mock_pg(responses)):
        results = await run_all_checks(days=7, strict=False)

    assert len(results) == 1
    assert results[0].contract_id == "DISCOVERY"
    assert results[0].status == "FAIL"


# ---------------------------------------------------------------------------
# Test 7: C-ING-001 stuck runs detected → WARN
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ing_001_stuck_runs():
    """ingestion_runs has rows but some are stuck (no finished_at)."""
    responses = {
        "FROM ingestion_runs WHERE finished_at IS NULL": [{"cnt": 2}],
        "FROM ingestion_runs": [{"cnt": 10}],
    }

    with patch(PG_QUERY, new=_mock_pg(responses)):
        result = await check_ing_001(7)

    assert result.status == "WARN"
    assert result.details["stuck_runs"] == 2


# ---------------------------------------------------------------------------
# Test 8: C-ING-002 missing buyers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ing_002_missing_buyers():
    """One buyer has imports, another does not."""

    call_count = 0

    async def _pg(sql: str, params: tuple = ()) -> list[dict]:
        nonlocal call_count
        if "import_history" in sql:
            call_count += 1
            # First buyer has imports, second does not
            return [{"cnt": 5}] if call_count == 1 else [{"cnt": 0}]
        return []

    with patch(PG_QUERY, new=AsyncMock(side_effect=_pg)):
        result = await check_ing_002(7, _buyers("buyer-A", "buyer-B"))

    assert result.status == "FAIL"
    assert "buyer-B" in result.details["missing_buyers"]
    assert "buyer-A" not in result.details["missing_buyers"]
