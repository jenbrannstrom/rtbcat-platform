"""Exception observability tests for creative response builder fallbacks."""

from __future__ import annotations

import logging

import pytest

pytest.importorskip("fastapi")

from services.creative_response_builder import get_stale_threshold_hours


def test_get_stale_threshold_hours_logs_warning_and_defaults_on_invalid_env(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("CREATIVE_CACHE_STALE_HOURS", "not-an-int")

    with caplog.at_level(logging.WARNING):
        value = get_stale_threshold_hours()

    assert value == 24
    assert "Invalid CREATIVE_CACHE_STALE_HOURS value" in caplog.text


def test_get_stale_threshold_hours_clamps_to_minimum_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CREATIVE_CACHE_STALE_HOURS", "0")
    assert get_stale_threshold_hours() == 1
