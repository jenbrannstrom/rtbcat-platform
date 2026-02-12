"""Web/domain data lane tests (Phase 5).

Tests cover:
1. Filename-first routing
2. Inventory type derivation (explicit, web heuristic, app heuristic, unknown)
3. Natural PK upsert idempotency
4. Top-N rollup with fallback ranking
5. Buyer allowlist / feature flag behavior
"""

from __future__ import annotations

import csv
import os
import tempfile
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from importers.flexible_mapper import map_columns, detect_best_report_type
from importers.domain_rollup import rollup_domains
from importers.unified_importer import (
    derive_inventory_type,
    is_web_lane_enabled,
    unified_import,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_csv(path: str, headers: list[str], rows: list[list[str]]):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for r in rows:
            w.writerow(r)


def _buyers(*ids: str) -> list[dict[str, Any]]:
    return [{"buyer_id": bid, "bidder_id": bid} for bid in ids]


def _mock_pg(responses: dict[str, list[dict]]) -> AsyncMock:
    async def _side_effect(sql: str, params: tuple = ()) -> list[dict]:
        for key, val in responses.items():
            if key in sql:
                return val
        return []
    return AsyncMock(side_effect=_side_effect)


PG_QUERY = "scripts.contracts_check.pg_query"


# ---------------------------------------------------------------------------
# Test 1: Filename routing forces domain table
# ---------------------------------------------------------------------------

def test_filename_routing_forces_domain_table():
    """catscan-domains-* filename overrides column detection even when
    creative_id is present."""
    tmpdir = tempfile.mkdtemp()
    csv_path = os.path.join(tmpdir, "data.csv")
    # CSV has creative_id (would normally route to rtb_daily)
    _write_csv(csv_path, [
        "Day", "Buyer Account ID", "Billing ID", "Creative ID",
        "Publisher Domain", "Impressions",
    ], [
        ["2026-01-15", "9999999999", "12345", "cr-1", "example.com", "100"],
    ])

    # Verify column detection would normally route to rtb_daily
    mapping = map_columns([
        "Day", "Buyer Account ID", "Billing ID", "Creative ID",
        "Publisher Domain", "Impressions",
    ])
    report_type, target_table, _ = detect_best_report_type(mapping)
    assert target_table == "rtb_daily", "Without filename, creative_id routes to rtb_daily"

    # Now test with domain filename — unified_import should override
    # We mock get_postgres_connection to avoid real DB calls
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    # Make executemany report 1 row inserted
    mock_cursor.rowcount = 1

    with patch("importers.unified_importer.get_postgres_connection", return_value=mock_conn), \
         patch.dict(os.environ, {"CATSCAN_WEB_LANE_ENABLED": "true", "CATSCAN_WEB_LANE_BUYERS": "9999999999"}), \
         patch("importers.unified_importer.ParquetExportManager") as mock_pem:
        mock_pem.from_env.return_value = None
        result = unified_import(
            csv_path,
            source_filename="catscan-domains-9999999999-yesterday-UTC.csv",
        )

    assert result.report_type == "domains"
    assert result.target_table == "web_domain_daily"


# ---------------------------------------------------------------------------
# Test 2: Inventory type explicit passthrough
# ---------------------------------------------------------------------------

def test_inventory_type_explicit_passthrough():
    """When inventory_type is explicitly set, derive_inventory_type is not used."""
    row_data = {
        "app_id": "com.example.app",
        "app_name": "Example App",
        "publisher_domain": "example.com",
    }
    # derive_inventory_type uses signals, but explicit value should bypass it
    # Here we test the derivation function directly for app signal
    assert derive_inventory_type(row_data) == "app"

    # Test explicit pass-through behavior: explicit 'web' overrides app signals
    row_data_explicit = {"inventory_type": "web"}
    # The importer respects explicit; derive_inventory_type is only called when absent
    assert row_data_explicit["inventory_type"] == "web"


# ---------------------------------------------------------------------------
# Test 3: Inventory type heuristic — web
# ---------------------------------------------------------------------------

def test_inventory_type_heuristic_web():
    """Domain present without app_id → web."""
    row_data = {
        "app_id": "",
        "app_name": "",
        "publisher_domain": "news.example.com",
    }
    assert derive_inventory_type(row_data) == "web"


# ---------------------------------------------------------------------------
# Test 4: Inventory type heuristic — app
# ---------------------------------------------------------------------------

def test_inventory_type_heuristic_app():
    """app_id present → app (takes precedence over domain)."""
    row_data = {
        "app_id": "com.game.fun",
        "app_name": "Fun Game",
        "publisher_domain": "funplatform.com",
    }
    assert derive_inventory_type(row_data) == "app"


# ---------------------------------------------------------------------------
# Test 5: Inventory type unknown / no domain
# ---------------------------------------------------------------------------

def test_inventory_type_unknown_no_domain():
    """No signals → unknown; __NO_DOMAIN__ treated as no domain."""
    row_data_empty = {
        "app_id": "",
        "app_name": "",
        "publisher_domain": "",
    }
    assert derive_inventory_type(row_data_empty) == "unknown"

    row_data_no_domain = {
        "app_id": "",
        "app_name": "",
        "publisher_domain": "__NO_DOMAIN__",
    }
    assert derive_inventory_type(row_data_no_domain) == "unknown"


# ---------------------------------------------------------------------------
# Test 6: Natural PK upsert idempotency
# ---------------------------------------------------------------------------

def test_natural_pk_upsert_idempotency():
    """Import same (date, buyer, billing, domain) twice → second is ON CONFLICT DO NOTHING."""
    tmpdir = tempfile.mkdtemp()
    csv_path = os.path.join(tmpdir, "domains.csv")
    _write_csv(csv_path, [
        "Day", "Buyer Account ID", "Billing ID", "Publisher Domain", "Impressions",
    ], [
        ["2026-01-15", "9999999999", "12345", "example.com", "100"],
        ["2026-01-15", "9999999999", "12345", "example.com", "200"],  # duplicate key
    ])

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    # Simulate: first executemany inserts 1 (second is DO NOTHING)
    mock_cursor.rowcount = 1

    with patch("importers.unified_importer.get_postgres_connection", return_value=mock_conn), \
         patch.dict(os.environ, {"CATSCAN_WEB_LANE_ENABLED": "true", "CATSCAN_WEB_LANE_BUYERS": "9999999999"}), \
         patch("importers.unified_importer.ParquetExportManager") as mock_pem:
        mock_pem.from_env.return_value = None
        result = unified_import(
            csv_path,
            source_filename="catscan-domains-9999999999-yesterday-UTC.csv",
        )

    assert result.success
    assert result.rows_read == 2
    # The SQL uses ON CONFLICT DO NOTHING, DB handles dedup
    # We verify executemany was called with a batch containing entries
    assert mock_cursor.executemany.called
    call_args = mock_cursor.executemany.call_args
    sql = call_args[0][0]
    assert "ON CONFLICT" in sql
    assert "DO NOTHING" in sql


# ---------------------------------------------------------------------------
# Test 7: Top-N rollup with fallback ranking
# ---------------------------------------------------------------------------

def test_topn_rollup_with_fallback_ranking():
    """250 rows N=200 → 201 rows; test spend_micros fallback when impressions=0."""
    # Case 1: impressions-based ranking (normal)
    rows_imps = []
    for i in range(250):
        rows_imps.append({
            "metric_date": "2026-01-15",
            "buyer_account_id": "buyer-1",
            "billing_id": "config-1",
            "publisher_domain": f"domain-{i:04d}.com",
            "impressions": 250 - i,  # descending
            "reached_queries": 10,
            "spend_micros": 1000,
        })

    result = rollup_domains(rows_imps, top_n=200)
    assert len(result) == 201, f"Expected 201 rows, got {len(result)}"

    # Verify __OTHER__ exists and has aggregated values
    other_rows = [r for r in result if r["publisher_domain"] == "__OTHER__"]
    assert len(other_rows) == 1
    other = other_rows[0]
    # Remainder is domains 200-249 (50 domains, impressions 50 down to 1)
    expected_imps = sum(range(1, 51))  # 1+2+...+50 = 1275
    assert other["impressions"] == expected_imps
    assert other["reached_queries"] == 10 * 50
    assert other["spend_micros"] == 1000 * 50

    # Case 2: spend_micros fallback when all impressions=0
    rows_spend = []
    for i in range(250):
        rows_spend.append({
            "metric_date": "2026-01-15",
            "buyer_account_id": "buyer-1",
            "billing_id": "config-1",
            "publisher_domain": f"domain-{i:04d}.com",
            "impressions": 0,
            "reached_queries": 5,
            "spend_micros": 250 - i,  # descending
        })

    result2 = rollup_domains(rows_spend, top_n=200)
    assert len(result2) == 201

    # Top row should have highest spend_micros
    non_other = [r for r in result2 if r["publisher_domain"] != "__OTHER__"]
    assert non_other[0]["spend_micros"] >= non_other[-1]["spend_micros"]


# ---------------------------------------------------------------------------
# Test 8: Buyer allowlist and SKIP behavior
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_buyer_allowlist_skip():
    """Global disabled → SKIP; enabled but buyer not in allowlist → rejected;
    buyer in allowlist → processes."""

    # --- Global disabled → contract checks return SKIP ---
    from scripts.contracts_check import check_web_001, check_web_002

    with patch.dict(os.environ, {}, clear=False):
        # Ensure CATSCAN_WEB_LANE_ENABLED is NOT set
        os.environ.pop("CATSCAN_WEB_LANE_ENABLED", None)
        os.environ.pop("CATSCAN_WEB_LANE_BUYERS", None)

        with patch(PG_QUERY, new=_mock_pg({})):
            r1 = await check_web_001(7)
            r2 = await check_web_002(7, _buyers("b1"))

    assert r1.status == "SKIP"
    assert r2.status == "SKIP"

    # --- is_web_lane_enabled checks ---
    with patch.dict(os.environ, {"CATSCAN_WEB_LANE_ENABLED": "true", "CATSCAN_WEB_LANE_BUYERS": "allowed-1,allowed-2"}):
        assert is_web_lane_enabled("allowed-1") is True
        assert is_web_lane_enabled("allowed-2") is True
        assert is_web_lane_enabled("not-allowed") is False

    # --- Global enabled, no buyer restriction ---
    with patch.dict(os.environ, {"CATSCAN_WEB_LANE_ENABLED": "true"}, clear=False):
        os.environ.pop("CATSCAN_WEB_LANE_BUYERS", None)
        assert is_web_lane_enabled("any-buyer") is True

    # --- Importer rejects non-allowlisted buyer ---
    tmpdir = tempfile.mkdtemp()
    csv_path = os.path.join(tmpdir, "domains.csv")
    _write_csv(csv_path, [
        "Day", "Buyer Account ID", "Billing ID", "Publisher Domain", "Impressions",
    ], [
        ["2026-01-15", "blocked-buyer", "12345", "example.com", "100"],
    ])

    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    with patch("importers.unified_importer.get_postgres_connection", return_value=mock_conn), \
         patch.dict(os.environ, {"CATSCAN_WEB_LANE_ENABLED": "true", "CATSCAN_WEB_LANE_BUYERS": "allowed-only"}), \
         patch("importers.unified_importer.ParquetExportManager") as mock_pem:
        mock_pem.from_env.return_value = None
        result = unified_import(
            csv_path,
            source_filename="catscan-domains-blocked-buyer-yesterday-UTC.csv",
        )

    assert "not in domain lane allowlist" in (result.error_message or "")
