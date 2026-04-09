"""Tests for raw parquet export and BigQuery registration behavior."""

from __future__ import annotations

pytest_plugins = ()

import pytest

pytest.importorskip("google.cloud.bigquery")

from importers import parquet_pipeline


def test_parquet_export_manager_respects_explicit_raw_export_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CATSCAN_GCS_BUCKET", "raw-bucket")
    monkeypatch.setenv("CATSCAN_RAW_EXPORT_ENABLED", "false")

    manager = parquet_pipeline.ParquetExportManager.from_env(
        "rtb_daily",
        "batch-1",
        [],
    )

    assert manager.enabled is False


def test_register_bigquery_allows_field_addition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeJob:
        def result(self, timeout: int | None = None) -> None:
            del timeout

    class _FakeClient:
        project = "catscan-prod-202601"

        def __init__(self) -> None:
            self.calls = []

        def load_table_from_uri(self, gcs_uri, table_id, job_config):
            self.calls.append((gcs_uri, table_id, job_config))
            return _FakeJob()

    fake_client = _FakeClient()
    monkeypatch.setenv("CATSCAN_BQ_DATASET", "rtbcat_analytics")
    monkeypatch.setenv("CATSCAN_BQ_PROJECT", "catscan-prod-202601")
    monkeypatch.setenv("CATSCAN_BQ_LOAD_MODE", "load")
    monkeypatch.setattr(parquet_pipeline.bigquery, "Client", lambda project=None: fake_client)

    manager = parquet_pipeline.ParquetExportManager(
        table_name="rtb_bid_filtering",
        batch_id="batch-1",
        result_errors=[],
        enabled=True,
    )
    manager._register_bigquery(["gs://raw-bucket/path/to/file.parquet"])

    assert len(fake_client.calls) == 1
    _, table_id, job_config = fake_client.calls[0]
    assert table_id == "catscan-prod-202601.rtbcat_analytics.rtb_bid_filtering"
    assert parquet_pipeline.bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION in (
        job_config.schema_update_options or []
    )

