from __future__ import annotations

from types import SimpleNamespace

from importers import unified_importer
from scripts import gmail_import, run_pipeline


def test_gmail_import_disables_per_file_legacy_scan(tmp_path, monkeypatch) -> None:
    csv_path = tmp_path / "report.csv"
    csv_path.write_text("#Day,Buyer account ID\n2026-07-10,123\n", encoding="utf-8")
    captured: dict = {}

    def _unified_import(path: str, **kwargs):
        captured.update({"path": path, **kwargs})
        return SimpleNamespace(
            success=True,
            report_type="buyer_spend",
            rows_imported=1,
            rows_duplicate=0,
            error_message="",
            rows_read=1,
            batch_id="batch-1",
            date_range_start="2026-07-10",
            date_range_end="2026-07-10",
            columns_mapped={},
        )

    monkeypatch.setattr(unified_importer, "unified_import", _unified_import)

    result = gmail_import.import_to_catscan(csv_path)

    assert result.success is True
    assert captured["sync_legacy_performance"] is False


def test_gmail_pipeline_defers_bigquery_aggregation(tmp_path, monkeypatch) -> None:
    csv_path = tmp_path / "report.csv"
    csv_path.write_text("#Day,Buyer account ID\n2026-07-10,123\n", encoding="utf-8")
    captured: dict = {}

    def _run_pipeline(**kwargs):
        captured.update(kwargs)
        return {"success": True}

    monkeypatch.setattr(gmail_import, "PIPELINE_ENABLED", True)
    monkeypatch.setattr(run_pipeline, "run_pipeline", _run_pipeline)

    assert gmail_import.run_pipeline_for_file(csv_path, "123", verbose=False) is True
    assert captured["metric_date"] == "2026-07-10"
    assert captured["skip_aggregate"] is True
