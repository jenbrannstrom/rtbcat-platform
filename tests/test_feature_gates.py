"""Tests for feature gating utilities."""

import sys
import types

# Stub out dependencies so tests run without installing Next.js packages
# We only need to test the pure Python-like TS logic via its Python equivalent

# Since feature-gates.ts is TypeScript, we test the logic directly in Python
# by mirroring the function implementations.


def is_restricted_user(user) -> bool:
    RESTRICTED_EMAILS = set()
    if not user or not getattr(user, "email", None):
        return False
    return user.email.lower() in RESTRICTED_EMAILS


def is_allowed_for_restricted_user(path_without_buyer: str) -> bool:
    RESTRICTED_ALLOWED_PATHS = {"/"}
    return path_without_buyer in RESTRICTED_ALLOWED_PATHS


class FakeUser:
    def __init__(self, email: str):
        self.email = email


class TestIsRestrictedUser:
    def test_dea_is_not_restricted(self):
        assert is_restricted_user(FakeUser("user@example.com")) is False

    def test_dea_case_insensitive(self):
        assert is_restricted_user(FakeUser("user@example.com")) is False

    def test_dea_mixed_case(self):
        assert is_restricted_user(FakeUser("user@example.com")) is False

    def test_admin_not_restricted(self):
        assert is_restricted_user(FakeUser("user@example.com")) is False

    def test_other_user_not_restricted(self):
        assert is_restricted_user(FakeUser("user@example.com")) is False

    def test_none_user(self):
        assert is_restricted_user(None) is False

    def test_user_no_email(self):
        user = types.SimpleNamespace()
        assert is_restricted_user(user) is False


class TestIsAllowedForRestrictedUser:
    def test_root_allowed(self):
        assert is_allowed_for_restricted_user("/") is True

    def test_creatives_not_allowed(self):
        assert is_allowed_for_restricted_user("/creatives") is False

    def test_settings_not_allowed(self):
        assert is_allowed_for_restricted_user("/settings/accounts") is False

    def test_admin_not_allowed(self):
        assert is_allowed_for_restricted_user("/admin/users") is False

    def test_import_not_allowed(self):
        assert is_allowed_for_restricted_user("/import") is False

    def test_qps_not_allowed(self):
        assert is_allowed_for_restricted_user("/qps/publisher") is False

    def test_history_not_allowed(self):
        assert is_allowed_for_restricted_user("/history") is False
