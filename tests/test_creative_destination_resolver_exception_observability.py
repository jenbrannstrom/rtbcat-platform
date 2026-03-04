"""Exception observability tests for creative destination resolver fallbacks."""

from __future__ import annotations

import logging

import pytest

import services.creative_destination_resolver as resolver


def test_classify_click_destination_logs_debug_and_returns_invalid_url_on_parse_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def _raise(*_args, **_kwargs):
        raise RuntimeError("url parse failed")

    monkeypatch.setattr(resolver, "urlparse", _raise)

    with caplog.at_level(logging.DEBUG):
        is_valid, reason = resolver.classify_click_destination("https://example.com/path")

    assert is_valid is False
    assert reason == "invalid_url"
    assert "marking as invalid_url" in caplog.text.lower()
