"""Tests for Authing callback URL hardening helpers."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from api.auth_authing import _get_callback_url, _normalize_host


def _make_request(
    host: str = "example.com",
    *,
    scheme: str = "http",
    client_host: str = "127.0.0.1",
    extra_headers: dict[str, str] | None = None,
) -> Request:
    headers = [(b"host", host.encode("utf-8"))]
    for key, value in (extra_headers or {}).items():
        headers.append((key.lower().encode("utf-8"), value.encode("utf-8")))

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": scheme,
        "path": "/auth/authing/login",
        "raw_path": b"/auth/authing/login",
        "query_string": b"",
        "headers": headers,
        "client": (client_host, 12345),
        "server": ("testserver", 80),
    }
    return Request(scope)


def test_normalize_host_accepts_valid_hosts() -> None:
    assert _normalize_host("example.com") == "example.com"
    assert _normalize_host("example.com:8443") == "example.com:8443"
    assert _normalize_host("[2001:db8::1]:443") == "[2001:db8::1]:443"


def test_normalize_host_rejects_invalid_hosts() -> None:
    assert _normalize_host("") is None
    assert _normalize_host("bad host") is None
    assert _normalize_host("evil.com/path") is None
    assert _normalize_host("user@example.com") is None


def test_get_callback_url_prefers_public_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CATSCAN_PUBLIC_BASE_URL", "https://public.example.com")
    request = _make_request(host="evil.example.com")
    assert _get_callback_url(request) == "https://public.example.com/api/auth/authing/callback"


def test_get_callback_url_uses_trusted_forwarded_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CATSCAN_PUBLIC_BASE_URL", raising=False)
    request = _make_request(
        host="internal.local",
        extra_headers={"x-forwarded-host": "prod.example.com"},
    )
    assert _get_callback_url(request) == "http://prod.example.com/api/auth/authing/callback"


def test_get_callback_url_rejects_invalid_host(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CATSCAN_PUBLIC_BASE_URL", raising=False)
    request = _make_request(host="bad host")
    with pytest.raises(HTTPException) as exc_info:
        _get_callback_url(request)
    assert exc_info.value.status_code == 400
