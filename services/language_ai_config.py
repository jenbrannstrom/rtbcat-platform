"""Language AI provider configuration helpers.

This module centralizes provider selection and API-key resolution for
creative language and geo-linguistic analysis.
"""

from __future__ import annotations

import os
from typing import Any, Optional

from services.secrets_manager import get_secrets_manager

SUPPORTED_LANGUAGE_AI_PROVIDERS: tuple[str, ...] = ("gemini", "claude", "grok")
DEFAULT_LANGUAGE_AI_PROVIDER = "gemini"

LANGUAGE_AI_PROVIDER_SETTING_KEY = "language_ai_provider"

_PROVIDER_TO_SETTING_KEY: dict[str, str] = {
    "gemini": "gemini_api_key",
    "claude": "claude_api_key",
    "grok": "grok_api_key",
}

_PROVIDER_TO_ENV_KEY: dict[str, str] = {
    "gemini": "GEMINI_API_KEY",
    "claude": "ANTHROPIC_API_KEY",
    "grok": "XAI_API_KEY",
}


def normalize_language_ai_provider(provider: Optional[str]) -> str:
    """Normalize and validate provider value, returning a safe default."""
    if not provider:
        return DEFAULT_LANGUAGE_AI_PROVIDER
    normalized = provider.strip().lower()
    if normalized not in SUPPORTED_LANGUAGE_AI_PROVIDERS:
        return DEFAULT_LANGUAGE_AI_PROVIDER
    return normalized


def get_provider_setting_key(provider: Optional[str]) -> str:
    """Return DB setting key for provider API key."""
    normalized = normalize_language_ai_provider(provider)
    return _PROVIDER_TO_SETTING_KEY[normalized]


def get_provider_env_key(provider: Optional[str]) -> str:
    """Return env/secrets key for provider API key."""
    normalized = normalize_language_ai_provider(provider)
    return _PROVIDER_TO_ENV_KEY[normalized]


def mask_api_key(key: str) -> str:
    """Mask API key for non-sensitive status display."""
    if len(key) <= 10:
        return "*" * len(key)
    return f"{key[:4]}...{key[-4:]}"


async def get_selected_language_ai_provider(store: Any) -> str:
    """Get selected language AI provider from DB setting or env fallback."""
    stored_value: Optional[str] = None
    if store and hasattr(store, "get_setting"):
        stored_value = await store.get_setting(LANGUAGE_AI_PROVIDER_SETTING_KEY)

    env_value = os.getenv("CATSCAN_LANGUAGE_AI_PROVIDER")
    return normalize_language_ai_provider(stored_value or env_value)


async def set_selected_language_ai_provider(
    store: Any,
    provider: str,
    updated_by: Optional[str] = None,
) -> str:
    """Persist selected language AI provider setting."""
    normalized = normalize_language_ai_provider(provider)
    if store and hasattr(store, "set_setting"):
        await store.set_setting(
            LANGUAGE_AI_PROVIDER_SETTING_KEY,
            normalized,
            updated_by=updated_by,
        )
    return normalized


async def get_provider_api_key(store: Any, provider: Optional[str]) -> Optional[str]:
    """Resolve provider API key from DB (preferred) then secrets/env."""
    normalized = normalize_language_ai_provider(provider)
    setting_key = get_provider_setting_key(normalized)

    stored_value: Optional[str] = None
    if store and hasattr(store, "get_setting"):
        stored_value = await store.get_setting(setting_key)
        if stored_value:
            return stored_value

    env_key = get_provider_env_key(normalized)
    return get_secrets_manager().get(env_key)


async def get_provider_key_status(store: Any, provider: str) -> dict[str, Any]:
    """Get non-sensitive key status for a provider."""
    normalized = normalize_language_ai_provider(provider)
    setting_key = get_provider_setting_key(normalized)
    env_key = get_provider_env_key(normalized)

    stored_key: Optional[str] = None
    if store and hasattr(store, "get_setting"):
        stored_key = await store.get_setting(setting_key)

    if stored_key:
        return {
            "provider": normalized,
            "configured": True,
            "masked_key": mask_api_key(stored_key),
            "source": "database",
            "message": f"{normalized.capitalize()} API key configured from database",
        }

    env_key_value = get_secrets_manager().get(env_key)
    if env_key_value:
        return {
            "provider": normalized,
            "configured": True,
            "masked_key": mask_api_key(env_key_value),
            "source": "environment",
            "message": f"{normalized.capitalize()} API key configured from environment variable",
        }

    return {
        "provider": normalized,
        "configured": False,
        "masked_key": None,
        "source": None,
        "message": f"{normalized.capitalize()} API key not configured",
    }


async def get_all_provider_key_statuses(store: Any) -> dict[str, dict[str, Any]]:
    """Get key status for all supported language AI providers."""
    statuses: dict[str, dict[str, Any]] = {}
    for provider in SUPPORTED_LANGUAGE_AI_PROVIDERS:
        statuses[provider] = await get_provider_key_status(store, provider)
    return statuses

