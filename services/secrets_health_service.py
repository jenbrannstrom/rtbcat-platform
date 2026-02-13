"""Secrets health checks for startup validation and status endpoint."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone

from services.secrets_manager import get_secrets_manager


def _env_true(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class FeatureCheck:
    name: str
    description: str
    required_keys: tuple[str, ...]
    enabled: bool


def _is_authing_enabled() -> bool:
    if _env_true("NEXT_PUBLIC_ENABLE_AUTHING_LOGIN", default=False):
        return True
    return any(
        os.getenv(k)
        for k in ("AUTHING_APP_ID", "AUTHING_APP_SECRET", "AUTHING_ISSUER")
    )


def _is_gmail_scheduler_enabled() -> bool:
    return _env_true("CATSCAN_ENABLE_GMAIL_IMPORT_SCHEDULER", default=False) or bool(
        os.getenv("GMAIL_IMPORT_SECRET")
    )


def _is_precompute_scheduler_enabled() -> bool:
    return _env_true("CATSCAN_ENABLE_PRECOMPUTE_SCHEDULER", default=False) or any(
        os.getenv(k) for k in ("PRECOMPUTE_REFRESH_SECRET", "PRECOMPUTE_MONITOR_SECRET")
    )


def _is_creative_cache_scheduler_enabled() -> bool:
    return _env_true("CATSCAN_ENABLE_CREATIVE_CACHE_SCHEDULER", default=False) or bool(
        os.getenv("CREATIVE_CACHE_REFRESH_SECRET")
    )


def _is_gemini_enabled() -> bool:
    return _env_true("CATSCAN_ENABLE_LANGUAGE_AI", default=False) or bool(
        os.getenv("GEMINI_API_KEY")
    )


def _is_clustering_enabled() -> bool:
    return _env_true("CATSCAN_ENABLE_CLUSTERING_AI", default=False) or bool(
        os.getenv("ANTHROPIC_API_KEY")
    )


def _is_oauth2_proxy_enabled() -> bool:
    return _env_true("OAUTH2_PROXY_ENABLED", default=False)


def _is_oauth_client_secret_required_in_api() -> bool:
    """Whether API startup should require Google OAuth client secret.

    Most deployments run oauth2-proxy as a separate process/service, so the API
    does not need `GOOGLE_OAUTH_CLIENT_SECRET` locally. Keep this opt-in.
    """
    return _env_true("CATSCAN_REQUIRE_OAUTH_CLIENT_SECRET_IN_API", default=False)


def _feature_checks() -> list[FeatureCheck]:
    return [
        FeatureCheck(
            name="authing_oidc",
            description="Authing login/callback endpoints",
            required_keys=("AUTHING_APP_ID", "AUTHING_APP_SECRET", "AUTHING_ISSUER"),
            enabled=_is_authing_enabled(),
        ),
        FeatureCheck(
            name="gmail_import_scheduler",
            description="Scheduled Gmail import endpoint",
            required_keys=("GMAIL_IMPORT_SECRET",),
            enabled=_is_gmail_scheduler_enabled(),
        ),
        FeatureCheck(
            name="precompute_scheduler",
            description="Scheduled precompute refresh/monitor endpoints",
            required_keys=("PRECOMPUTE_REFRESH_SECRET", "PRECOMPUTE_MONITOR_SECRET"),
            enabled=_is_precompute_scheduler_enabled(),
        ),
        FeatureCheck(
            name="creative_cache_scheduler",
            description="Scheduled creative cache refresh endpoint",
            required_keys=("CREATIVE_CACHE_REFRESH_SECRET",),
            enabled=_is_creative_cache_scheduler_enabled(),
        ),
        FeatureCheck(
            name="gemini_language_ai",
            description="Gemini language detection",
            required_keys=("GEMINI_API_KEY",),
            enabled=_is_gemini_enabled(),
        ),
        FeatureCheck(
            name="anthropic_clustering_ai",
            description="Anthropic clustering analysis",
            required_keys=("ANTHROPIC_API_KEY",),
            enabled=_is_clustering_enabled(),
        ),
        FeatureCheck(
            name="oauth2_proxy",
            description="Google OAuth2 Proxy authentication",
            required_keys=(
                ("GOOGLE_OAUTH_CLIENT_SECRET",)
                if _is_oauth_client_secret_required_in_api()
                else ()
            ),
            enabled=_is_oauth2_proxy_enabled(),
        ),
    ]


def get_secrets_health(strict_mode: bool | None = None) -> dict:
    """Check required secrets for enabled features.

    Returns non-sensitive status only (no secret values).
    """
    strict = _env_true("SECRETS_HEALTH_STRICT", default=False) if strict_mode is None else strict_mode
    manager = get_secrets_manager()
    checks = _feature_checks()

    enabled_features = [c for c in checks if c.enabled]
    feature_results = []
    missing_required_keys: list[str] = []

    for feature in checks:
        keys = []
        missing = []
        for key in feature.required_keys:
            configured = bool(manager.get(key))
            keys.append({"key": key, "configured": configured})
            if feature.enabled and not configured:
                missing.append(key)
                missing_required_keys.append(key)
        feature_results.append(
            {
                "name": feature.name,
                "description": feature.description,
                "enabled": feature.enabled,
                "healthy": len(missing) == 0,
                "required_keys": keys,
                "missing_keys": missing,
            }
        )

    unique_missing = sorted(set(missing_required_keys))
    healthy = len(unique_missing) == 0

    required_key_count = sum(len(c.required_keys) for c in enabled_features)
    configured_key_count = required_key_count - len(unique_missing)

    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "strict_mode": strict,
        "healthy": healthy,
        "backend": manager.cfg.backend,
        "prefer_env": manager.cfg.prefer_env,
        "name_prefix": manager.cfg.name_prefix,
        "summary": {
            "enabled_features": len(enabled_features),
            "required_keys": required_key_count,
            "configured_keys": configured_key_count,
            "missing_keys": len(unique_missing),
        },
        "missing_required_keys": unique_missing,
        "features": feature_results,
    }
