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

    def test_extract_text_does_not_treat_html_advertiser_as_ad_copy(self):
        analyzer = LanguageAnalyzer(provider="gemini", api_key="test-gemini-key")

        text = analyzer.extract_text_from_creative(
            {"html": {}, "advertiserName": "Amazing Design Tools"},
            "HTML",
        )

        assert text is None

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

    def test_detect_language_uses_devanagari_script_heuristic(self):
        analyzer = LanguageAnalyzer(provider="gemini", api_key="test-gemini-key")

        result = analyzer.detect_language("AD मिटाना")

        assert result.success
        assert result.language == "Hindi"
        assert result.language_code == "hi"
        assert result.source == "script_heuristic"

    def test_detect_language_uses_vietnamese_diacritic_heuristic(self):
        analyzer = LanguageAnalyzer(provider="gemini", api_key="test-gemini-key")

        result = analyzer.detect_language("THỨ 4 SIÊU RẺ ĐỘC QUYỀN 1.000Đ")

        assert result.success
        assert result.language == "Vietnamese"
        assert result.language_code == "vi"
        assert result.source == "script_heuristic"

    def test_parse_response_uses_visible_text_script_signal(self):
        analyzer = LanguageAnalyzer(provider="gemini", api_key="test-gemini-key")

        result = analyzer._parse_response(
            (
                '{"visible_text":"AD मिटाना","language":"English",'
                '"language_code":"en","confidence":0.92}'
            )
        )

        assert result.success
        assert result.language == "Hindi"
        assert result.language_code == "hi"
        assert result.source == "gemini_script_heuristic"

    def test_parse_response_uses_visible_vietnamese_over_provider_label(self):
        analyzer = LanguageAnalyzer(provider="gemini", api_key="test-gemini-key")

        result = analyzer._parse_response(
            (
                '{"visible_text":"THỨ 4 SIÊU RẺ ĐỘC QUYỀN 1.000Đ",'
                '"language":"Chinese","language_code":"zh","confidence":0.92}'
            )
        )

        assert result.success
        assert result.language == "Vietnamese"
        assert result.language_code == "vi"
        assert result.source == "gemini_script_heuristic"

    @pytest.mark.asyncio
    async def test_html_english_vision_result_checks_rendered_script_evidence(self, monkeypatch):
        analyzer = LanguageAnalyzer(provider="gemini", api_key="test-gemini-key")

        monkeypatch.setattr(
            analyzer,
            "detect_language_from_image",
            lambda image_source: analyzer._parse_response(
                '{"language":"English","language_code":"en","confidence":0.96}'
            ),
        )
        monkeypatch.setattr(
            "services.creative_evidence_service.CreativeEvidenceService.collect_evidence",
            lambda *args, **kwargs: SimpleNamespace(
                text_content="",
                ocr_texts=["AD मिटाना"],
                screenshot_path="/tmp/rendered.png",
                video_frames=[],
            ),
        )

        result = await analyzer.analyze_creative(
            "creative-1",
            {"previewUrl": "https://storage.example.com/preview"},
            "HTML",
        )

        assert result.success
        assert result.language == "Hindi"
        assert result.language_code == "hi"
        assert result.source == "script_heuristic_rendered_evidence"

    @pytest.mark.asyncio
    async def test_native_analysis_can_use_google_detected_language_metadata(self, monkeypatch):
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
                "native": {},
                "creativeServingDecision": {"detectedLanguages": ["hi"]},
            },
            "NATIVE",
        )

        assert result.success
        assert result.language == "Hindi"
        assert result.language_code == "hi"
        assert result.source == "google_detected_language"

    @pytest.mark.asyncio
    async def test_html_analysis_does_not_use_google_metadata_as_visible_language(self, monkeypatch):
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
                "creativeServingDecision": {"detectedLanguages": ["zh"]},
            },
            "HTML",
        )

        assert not result.success
        assert result.language_code is None
        assert result.source == "gemini"

    @pytest.mark.asyncio
    async def test_video_analysis_prefers_rendered_evidence_over_metadata_text(self, monkeypatch):
        analyzer = LanguageAnalyzer(provider="gemini", api_key="test-gemini-key")

        monkeypatch.setattr(
            analyzer,
            "_detect_from_rendered_evidence",
            lambda *args, **kwargs: analyzer._script_language_result(
                "THỨ 4 SIÊU RẺ ĐỘC QUYỀN",
                source="script_heuristic_rendered_evidence",
            ),
        )
        monkeypatch.setattr(
            analyzer,
            "detect_language",
            lambda text: analyzer._parse_response(
                '{"language":"Chinese","language_code":"zh","confidence":0.9}'
            ),
        )

        result = await analyzer.analyze_creative(
            "creative-1",
            {
                "video": {
                    "vastXml": "<VAST><AdTitle>metadata title</AdTitle></VAST>",
                }
            },
            "VIDEO",
        )

        assert result.success
        assert result.language == "Vietnamese"
        assert result.language_code == "vi"
        assert result.source == "script_heuristic_rendered_evidence"
