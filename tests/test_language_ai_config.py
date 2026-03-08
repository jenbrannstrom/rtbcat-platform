"""Tests for language AI provider selection and key resolution."""

import pytest

from services import language_ai_config


class StubStore:
    def __init__(self, values: dict[str, str] | None = None):
        self.values = values or {}
        self.writes: list[tuple[str, str, str | None]] = []

    async def get_setting(self, key: str):
        return self.values.get(key)

    async def set_setting(self, key: str, value: str, updated_by: str | None = None):
        self.values[key] = value
        self.writes.append((key, value, updated_by))


class StubSecretsManager:
    def __init__(self, values: dict[str, str] | None = None):
        self.values = values or {}

    def get(self, key: str):
        return self.values.get(key)


def test_normalize_language_ai_provider_defaults_to_gemini():
    assert language_ai_config.normalize_language_ai_provider(None) == "gemini"
    assert language_ai_config.normalize_language_ai_provider("unknown") == "gemini"


def test_normalize_language_ai_provider_accepts_supported_values():
    assert language_ai_config.normalize_language_ai_provider("claude") == "claude"
    assert language_ai_config.normalize_language_ai_provider("  GROK ") == "grok"


@pytest.mark.asyncio
async def test_selected_provider_prefers_store_over_env(monkeypatch):
    monkeypatch.setenv("CATSCAN_LANGUAGE_AI_PROVIDER", "grok")
    store = StubStore({"language_ai_provider": "claude"})

    provider = await language_ai_config.get_selected_language_ai_provider(store)

    assert provider == "claude"


@pytest.mark.asyncio
async def test_selected_provider_uses_env_when_store_missing(monkeypatch):
    monkeypatch.setenv("CATSCAN_LANGUAGE_AI_PROVIDER", "grok")

    provider = await language_ai_config.get_selected_language_ai_provider(StubStore())

    assert provider == "grok"


@pytest.mark.asyncio
async def test_set_selected_provider_normalizes_and_persists():
    store = StubStore()

    provider = await language_ai_config.set_selected_language_ai_provider(
        store,
        "CLAUDE",
        updated_by="test-suite",
    )

    assert provider == "claude"
    assert store.values["language_ai_provider"] == "claude"
    assert store.writes == [("language_ai_provider", "claude", "test-suite")]


@pytest.mark.asyncio
async def test_get_provider_api_key_prefers_store(monkeypatch):
    monkeypatch.setattr(
        language_ai_config,
        "get_secrets_manager",
        lambda: StubSecretsManager({"ANTHROPIC_API_KEY": "env-claude-key"}),
    )
    store = StubStore({"claude_api_key": "db-claude-key"})

    api_key = await language_ai_config.get_provider_api_key(store, "claude")

    assert api_key == "db-claude-key"


@pytest.mark.asyncio
async def test_get_provider_api_key_falls_back_to_secrets_manager(monkeypatch):
    monkeypatch.setattr(
        language_ai_config,
        "get_secrets_manager",
        lambda: StubSecretsManager({"XAI_API_KEY": "env-grok-key"}),
    )

    api_key = await language_ai_config.get_provider_api_key(StubStore(), "grok")

    assert api_key == "env-grok-key"


@pytest.mark.asyncio
async def test_get_all_provider_key_statuses_reports_each_provider(monkeypatch):
    monkeypatch.setattr(
        language_ai_config,
        "get_secrets_manager",
        lambda: StubSecretsManager(
            {
                "GEMINI_API_KEY": "gemini-secret-1234",
                "XAI_API_KEY": "xai-secret-5678",
            }
        ),
    )
    store = StubStore({"claude_api_key": "claude-db-secret"})

    statuses = await language_ai_config.get_all_provider_key_statuses(store)

    assert set(statuses) == {"gemini", "claude", "grok"}
    assert statuses["gemini"]["configured"] is True
    assert statuses["gemini"]["source"] == "environment"
    assert statuses["claude"]["configured"] is True
    assert statuses["claude"]["source"] == "database"
    assert statuses["grok"]["configured"] is True
    assert statuses["grok"]["source"] == "environment"
