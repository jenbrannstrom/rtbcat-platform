"""Authentication provider feature flags and discovery helpers."""

from __future__ import annotations

import os
from typing import Literal, cast

from services.secrets_manager import get_secrets_manager

AuthMethod = Literal["password", "google", "authing"]


def _env_enabled(name: str, default: bool) -> bool:
    """Parse boolean feature flags from environment variables."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def is_password_login_enabled() -> bool:
    """Whether email/password login is enabled."""
    return _env_enabled("CATSCAN_ENABLE_PASSWORD_LOGIN", True)


def is_google_login_enabled() -> bool:
    """Whether Google login via OAuth2 Proxy is enabled."""
    if not _env_enabled("CATSCAN_ENABLE_GOOGLE_LOGIN", True):
        return False
    return _env_enabled("OAUTH2_PROXY_ENABLED", False)


def is_authing_configured() -> bool:
    """Whether required Authing secrets are present."""
    secrets_mgr = get_secrets_manager()
    app_id = (secrets_mgr.get("AUTHING_APP_ID") or "").strip()
    app_secret = (secrets_mgr.get("AUTHING_APP_SECRET") or "").strip()
    issuer = (secrets_mgr.get("AUTHING_ISSUER") or "").strip()
    return bool(app_id and app_secret and issuer)


def is_authing_login_enabled() -> bool:
    """Whether Authing OIDC login is enabled and configured."""
    if not _env_enabled("CATSCAN_ENABLE_AUTHING_LOGIN", True):
        return False
    return is_authing_configured()


def get_enabled_auth_methods() -> list[AuthMethod]:
    """Return enabled authentication methods in preferred display order."""
    methods: list[AuthMethod] = []
    if is_authing_login_enabled():
        methods.append("authing")
    if is_google_login_enabled():
        methods.append("google")
    if is_password_login_enabled():
        methods.append("password")
    return methods


def get_default_auth_method(enabled_methods: list[AuthMethod] | None = None) -> AuthMethod:
    """Choose default login method from env preference and enabled methods."""
    enabled = enabled_methods or get_enabled_auth_methods()

    preferred = os.environ.get("CATSCAN_DEFAULT_LOGIN_METHOD", "").strip().lower()
    if preferred in enabled:
        return cast(AuthMethod, preferred)

    for method in ("authing", "google", "password"):
        if method in enabled:
            return cast(AuthMethod, method)

    return "password"


def get_auth_provider_status() -> dict[str, object]:
    """Get runtime login-provider availability for the frontend."""
    enabled_methods = get_enabled_auth_methods()
    return {
        "password": "password" in enabled_methods,
        "google": "google" in enabled_methods,
        "authing": "authing" in enabled_methods,
        "enabled_methods": enabled_methods,
        "default_method": get_default_auth_method(enabled_methods),
    }
