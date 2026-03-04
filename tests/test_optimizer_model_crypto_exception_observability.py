"""Exception observability tests for optimizer model crypto fallbacks."""

from __future__ import annotations

import logging

import pytest

import services.optimizer_model_crypto as crypto


def test_get_fernet_logs_warning_and_returns_none_on_init_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    crypto.clear_optimizer_model_crypto_cache()
    monkeypatch.setenv("CATSCAN_OPTIMIZER_MODEL_SECRET_KEY", "definitely-not-valid")

    class _ExplodingFernet:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("init failed")

    monkeypatch.setattr(crypto, "Fernet", _ExplodingFernet)

    with caplog.at_level(logging.WARNING):
        result = crypto._get_fernet()

    assert result is None
    assert "Failed to initialize optimizer model Fernet crypto" in caplog.text


def test_normalize_fernet_key_logs_debug_when_base64_decode_fails(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.DEBUG):
        key = crypto._normalize_fernet_key("not-base64-key")

    assert isinstance(key, bytes)
    assert len(key) > 0
    assert "not a valid fernet token" in caplog.text.lower()
