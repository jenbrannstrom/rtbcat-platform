from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from scripts.catscan_mcp_db_smoke import (
    DISCOVER_BUYERS_SQL,
    DISCOVER_LATEST_SPEND_DATE_SQL,
    TOOL_CONTRACTS,
    SmokeContext,
    SmokeError,
    compare_rows,
    discover_context,
    normalize_rows,
    rows_sha256,
    run_contracts,
)


class _FakeEndpoint:
    def __init__(
        self,
        label: str,
        *,
        buyers: list[str] | None = None,
        latest: date | None = None,
        contract_rows: dict[str, list[dict]] | None = None,
    ) -> None:
        self.label = label
        self.buyers = buyers or ["buyer-1"]
        self.latest = latest or date(2026, 7, 22)
        self.contract_rows = contract_rows or {}
        self.calls: list[tuple[str, dict]] = []

    def query(self, sql: str, params=None):
        safe_params = dict(params or {})
        self.calls.append((sql, safe_params))
        if sql == DISCOVER_BUYERS_SQL:
            return [{"buyer_id": buyer_id} for buyer_id in self.buyers]
        if sql == DISCOVER_LATEST_SPEND_DATE_SQL:
            return [{"latest_metric_date": self.latest}]
        for contract in TOOL_CONTRACTS:
            if sql == contract.sql:
                return self.contract_rows.get(contract.name, [])
        raise AssertionError("unexpected query")

    def close(self) -> None:
        pass


def test_contract_catalog_is_buyer_scoped_precomputed_and_mcp_shaped() -> None:
    expected = {
        "catscan.list_buyers",
        "catscan.get_data_freshness",
        "catscan.get_daily_spend",
        "catscan.get_monthly_spend",
        "catscan.get_all_time_spend",
        "catscan.get_performance_summary",
        "catscan.get_report_completeness",
        "catscan.get_top_geos",
        "catscan.get_top_publishers",
        "catscan.get_top_configs",
    }

    assert {contract.name for contract in TOOL_CONTRACTS} == expected
    for contract in TOOL_CONTRACTS:
        normalized_sql = " ".join(contract.sql.lower().split())
        assert "%(buyer_ids)s" in contract.sql
        assert "rtb_daily" not in normalized_sql
        assert contract.name.startswith("catscan.")
        assert contract.key_columns

    daily_spend = next(
        contract
        for contract in TOOL_CONTRACTS
        if contract.name == "catscan.get_daily_spend"
    )
    assert "rtb_buyer_spend_daily" in daily_spend.sql


def test_normalization_and_hash_are_stable_for_database_types() -> None:
    first = [
        {
            "metric_date": date(2026, 7, 1),
            "generated_at": datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc),
            "spend": Decimal("12.500000"),
            "payload": {"b": 2, "a": [Decimal("1.20")]},
        }
    ]
    second = [
        {
            "metric_date": "2026-07-01",
            "generated_at": "2026-07-01T12:00:00+00:00",
            "spend": "12.500000",
            "payload": {"a": ["1.20"], "b": 2},
        }
    ]

    assert normalize_rows(first) == normalize_rows(second)
    assert rows_sha256(first) == rows_sha256(second)


def test_compare_rows_reports_changed_columns_without_metric_values() -> None:
    source = [
        {
            "buyer_id": "buyer-secret",
            "metric_date": "2026-07-01",
            "spend_micros": 100,
        }
    ]
    target = [
        {
            "buyer_id": "buyer-secret",
            "metric_date": "2026-07-01",
            "spend_micros": 99,
        }
    ]

    result = compare_rows(
        source,
        target,
        key_columns=("buyer_id", "metric_date"),
    )

    assert result.changed == 1
    assert result.source_only == 0
    assert result.target_only == 0
    assert result.samples[0]["columns"] == ["spend_micros"]
    serialized = str(result)
    assert "buyer-secret" not in serialized
    assert "100" not in serialized


def test_compare_rows_rejects_non_unique_contract_keys() -> None:
    rows = [{"buyer_id": "one"}, {"buyer_id": "one"}]

    with pytest.raises(SmokeError, match="not unique"):
        compare_rows(rows, rows[:1], key_columns=("buyer_id",))


def test_discover_context_uses_shared_buyers_and_closed_target_window() -> None:
    source = _FakeEndpoint(
        "source",
        buyers=["buyer-1", "buyer-2", "source-only"],
        latest=date(2026, 7, 24),
    )
    target = _FakeEndpoint(
        "target",
        buyers=["buyer-1", "buyer-2", "target-only"],
        latest=date(2026, 7, 22),
    )

    context = discover_context(source, target, days=14, stable_lag_days=1, top_limit=5)

    assert context == SmokeContext(
        buyer_ids=("buyer-1", "buyer-2"),
        start_date=date(2026, 7, 8),
        end_date=date(2026, 7, 21),
        top_limit=5,
    )


def test_discover_context_rejects_buyer_not_present_in_both_databases() -> None:
    source = _FakeEndpoint("source", buyers=["buyer-1"])
    target = _FakeEndpoint("target", buyers=["buyer-1"])

    with pytest.raises(SmokeError, match="not present in both"):
        discover_context(source, target, buyer_ids=["buyer-2"])


def test_run_contracts_compares_every_contract_and_passes_shared_params() -> None:
    rows_by_contract = {
        contract.name: [
            {
                column: f"value-{index}"
                for index, column in enumerate(contract.key_columns)
            }
        ]
        for contract in TOOL_CONTRACTS
    }
    source = _FakeEndpoint("source", contract_rows=rows_by_contract)
    target = _FakeEndpoint("target", contract_rows=rows_by_contract)
    context = SmokeContext(
        buyer_ids=("buyer-1",),
        start_date=date(2026, 7, 1),
        end_date=date(2026, 7, 7),
        top_limit=10,
    )

    results = run_contracts(source, target, context)

    assert len(results) == len(TOOL_CONTRACTS)
    assert all(result.passed for result in results)
    contract_calls = source.calls[-len(TOOL_CONTRACTS) :]
    assert all(call[1]["buyer_ids"] == ["buyer-1"] for call in contract_calls)
    assert all(call[1]["start_date"] == date(2026, 7, 1) for call in contract_calls)
