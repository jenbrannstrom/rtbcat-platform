"""Tests for provider-specific language analyzer paths."""

from types import SimpleNamespace

import pytest

from api.analysis.language_analyzer import LanguageAnalyzer


class TestLanguageAnalyzerProviders:
    def test_detect_language_with_gemini(self, monkeypatch):
        analyzer = LanguageAnalyzer(provider="gemini", api_key="test-gemini-key")

        monkeypatch.setattr(
            "api.analysis.language_analyzer.generate_gemini_content",
            lambda *args, **kwargs: (
                '{"language":"English","language_code":"en","confidence":0.97}'
            ),
        )

        result = analyzer.detect_language("Buy now")
        assert result.success
        assert result.language == "English"
        assert result.language_code == "en"
        assert result.source == "gemini"

    def test_detect_language_with_claude(self, monkeypatch):
        analyzer = LanguageAnalyzer(provider="claude", api_key="test-claude-key")

        def fake_post_json(url, headers, payload, timeout):
            assert "anthropic.com" in url
            assert headers["x-api-key"] == "test-claude-key"
            assert "messages" in payload
            return {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            '{"language":"Spanish","language_code":"es","confidence":0.91}'
                        ),
                    }
                ]
            }

        monkeypatch.setattr(analyzer, "_post_json", fake_post_json)
        result = analyzer.detect_language("Instalar ahora")
        assert result.success
        assert result.language == "Spanish"
        assert result.language_code == "es"
        assert result.source == "claude"

    def test_detect_language_with_grok(self, monkeypatch):
        analyzer = LanguageAnalyzer(provider="grok", api_key="test-grok-key")

        def fake_post_json(url, headers, payload, timeout):
            assert "x.ai" in url
            assert headers["Authorization"] == "Bearer test-grok-key"
            assert payload["model"]
            return {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"language":"German","language_code":"de","confidence":0.88}'
                            )
                        }
                    }
                ]
            }

        monkeypatch.setattr(analyzer, "_post_json", fake_post_json)
        result = analyzer.detect_language("Jetzt installieren")
        assert result.success
        assert result.language == "German"
        assert result.language_code == "de"
        assert result.source == "grok"

    def test_claude_missing_text_returns_error(self, monkeypatch):
        analyzer = LanguageAnalyzer(provider="claude", api_key="test-claude-key")

        def fake_post_json(url, headers, payload, timeout):
            return {"content": []}

        monkeypatch.setattr(analyzer, "_post_json", fake_post_json)
        result = analyzer.detect_language("hello")
        assert not result.success
        assert "text content" in (result.error or "").lower()
        assert result.source == "claude"

    @pytest.mark.asyncio
    async def test_html_analysis_uses_rendered_evidence_ocr(self, monkeypatch):
        analyzer = LanguageAnalyzer(provider="gemini", api_key="test-gemini-key")
        raw_data = {
            "html": {
                "snippet": (
                    "<html><body><canvas id='ad'></canvas>"
                    "<script>/* text is rendered at runtime */</script></body></html>"
                )
            }
        }

        monkeypatch.setattr(
            "services.creative_evidence_service.CreativeEvidenceService.collect_evidence",
            lambda *args, **kwargs: SimpleNamespace(
                text_content="",
                ocr_texts=["ဝယ်ယူပါ"],
                screenshot_path="/tmp/rendered.png",
                video_frames=[],
            ),
        )
        monkeypatch.setattr(
            analyzer,
            "detect_language",
            lambda text: analyzer._parse_response(
                '{"language":"Burmese","language_code":"my","confidence":0.93}'
            ),
        )

        result = await analyzer.analyze_creative("creative-1", raw_data, "HTML")

        assert result.success
        assert result.language == "Burmese"
        assert result.language_code == "my"
        assert result.source == "gemini_rendered_evidence"

    def test_extract_text_reads_google_html_snippet_variant(self):
        analyzer = LanguageAnalyzer(provider="gemini", api_key="test-gemini-key")
        text = analyzer.extract_text_from_creative(
            {"html": {"htmlSnippet": "<div>मिटाना</div>"}},
            "HTML",
        )
        assert text == "मिटाना"

    def test_resolve_image_uses_html_thumbnail_hint(self):
        analyzer = LanguageAnalyzer(provider="gemini", api_key="test-gemini-key")
        image = analyzer._resolve_image_for_creative(
            "creative-1",
            {"html": {"thumbnailUrl": "https://cdn.example.com/thumb.png"}},
            "HTML",
        )
        assert image == "https://cdn.example.com/thumb.png"

    def test_resolve_image_uses_google_preview_url_hint(self):
        analyzer = LanguageAnalyzer(provider="gemini", api_key="test-gemini-key")
        image = analyzer._resolve_image_for_creative(
            "creative-1",
            {"html": {"snippet": ""}, "previewUrl": "https://storage.example.com/preview"},
            "HTML",
        )
        assert image == "https://storage.example.com/preview"

    @pytest.mark.asyncio
    async def test_html_analysis_uses_google_detected_language_metadata(self, monkeypatch):
        analyzer = LanguageAnalyzer(provider="gemini", api_key="test-gemini-key")

        monkeypatch.setattr(
            "services.creative_evidence_service.CreativeEvidenceService.collect_evidence",
            lambda *args, **kwargs: SimpleNamespace(
                text_content="",
                ocr_texts=[],
                screenshot_path=None,
                video_frames=[],
            ),
        )

        result = await analyzer.analyze_creative(
            "creative-1",
            {
                "html": {"snippet": ""},
                "creativeServingDecision": {"detectedLanguages": ["hi"]},
            },
            "HTML",
        )

        assert result.success
        assert result.language == "Hindi"
        assert result.language_code == "hi"
        assert result.source == "google_detected_language"
