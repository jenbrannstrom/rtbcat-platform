"""Regression tests for Gmail import OAuth token refresh handling."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
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


def test_download_from_url_refreshes_token_on_401(monkeypatch, tmp_path):
    _stub_google_modules()
    from scripts import gmail_import

    monkeypatch.setattr(gmail_import, "IMPORTS_DIR", tmp_path)
    monkeypatch.setattr(gmail_import, "download_via_gcs_client", lambda *args, **kwargs: False)

    auth_headers = []
    provider_calls = []

    def token_provider(force_refresh: bool = False):
        provider_calls.append(force_refresh)
        return "refreshed-token" if force_refresh else "initial-token"

    class _Resp:
        def __init__(self, status_code: int, body: bytes, text: str):
            self.status_code = status_code
            self._body = body
            self.text = text

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def iter_content(self, chunk_size: int = 1024 * 1024):
            yield self._body

    def fake_get(url, headers, stream, timeout):
        del url, stream, timeout
        auth_headers.append(headers.get("Authorization"))
        if len(auth_headers) == 1:
            return _Resp(401, b"", "AuthenticationRequired")
        return _Resp(200, b"col1,col2\n1,2\n", "")

    monkeypatch.setattr("requests.get", fake_get)

    files = gmail_import.download_from_url(
        "https://storage.cloud.google.com/buyside-scheduled-report-export/path/report.csv",
        "message-123",
        access_token="initial-token",
        seat_id="1487810529",
        access_token_provider=token_provider,
    )

    assert len(files) == 1
    assert files[0].exists()
    assert files[0].read_text() == "col1,col2\n1,2\n"
    assert auth_headers == ["Bearer initial-token", "Bearer refreshed-token"]
    assert provider_calls == [True]


def test_access_token_provider_force_refresh_persists_token(monkeypatch, tmp_path):
    _stub_google_modules()
    from scripts import gmail_import

    token_path = tmp_path / "gmail-token.json"
    monkeypatch.setattr(gmail_import, "TOKEN_PATH", token_path)

    class _FakeCreds:
        def __init__(self):
            self.token = "token-v1"
            self.valid = True
            self.refresh_token = "refresh-token"
            self.expiry = datetime.now() + timedelta(minutes=10)
            self.refresh_calls = 0

        def refresh(self, request):  # noqa: ARG002
            self.refresh_calls += 1
            self.token = f"token-v{self.refresh_calls + 1}"
            self.valid = True
            self.expiry = datetime.now() + timedelta(hours=1)

        def to_json(self):
            return '{"token":"%s"}' % self.token

    creds = _FakeCreds()
    provider = gmail_import.build_access_token_provider(creds, verbose=False)

    token_before = provider(False)
    token_after = provider(True)

    assert token_before == "token-v1"
    assert token_after == "token-v2"
    assert creds.refresh_calls == 1
    assert token_path.exists()
    assert "token-v2" in token_path.read_text()
