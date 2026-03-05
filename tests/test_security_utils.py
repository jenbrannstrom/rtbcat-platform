"""Tests for API security helper utilities."""

from __future__ import annotations

from api.security_utils import has_valid_scheduler_secret


def test_has_valid_scheduler_secret_accepts_exact_ascii_match() -> None:
    assert has_valid_scheduler_secret("abc123", "abc123") is True


def test_has_valid_scheduler_secret_rejects_missing_values() -> None:
    assert has_valid_scheduler_secret(None, "abc123") is False
    assert has_valid_scheduler_secret("abc123", None) is False
    assert has_valid_scheduler_secret("", "abc123") is False
    assert has_valid_scheduler_secret("abc123", "") is False


def test_has_valid_scheduler_secret_rejects_mismatch() -> None:
    assert has_valid_scheduler_secret("abc123", "abc124") is False


def test_has_valid_scheduler_secret_returns_false_for_non_ascii_strings() -> None:
    # `secrets.compare_digest` on str may raise for non-ASCII; helper must return False.
    secret = "\u00e1-secret"
    provided = "\u00e1-secret"
    assert has_valid_scheduler_secret(secret, provided) is False
