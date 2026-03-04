"""Resilience tests for background language analysis in seats router."""

from __future__ import annotations

import logging
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

pytest.importorskip("fastapi")

from api.routers import seats as seats_router


class _FailingCreativeRepo:
    def __init__(self) -> None:
        self.update_attempts = 0

    async def get_creatives_needing_language_analysis(self, limit: int = 50):
        del limit
        return [
            SimpleNamespace(
                id="cr-1",
                raw_data={"html": "<html></html>"},
                format="HTML",
            )
        ]

    async def update_language_detection(self, **kwargs):
        del kwargs
        self.update_attempts += 1
        raise RuntimeError("db write failed")


class _Store:
    def __init__(self) -> None:
        self.creative_repository = _FailingCreativeRepo()
        self.db_path = "/tmp/catscan-test.db"


@pytest.mark.asyncio
async def test_trigger_background_language_analysis_survives_error_persist_failure(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class _Analyzer:
        def __init__(self, provider: str, api_key: str, db_path: str | None):
            del provider, api_key, db_path
            self.is_configured = True

        async def analyze_creative(self, **kwargs):
            del kwargs
            raise RuntimeError("ai provider failed")

    fake_module = types.ModuleType("api.analysis.language_analyzer")
    fake_module.LanguageAnalyzer = _Analyzer
    monkeypatch.setitem(sys.modules, "api.analysis.language_analyzer", fake_module)

    monkeypatch.setattr(
        seats_router,
        "get_selected_language_ai_provider",
        AsyncMock(return_value="openai"),
    )

    class _ConfigService:
        async def get_ai_provider_api_key(self, store, provider: str):
            del store, provider
            return "test-key"

    monkeypatch.setattr(seats_router, "ConfigService", lambda: _ConfigService())

    store = _Store()
    with caplog.at_level(logging.WARNING):
        analyzed = await seats_router._trigger_background_language_analysis(store, limit=5)

    assert analyzed == 0
    assert store.creative_repository.update_attempts == 1
    assert "Failed to analyze language for creative cr-1" in caplog.text
    assert "Failed to persist language-analysis error for creative cr-1" in caplog.text
