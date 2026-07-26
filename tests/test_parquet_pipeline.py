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
        project = "test-project"

        def __init__(self) -> None:
            self.calls = []

        def load_table_from_uri(self, gcs_uri, table_id, job_config):
            self.calls.append((gcs_uri, table_id, job_config))
            return _FakeJob()

    fake_client = _FakeClient()
    monkeypatch.setenv("CATSCAN_BQ_DATASET", "rtbcat_analytics")
    monkeypatch.setenv("CATSCAN_BQ_PROJECT", "test-project")
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
    assert table_id == "test-project.rtbcat_analytics.rtb_bid_filtering"
    assert parquet_pipeline.bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION in (
        job_config.schema_update_options or []
    )


def test_discard_removes_local_parquet_without_uploading(tmp_path, monkeypatch) -> None:
    class _FakeWriter:
        closed = False

        def close(self) -> None:
            self.closed = True

    parquet_path = tmp_path / "rtb_daily" / "day=2026-07-05" / "batch-1.parquet"
    parquet_path.parent.mkdir(parents=True)
    parquet_path.write_bytes(b"buffered duplicate")
    writer = _FakeWriter()
    manager = parquet_pipeline.ParquetExportManager(
        table_name="rtb_daily",
        batch_id="batch-1",
        result_errors=[],
        enabled=True,
        local_root=tmp_path,
    )
    manager._buffers["2026-07-05"] = [{"metric_date": "2026-07-05"}]
    manager._writers["2026-07-05"] = writer
    manager._paths["2026-07-05"] = parquet_path
    monkeypatch.setattr(
        manager,
        "_upload_files",
        lambda: (_ for _ in ()).throw(AssertionError("discard must not upload")),
    )

    manager.discard()

    assert writer.closed is True
    assert not parquet_path.exists()
    assert manager._buffers == {}
    assert manager._writers == {}
    assert manager._paths == {}
