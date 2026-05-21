"""Tests for Gmail import status surface fields."""

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


def test_gmail_status_includes_unread_report_count(tmp_path, monkeypatch):
    _stub_google_modules()

    from scripts import gmail_import

    status_path = tmp_path / "gmail_import_status.json"
    lock_path = tmp_path / "gmail_import.lock"

    monkeypatch.setattr(gmail_import, "STATUS_PATH", status_path)
    monkeypatch.setattr(gmail_import, "LOCK_PATH", lock_path)

    gmail_import.update_status(
        success=True,
        files_imported=0,
        emails_processed=0,
        reason="no_new_mail",
        unread_report_emails=44,
    )

    status = gmail_import.get_status()
    assert status["last_unread_report_emails"] == 44
    assert status["recent_history"][0]["unread_report_emails"] == 44


def test_gmail_status_includes_file_failures(tmp_path, monkeypatch):
    _stub_google_modules()

    from scripts import gmail_import

    status_path = tmp_path / "gmail_import_status.json"
    lock_path = tmp_path / "gmail_import.lock"

    monkeypatch.setattr(gmail_import, "STATUS_PATH", status_path)
    monkeypatch.setattr(gmail_import, "LOCK_PATH", lock_path)

    failure = {
        "message_id": "msg-1",
        "filename": "catscan-report-6574658621.csv",
        "seat_id": "6574658621",
        "report_kind": "bid_filtering",
        "error": "PostgreSQL text fields cannot contain NUL (0x00) bytes",
    }

    gmail_import.update_status(
        success=True,
        files_imported=18,
        emails_processed=20,
        reason="import_completed_with_failures",
        unread_report_emails=20,
        file_failures=[failure],
    )

    status = gmail_import.get_status()
    assert status["last_file_failure_count"] == 1
    assert status["last_file_failures"] == [failure]
    assert status["recent_history"][0]["file_failure_count"] == 1
    assert status["recent_history"][0]["file_failures"] == [failure]


def test_run_import_records_failed_file_in_result_and_status(tmp_path, monkeypatch):
    _stub_google_modules()

    from scripts import gmail_import

    status_path = tmp_path / "gmail_import_status.json"
    lock_path = tmp_path / "gmail_import.lock"
    bad_csv = tmp_path / "catscan-report-6574658621.csv"
    bad_csv.write_text("bad", encoding="utf-8")

    monkeypatch.setattr(gmail_import, "STATUS_PATH", status_path)
    monkeypatch.setattr(gmail_import, "LOCK_PATH", lock_path)
    monkeypatch.setattr(gmail_import, "start_scheduler_ingestion_run", lambda *_args, **_kwargs: "run-1")
    monkeypatch.setattr(gmail_import, "finish_scheduler_ingestion_run", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        gmail_import,
        "get_runtime_freshness_snapshot",
        lambda: {
            "runtime_path_verified": True,
            "latest_metric_date": "2026-05-12",
            "rows_on_latest_metric_date": 1,
        },
    )
    monkeypatch.setattr(gmail_import, "get_gmail_service", lambda: (object(), object()))
    monkeypatch.setattr(gmail_import, "build_access_token_provider", lambda *_args, **_kwargs: lambda *_: "token")
    monkeypatch.setattr(gmail_import, "find_report_emails", lambda _service: [{"id": "msg-1"}])
    monkeypatch.setattr(
        gmail_import,
        "process_message",
        lambda *_args, **_kwargs: ([bad_csv], "6574658621", "subject", False),
    )
    monkeypatch.setattr(gmail_import, "archive_to_s3", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(gmail_import, "record_import_run", lambda *_args, **_kwargs: None)

    class FailedImport:
        success = False
        report_type = "bid_filtering"
        rows_imported = 0
        rows_duplicate = 0
        error = "PostgreSQL text fields cannot contain NUL (0x00) bytes"
        rows_read = 10
        batch_id = "batch-1"
        date_range_start = "2026-05-11"
        date_range_end = "2026-05-11"
        columns_found = "Creative ID"
        file_size_bytes = 3

    monkeypatch.setattr(gmail_import, "import_to_catscan", lambda _filepath: FailedImport())

    result = gmail_import.run_import(verbose=False, job_id="job-1")

    assert result["success"] is True
    assert result["file_failure_count"] == 1
    assert result["file_failures"][0]["filename"] == bad_csv.name
    assert result["file_failures"][0]["seat_id"] == "6574658621"
    assert "Import failed for" in result["errors"][0]

    status = gmail_import.get_status()
    assert status["last_reason"] == "import_completed_with_failures"
    assert status["last_file_failure_count"] == 1
