"""Exception observability tests for rule-based clustering helpers."""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

import pytest


def _load_rule_based_module():
    module_path = Path(__file__).resolve().parents[1] / "api" / "clustering" / "rule_based.py"
    spec = importlib.util.spec_from_file_location("rule_based_test_module", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_extract_domain_logs_debug_and_returns_none_on_parse_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    rule_based = _load_rule_based_module()

    def _raise(*_args, **_kwargs):
        raise RuntimeError("parse failure")

    monkeypatch.setattr(rule_based, "urlparse", _raise)

    with caplog.at_level(logging.DEBUG):
        value = rule_based.extract_domain("https://example.com/path")

    assert value is None
    assert "Failed to parse domain from creative URL" in caplog.text


def test_get_week_key_logs_debug_and_returns_unknown_on_parse_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    rule_based = _load_rule_based_module()

    class _ExplodingDateTime:
        @staticmethod
        def strptime(*_args, **_kwargs):
            raise RuntimeError("datetime parse failed")

    monkeypatch.setattr(rule_based, "datetime", _ExplodingDateTime)

    with caplog.at_level(logging.DEBUG):
        value = rule_based.get_week_key("2026-03-04T00:00:00")

    assert value == "unknown"
    assert "falling back to unknown week key" in caplog.text.lower()
