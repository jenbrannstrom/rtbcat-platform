"""Tests for unread-independent Gmail report discovery and durable dedup."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock


def _stub_google_modules() -> None:
    for mod_name in [
        "google",
        "google.auth",
        "google.auth.transport",
        "google.auth.transport.requests",
        "google.oauth2",
        "google.oauth2.credentials",
        "google_auth_oauthlib",
        "google_auth_oauthlib.flow",
        "googleapiclient",
        "googleapiclient.discovery",
        "google.cloud",
        "google.cloud.storage",
    ]:
        if mod_name not in sys.modules:
            sys.modules[mod_name] = MagicMock()


class _StubConn:
    """Minimal sync-psycopg stand-in capturing executed statements."""

    def __init__(self, rows: list[dict] | None = None):
        self.rows = rows or []
        self.calls: list[tuple[str, tuple]] = []

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return self

    def fetchall(self):
        return self.rows

    def close(self):
        pass


def test_default_query_uses_rolling_window_not_unread(monkeypatch):
    _stub_google_modules()
    from scripts import gmail_import

    monkeypatch.setattr(gmail_import, "GMAIL_QUERY", "")
    monkeypatch.setattr(gmail_import, "GMAIL_LABEL", "")
    monkeypatch.setattr(gmail_import, "GMAIL_LOOKBACK_DAYS", 3)

    query = gmail_import.build_report_search_query()

    assert "is:unread" not in query
    assert "newer_than:3d" in query
    assert "from:noreply-google-display-ads-managed-reports@google.com" in query


def test_default_query_honors_lookback_days_and_label(monkeypatch):
    _stub_google_modules()
    from scripts import gmail_import

    monkeypatch.setattr(gmail_import, "GMAIL_QUERY", "")
    monkeypatch.setattr(gmail_import, "GMAIL_LABEL", "reports")
    monkeypatch.setattr(gmail_import, "GMAIL_LOOKBACK_DAYS", 7)

    query = gmail_import.build_report_search_query()

    assert "newer_than:7d" in query
    assert "label:reports" in query


def test_explicit_query_env_still_wins(monkeypatch):
    _stub_google_modules()
    from scripts import gmail_import

    monkeypatch.setattr(gmail_import, "GMAIL_QUERY", "subject:catscan is:unread")

    assert gmail_import.build_report_search_query() == "subject:catscan is:unread"


def test_filter_new_messages_drops_already_imported_ids():
    _stub_google_modules()
    from scripts import gmail_import

    messages = [{"id": "m-1"}, {"id": "m-2"}, {"id": "m-3"}]

    remaining = gmail_import.filter_new_messages(messages, {"m-2"})

    assert remaining == [{"id": "m-1"}, {"id": "m-3"}]


def test_find_report_emails_filters_imported_ids(monkeypatch):
    _stub_google_modules()
    from scripts import gmail_import

    class Request:
        def execute(self):
            return {"messages": [{"id": "m-1"}, {"id": "m-2"}]}

    class Messages:
        def list(self, **_kwargs):
            return Request()

    class Users:
        def messages(self):
            return Messages()

    class Service:
        def users(self):
            return Users()

    seen_ids: list[list[str]] = []

    def _imported(message_ids):
        seen_ids.append(list(message_ids))
        return {"m-1"}

    monkeypatch.setattr(gmail_import, "get_imported_message_ids", _imported)

    messages = gmail_import.find_report_emails(Service())

    assert messages == [{"id": "m-2"}]
    assert seen_ids == [["m-1", "m-2"]]


def test_get_imported_message_ids_queries_imported_status_only(monkeypatch):
    _stub_google_modules()
    from scripts import gmail_import

    conn = _StubConn(rows=[{"gmail_message_id": "m-1"}])
    monkeypatch.setattr(gmail_import, "_get_sync_connection", lambda: conn)

    imported = gmail_import.get_imported_message_ids(["m-1", "m-2"])

    assert imported == {"m-1"}
    sql, params = conn.calls[0]
    assert "status = 'imported'" in sql
    assert params == (["m-1", "m-2"],)


def test_get_imported_message_ids_without_db_returns_empty(monkeypatch):
    _stub_google_modules()
    from scripts import gmail_import

    monkeypatch.setattr(gmail_import, "_get_sync_connection", lambda: None)

    assert gmail_import.get_imported_message_ids(["m-1"]) == set()
    assert gmail_import.get_imported_message_ids([]) == set()


def test_record_processed_message_upserts_full_row(monkeypatch):
    _stub_google_modules()
    from scripts import gmail_import

    conn = _StubConn()
    monkeypatch.setattr(gmail_import, "_get_sync_connection", lambda: conn)

    gmail_import.record_processed_message(
        "m-1",
        status="imported",
        subject="catscan-bidsinauction-123-yesterday-UTC",
        seat_id="123",
        filename="catscan-report-123.csv",
        batch_id="batch-1",
    )

    sql, params = conn.calls[0]
    assert "INSERT INTO gmail_processed_messages" in sql
    assert "ON CONFLICT (gmail_message_id) DO UPDATE" in sql
    assert params == (
        "m-1",
        "catscan-bidsinauction-123-yesterday-UTC",
        "123",
        "catscan-report-123.csv",
        "batch-1",
        "imported",
    )


def test_run_import_records_imported_message_and_marks_read(tmp_path, monkeypatch):
    _stub_google_modules()
    from scripts import gmail_import

    monkeypatch.setattr(gmail_import, "STATUS_PATH", tmp_path / "gmail_import_status.json")
    monkeypatch.setattr(gmail_import, "LOCK_PATH", tmp_path / "gmail_import.lock")
    monkeypatch.setattr(gmail_import, "start_scheduler_ingestion_run", lambda *_a, **_k: "run-1")
    monkeypatch.setattr(gmail_import, "finish_scheduler_ingestion_run", lambda *_a, **_k: None)
    monkeypatch.setattr(
        gmail_import,
        "get_runtime_freshness_snapshot",
        lambda: {
            "runtime_path_verified": True,
            "latest_metric_date": "2026-07-12",
            "rows_on_latest_metric_date": 1,
        },
    )
    monkeypatch.setattr(gmail_import, "get_gmail_service", lambda: (object(), object()))
    monkeypatch.setattr(gmail_import, "build_access_token_provider", lambda *_a, **_k: lambda *_: "token")
    monkeypatch.setattr(gmail_import, "find_report_emails", lambda _service: [{"id": "m-1"}])
    monkeypatch.setattr(gmail_import, "prioritize_report_messages", lambda _service, messages: messages)

    csv_path = tmp_path / "catscan-pipeline-123-report.csv"
    csv_path.write_text("#Day\n2026-07-12\n", encoding="utf-8")
    monkeypatch.setattr(
        gmail_import,
        "process_message",
        lambda *_a, **_k: ([csv_path], "123", "subject", False),
    )
    monkeypatch.setattr(gmail_import, "archive_to_s3", lambda *_a, **_k: None)
    monkeypatch.setattr(gmail_import, "record_import_run", lambda *_a, **_k: None)
    monkeypatch.setattr(gmail_import, "run_pipeline_for_file", lambda *_a, **_k: True)

    class SuccessfulImport:
        success = True
        report_type = "rtb_bidstream_publisher"
        rows_imported = 1
        rows_duplicate = 0
        error = None
        rows_read = 1
        batch_id = "batch-1"
        date_range_start = "2026-07-12"
        date_range_end = "2026-07-12"
        columns_found = "Day"
        file_size_bytes = 10

    monkeypatch.setattr(gmail_import, "import_to_catscan", lambda _filepath: SuccessfulImport())

    recorded: list[dict] = []
    monkeypatch.setattr(
        gmail_import,
        "record_processed_message",
        lambda message_id, **kwargs: recorded.append({"message_id": message_id, **kwargs}),
    )
    marked_read: list[str] = []
    monkeypatch.setattr(
        gmail_import, "mark_as_read", lambda _service, message_id: marked_read.append(message_id)
    )

    result = gmail_import.run_import(verbose=False, job_id="job-1")

    assert result["success"] is True
    assert result["files_imported"] == 1
    assert recorded == [
        {
            "message_id": "m-1",
            "status": "imported",
            "subject": "subject",
            "seat_id": "123",
            "filename": csv_path.name,
            "batch_id": "batch-1",
        }
    ]
    assert marked_read == ["m-1"]
