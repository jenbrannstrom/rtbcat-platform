from __future__ import annotations

from types import SimpleNamespace

from importers import unified_importer
from scripts import gmail_import, run_pipeline


def test_canonical_spend_messages_are_prioritized_stably() -> None:
    subjects = {
        "quality-1": "Authorized Buyers Scheduled Report - catscan-quality-123-yesterday-UTC",
        "spend-1": "Authorized Buyers Scheduled Report - catscan-bidsinauction-123-yesterday-UTC",
        "pipeline-1": "Authorized Buyers Scheduled Report - catscan-pipeline-123-yesterday-UTC",
        "spend-2": "Authorized Buyers Scheduled Report - catscan-bidsinauction-456-yesterday-UTC",
    }

    class Request:
        def __init__(self, message_id: str):
            self.message_id = message_id

        def execute(self):
            return {
                "payload": {
                    "headers": [{"name": "Subject", "value": subjects[self.message_id]}]
                }
            }

    class Messages:
        def get(self, **kwargs):
            return Request(kwargs["id"])

    class Users:
        def messages(self):
            return Messages()

    class Service:
        def users(self):
            return Users()

    messages = [{"id": message_id} for message_id in subjects]

    ordered = gmail_import.prioritize_report_messages(Service(), messages)

    assert [message["id"] for message in ordered] == [
        "spend-1",
        "spend-2",
        "quality-1",
        "pipeline-1",
    ]


def test_publish_buyer_spend_range_scopes_refresh_to_seat(monkeypatch) -> None:
    captured = {}

    async def _refresh(start_date, end_date, buyer_account_id=None):
        captured.update(
            start_date=start_date,
            end_date=end_date,
            buyer_account_id=buyer_account_id,
        )

    from services import rtb_precompute

    monkeypatch.setattr(rtb_precompute, "refresh_rtb_summaries", _refresh)

    gmail_import.publish_buyer_spend_range(
        start_date="2026-07-10",
        end_date="2026-07-10",
        seat_id="6574658621",
    )

    assert captured == {
        "start_date": "2026-07-10",
        "end_date": "2026-07-10",
        "buyer_account_id": "6574658621",
    }


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
