"""Exception observability tests for campaign router helper fallbacks."""

from __future__ import annotations

import logging

import pytest

pytest.importorskip("fastapi")

import api.campaigns_router as campaigns_router


def test_extract_reference_domain_logs_debug_and_returns_none_on_parse_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def _raise(*_args, **_kwargs):
        raise RuntimeError("parse failed")

    monkeypatch.setattr(campaigns_router, "urlparse", _raise)

    with caplog.at_level(logging.DEBUG):
        result = campaigns_router._extract_reference_domain("https://example.com/path")

    assert result is None
    assert "Failed to extract reference domain from campaign URL" in caplog.text
