"""Tests for BigQuery raw schema health service."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from services import bigquery_schema_health_service as schema_health


def _field(name: str) -> SimpleNamespace:
    return SimpleNamespace(name=name)


def test_bigquery_raw_schema_health_is_disabled_without_raw_export(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(schema_health.parquet_pipeline, "_raw_export_enabled", lambda: False)
    monkeypatch.setattr(schema_health.parquet_pipeline, "_gcs_bucket", lambda: "")
    monkeypatch.setattr(schema_health.parquet_pipeline, "_bq_dataset", lambda: "")
    monkeypatch.setattr(schema_health.parquet_pipeline, "_bq_project", lambda: "")

    payload = schema_health.get_bigquery_raw_schema_health()

    assert payload["enabled"] is False
    assert payload["status"] == "disabled"
    assert payload["healthy"] is True
    assert payload["tables"] == []


def test_bigquery_raw_schema_health_detects_missing_columns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_columns = {
        "rtb_daily": ["metric_date", "report_type"],
        "rtb_bidstream": ["metric_date", "report_type"],
        "rtb_bid_filtering": ["metric_date", "report_type"],
        "rtb_quality": ["metric_date", "report_type"],
    }

    class _FakeClient:
        project = "catscan-prod-202601"

        def get_table(self, table_id: str):
            table_name = table_id.split(".")[-1]
            actual = expected_columns[table_name]
            if table_name == "rtb_bid_filtering":
                actual = ["metric_date"]
            return SimpleNamespace(schema=[_field(name) for name in actual])

    monkeypatch.setattr(schema_health.parquet_pipeline, "_raw_export_enabled", lambda: True)
    monkeypatch.setattr(schema_health.parquet_pipeline, "_gcs_bucket", lambda: "raw-bucket")
    monkeypatch.setattr(schema_health.parquet_pipeline, "_bq_dataset", lambda: "rtbcat_analytics")
    monkeypatch.setattr(schema_health.parquet_pipeline, "_bq_project", lambda: "catscan-prod-202601")
    monkeypatch.setattr(schema_health.parquet_pipeline, "_HAS_BQ", True)
    monkeypatch.setattr(
        schema_health.parquet_pipeline,
        "_bq_schema_for_table",
        lambda table_name: [_field(name) for name in expected_columns[table_name]],
    )
    monkeypatch.setattr(
        schema_health.parquet_pipeline,
        "bigquery",
        SimpleNamespace(Client=lambda project=None: _FakeClient()),
    )

    payload = schema_health.get_bigquery_raw_schema_health()

    assert payload["enabled"] is True
    assert payload["healthy"] is False
    assert payload["status"] == "degraded"
    assert payload["summary"]["degraded_tables"] == 1

    rtb_bid_filtering = next(
        table for table in payload["tables"] if table["table_name"] == "rtb_bid_filtering"
    )
    assert rtb_bid_filtering["missing_columns"] == ["report_type"]
    assert rtb_bid_filtering["status"] == "degraded"

