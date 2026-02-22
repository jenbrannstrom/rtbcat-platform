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
