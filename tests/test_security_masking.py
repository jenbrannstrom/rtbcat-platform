"""Tests for utils/security.py masking and redaction utilities."""

from __future__ import annotations

import pytest

from utils.security import mask_secret, redact_dict, redact_response_body


# ── mask_secret ──────────────────────────────────────────────────────


class TestMaskSecret:
    def test_long_key_shows_prefix_and_suffix(self):
        assert mask_secret("sk-1234567890abcdef") == "sk-1***cdef"

    def test_short_key_fully_masked(self):
        assert mask_secret("short") == "*****"

    def test_empty_string(self):
        assert mask_secret("") == "***"

    def test_exact_boundary(self):
        # 8 chars = 2*visible(4), should be fully masked
        assert mask_secret("12345678") == "********"

    def test_nine_chars_shows_partial(self):
        assert mask_secret("123456789") == "1234***6789"


# ── redact_dict ──────────────────────────────────────────────────────


class TestRedactDict:
    def test_masks_token_value(self):
        data = {"access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.long_token_value"}
        result = redact_dict(data)
        # Value should be masked (different from original) with *** in the middle
        assert result["access_token"] != data["access_token"]
        assert "***" in result["access_token"]

    def test_masks_api_key(self):
        data = {"api_key": "demo-maskable-value-1234567890"}
        result = redact_dict(data)
        assert result["api_key"] != "demo-maskable-value-1234567890"

    def test_masks_secret(self):
        data = {"client_secret": "supersecretvalue123456"}
        result = redact_dict(data)
        assert "supersecret" not in result["client_secret"]

    def test_preserves_non_sensitive_keys(self):
        data = {"email": "user@example.com", "name": "Test User"}
        result = redact_dict(data)
        assert result == data

    def test_nested_dict_redaction(self):
        data = {"config": {"password": "hunter2", "host": "localhost"}}
        result = redact_dict(data)
        assert result["config"]["host"] == "localhost"
        assert result["config"]["password"] != "hunter2"

    def test_non_string_values_preserved(self):
        data = {"api_key_count": 5, "has_token": True}
        result = redact_dict(data)
        assert result == data


# ── redact_response_body ─────────────────────────────────────────────


class TestRedactResponseBody:
    def test_redacts_access_token(self):
        body = '{"access_token": "eyJhbGciOiJSUzI1NiJ9.payload.sig", "token_type": "Bearer"}'
        result = redact_response_body(body)
        assert "eyJhbGci" not in result
        assert "<REDACTED>" in result

    def test_redacts_refresh_token(self):
        body = '{"refresh_token": "rt-supersecretrefreshtoken"}'
        result = redact_response_body(body)
        assert "supersecret" not in result

    def test_redacts_client_secret(self):
        body = '{"client_secret": "cs_live_secretvalue"}'
        result = redact_response_body(body)
        assert "secretvalue" not in result

    def test_preserves_non_sensitive_fields(self):
        body = '{"email": "user@example.com", "name": "Test"}'
        result = redact_response_body(body)
        assert "user@example.com" in result

    def test_empty_body(self):
        assert redact_response_body("") == "<empty>"

    def test_truncation_of_long_body(self):
        body = "x" * 500
        result = redact_response_body(body, max_length=100)
        assert len(result) < 200
        assert "<truncated>" in result

    def test_case_insensitive_key_matching(self):
        body = '{"Access_Token": "secret123"}'
        result = redact_response_body(body)
        assert "secret123" not in result
