"""Exception observability tests for SecretsManager fallback paths."""

from __future__ import annotations

import logging

from services.secrets_manager import SecretsConfig, SecretsManager


def test_get_int_logs_warning_and_uses_default_on_invalid_value(
    monkeypatch,
    caplog,
) -> None:
    monkeypatch.setenv("CATSCAN_TIMEOUT_SECONDS", "not-an-int")
    manager = SecretsManager(
        cfg=SecretsConfig(backend="env", name_prefix="catscan", prefer_env=True)
    )

    with caplog.at_level(logging.WARNING):
        value = manager.get_int("CATSCAN_TIMEOUT_SECONDS", default=240)

    assert value == 240
    assert "Failed to parse integer secret/config value; using default" in caplog.text
