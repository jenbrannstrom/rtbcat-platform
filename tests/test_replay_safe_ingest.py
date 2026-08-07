"""Replay-safe spend ingest (option C of BRIEF_PARQUET_BQ_IDEMPOTENCY).

Covers the three pieces that together make re-delivered / restated / overlapping
report files safe:

  1. every exported parquet row carries the batch's ``created_at`` stamp, so
     competing batches for the same day are orderable inside BigQuery;
  2. every raw-table read in ``refresh_rtb_summaries`` goes through the
     winning-batch filter (newest batch per report_type/buyer/day wins);
  3. the delivery watchdog treats identical duplicate batches as normal and
     alerts only on batches with differing totals (a genuine restatement).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

pytest.importorskip("google.cloud.bigquery")

from importers import parquet_pipeline
from services import rtb_precompute
from scripts.check_report_delivery import evaluate_spend_lane


# --- 1. created_at stamping -------------------------------------------------

@pytest.mark.parametrize(
    "table", ["rtb_daily", "rtb_bidstream", "rtb_bid_filtering", "rtb_quality"]
)
def test_schemas_carry_created_at(table: str) -> None:
    pytest.importorskip("pyarrow")
    parquet_schema = parquet_pipeline._parquet_schema_for_table(table)
    assert "created_at" in parquet_schema.names
    bq_names = [f.name for f in parquet_pipeline._bq_schema_for_table(table)]
    assert "created_at" in bq_names


def test_add_row_stamps_batch_created_at(tmp_path) -> None:
    manager = parquet_pipeline.ParquetExportManager(
        table_name="rtb_daily",
        batch_id="batch-1",
        result_errors=[],
        enabled=True,
        local_root=tmp_path,
    )
    manager.add_row("2026-08-01", {"metric_date": "2026-08-01", "spend_micros": 5})
    row = manager._buffers["2026-08-01"][0]
    assert row["created_at"] == manager.created_at
    assert manager.created_at.tzinfo is not None


def test_add_row_keeps_explicit_created_at(tmp_path) -> None:
    explicit = datetime(2026, 7, 1, tzinfo=timezone.utc)
    manager = parquet_pipeline.ParquetExportManager(
        table_name="rtb_daily",
        batch_id="batch-1",
        result_errors=[],
        enabled=True,
        local_root=tmp_path,
    )
    manager.add_row("2026-07-01", {"metric_date": "2026-07-01", "created_at": explicit})
    assert manager._buffers["2026-07-01"][0]["created_at"] == explicit


def test_normalize_value_passes_timestamps() -> None:
    pa = pytest.importorskip("pyarrow")

    stamp = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)
    field_type = pa.timestamp("us", tz="UTC")
    assert parquet_pipeline._normalize_value(stamp, field_type) is stamp
    parsed = parquet_pipeline._normalize_value("2026-08-01T12:00:00+00:00", field_type)
    assert parsed == stamp


# --- 2. winning-batch reader filter ----------------------------------------

def test_winning_batch_source_sql_contract() -> None:
    sql = rtb_precompute.winning_batch_source("p.d.rtb_daily", buyer_clause=" AND buyer_account_id = @buyer_account_id")
    assert sql.startswith("(SELECT * FROM `p.d.rtb_daily`")
    assert "metric_date BETWEEN @start_date AND @end_date" in sql
    assert "AND buyer_account_id = @buyer_account_id" in sql
    assert "QUALIFY RANK() OVER (" in sql
    assert "PARTITION BY report_type, COALESCE(buyer_account_id, ''), metric_date" in sql
    # Newest batch wins; legacy NULL created_at sorts to the epoch; batch id
    # is the deterministic tiebreak.
    assert "COALESCE(created_at, TIMESTAMP '1970-01-01 00:00:00+00') DESC" in sql
    assert "COALESCE(import_batch_id, '') DESC) = 1)" in sql


def test_refresh_reads_only_winner_filtered_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[str] = []

    class _FakeClient:
        project = "proj"

    def fake_run_query(client, *, sql, params, timeout_seconds, max_retries):
        captured.append(sql)
        return []

    class _FakeConn:
        def execute(self, *args, **kwargs):
            return None

    async def fake_pg_transaction_async(fn):
        return fn(_FakeConn())

    monkeypatch.setenv("BIGQUERY_DATASET", "ds")
    monkeypatch.setattr(rtb_precompute, "get_bigquery_client", lambda: _FakeClient())
    monkeypatch.setattr(rtb_precompute, "run_query", fake_run_query)
    monkeypatch.setattr(rtb_precompute, "pg_transaction_async", fake_pg_transaction_async)
    monkeypatch.setattr(rtb_precompute, "execute_many", lambda *a, **k: None)
    monkeypatch.setattr(rtb_precompute, "record_refresh_log_postgres", lambda *a, **k: None)
    monkeypatch.setattr(rtb_precompute, "record_refresh_run_postgres", lambda *a, **k: None)

    result = asyncio.run(
        rtb_precompute.refresh_rtb_summaries("2026-08-01", "2026-08-02", "7942355670")
    )

    raw_reads = [s for s in captured if "rtb_daily" in s or "rtb_bidstream" in s]
    assert len(raw_reads) == 9, f"expected 9 raw-table queries, saw {len(raw_reads)}"
    for sql in raw_reads:
        assert "QUALIFY RANK() OVER (" in sql, f"raw read without winner filter:\n{sql}"
        # The raw table must only ever be scanned inside the filtered subquery.
        assert "FROM `proj.ds.rtb_daily`\n" not in sql
        assert "FROM `proj.ds.rtb_bidstream`\n" not in sql
    # row_counts is popped into the refresh-run bookkeeping before return.
    assert result["refresh_run_id"]
    assert result["dates"] == ["2026-08-01", "2026-08-02"]


# --- 3. watchdog restatement semantics --------------------------------------

def _batch(batch_id: str, micros: int, when: datetime | None) -> dict:
    return {"batch_id": batch_id, "spend_micros": micros, "created_at": when}


def test_watchdog_single_batch_ok() -> None:
    status, alert = evaluate_spend_lane(
        [_batch("a", 100, datetime(2026, 8, 2, tzinfo=timezone.utc))], "2026-08-01", "seat"
    )
    assert status == "ok"
    assert alert is None


def test_watchdog_missing() -> None:
    status, alert = evaluate_spend_lane([], "2026-08-01", "seat")
    assert status == "missing"
    assert alert is None


def test_watchdog_identical_duplicates_are_normal() -> None:
    when = datetime(2026, 8, 2, tzinfo=timezone.utc)
    status, alert = evaluate_spend_lane(
        [_batch("b", 100, when), _batch("a", 100, when)], "2026-08-01", "seat"
    )
    assert alert is None
    assert "identical" in status


def test_watchdog_differing_totals_alert_names_winner() -> None:
    newer = datetime(2026, 8, 3, tzinfo=timezone.utc)
    older = datetime(2026, 8, 2, tzinfo=timezone.utc)
    summaries = sorted(
        [_batch("old", 100, older), _batch("new", 150, newer)],
        key=lambda b: (b["created_at"], b["batch_id"]),
        reverse=True,
    )
    status, alert = evaluate_spend_lane(summaries, "2026-08-01", "seat")
    assert status.startswith("RESTATED(2")
    assert alert is not None
    assert "batch new" in alert
    assert "DIFFERING" in alert
