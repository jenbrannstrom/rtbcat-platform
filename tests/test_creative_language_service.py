"""Tests for creative language analysis orchestration."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from services.creative_language_service import CreativeLanguageService


class _Repo:
    def __init__(self) -> None:
        self.updated: dict | None = None

    async def update_language_detection(self, **kwargs):
        self.updated = kwargs


class _Store:
    def __init__(self) -> None:
        self.creative_repository = _Repo()
        self.saved_creatives = []
        self.thumbnail_status = None

    async def save_creatives(self, creatives):
        self.saved_creatives.extend(creatives)

    async def get_thumbnail_status(self, creative_id):
        return self.thumbnail_status


class _FakeClient:
    async def get_creative_by_id(self, *, creative_id: str, view: str, buyer_id: str):
        assert creative_id == "2014265280192819202"
        assert view == "FULL"
        assert buyer_id == "1487810529"
        return {
            "creativeId": creative_id,
            "creativeName": f"buyers/{buyer_id}/creatives/{creative_id}",
            "format": "HTML",
            "accountId": buyer_id,
            "buyerId": buyer_id,
            "html": {
                "snippet": "<div>मिटाना</div>",
                "width": 320,
                "height": 50,
            },
        }


class _FakeCacheService:
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def resolve_live_client(self, creative):
        assert creative.id == "2014265280192819202"
        return _FakeClient()


@pytest.mark.asyncio
async def test_analyze_language_uses_live_creative_payload(monkeypatch):
    store = _Store()
    creative = SimpleNamespace(
        id="2014265280192819202",
        buyer_id="1487810529",
        campaign_id=None,
        cluster_id=None,
        seat_name="Amazing Design Tools LLC",
        format="HTML",
        raw_data={"html": {"snippet": ""}},
        detected_language=None,
        detected_language_code=None,
        language_confidence=None,
        language_source=None,
        language_analyzed_at=None,
        language_analysis_error=None,
    )
    analyzed_payloads = []

    async def _provider(store):
        return "gemini"

    class _ConfigService:
        async def get_ai_provider_api_key(self, store, provider):
            return "test-gemini-key"

    class _Analyzer:
        def __init__(self, **kwargs) -> None:
            self.is_configured = True

        async def analyze_creative(self, *, creative_id, raw_data, creative_format):
            analyzed_payloads.append((creative_id, raw_data, creative_format))
            return SimpleNamespace(
                language="Hindi",
                language_code="hi",
                confidence=0.95,
                source="gemini_vision_rendered_screenshot",
                error=None,
                success=True,
            )

    monkeypatch.setattr(
        "services.creative_language_service.get_selected_language_ai_provider",
        _provider,
    )
    monkeypatch.setattr(
        "services.creative_language_service.ConfigService",
        _ConfigService,
    )
    monkeypatch.setattr(
        "services.creative_language_service.CreativeCacheService",
        _FakeCacheService,
    )
    monkeypatch.setattr(
        "api.analysis.language_analyzer.LanguageAnalyzer",
        _Analyzer,
    )

    result = await CreativeLanguageService().analyze_language(
        creative=creative,
        store=store,
        force=True,
    )

    assert result["success"] is True
    assert result["detected_language_code"] == "hi"
    assert store.saved_creatives
    assert analyzed_payloads[0][1]["html"]["snippet"] == "<div>मिटाना</div>"
    assert analyzed_payloads[0][2] == "HTML"
    assert store.creative_repository.updated["detected_language_code"] == "hi"


@pytest.mark.asyncio
async def test_analyze_language_attaches_html_thumbnail_hint(monkeypatch):
    store = _Store()
    store.thumbnail_status = {"thumbnail_url": "https://cdn.example.com/html-thumb.png"}
    creative = SimpleNamespace(
        id="2014265280192819202",
        buyer_id="1487810529",
        campaign_id=None,
        cluster_id=None,
        seat_name="Amazing Design Tools LLC",
        format="HTML",
        raw_data={"html": {"snippet": ""}},
        detected_language=None,
        detected_language_code=None,
        language_confidence=None,
        language_source=None,
        language_analyzed_at=None,
        language_analysis_error=None,
    )
    analyzed_payloads = []

    async def _provider(store):
        return "gemini"

    class _ConfigService:
        async def get_ai_provider_api_key(self, store, provider):
            return "test-gemini-key"

    class _Analyzer:
        def __init__(self, **kwargs) -> None:
            self.is_configured = True

        async def analyze_creative(self, *, creative_id, raw_data, creative_format):
            analyzed_payloads.append(raw_data)
            return SimpleNamespace(
                language="Hindi",
                language_code="hi",
                confidence=0.95,
                source="gemini_vision",
                error=None,
                success=True,
            )

    monkeypatch.setattr("services.creative_language_service.get_selected_language_ai_provider", _provider)
    monkeypatch.setattr("services.creative_language_service.ConfigService", _ConfigService)
    monkeypatch.setattr("services.creative_language_service.CreativeCacheService", _FakeCacheService)
    monkeypatch.setattr("api.analysis.language_analyzer.LanguageAnalyzer", _Analyzer)

    await CreativeLanguageService().analyze_language(creative=creative, store=store, force=True)

    assert analyzed_payloads[0]["html"]["thumbnailUrl"] == "https://cdn.example.com/html-thumb.png"
