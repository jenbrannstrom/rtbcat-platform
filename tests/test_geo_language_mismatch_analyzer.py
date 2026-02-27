"""Tests for the GeminiGeoLinguisticAnalyzer."""

import json
from unittest.mock import MagicMock, patch

import pytest

from api.analysis.geo_language_mismatch_analyzer import (
    GeminiGeoLinguisticAnalyzer,
    GeoLinguisticAnalysisResult,
)


@pytest.fixture
def analyzer():
    """Create analyzer with a fake API key."""
    return GeminiGeoLinguisticAnalyzer(api_key="test-key")


class TestIsConfigured:
    def test_configured_with_key(self, analyzer):
        assert analyzer.is_configured is True

    def test_not_configured_without_key(self):
        with patch("api.analysis.geo_language_mismatch_analyzer.get_secrets_manager") as mock_sm:
            mock_sm.return_value.get.return_value = None
            a = GeminiGeoLinguisticAnalyzer(api_key=None)
            assert a.is_configured is False


class TestBuildPrompt:
    def test_prompt_includes_countries(self, analyzer):
        prompt = analyzer._build_prompt(
            serving_countries=["IN", "US"],
            text_content="Buy now!",
            ocr_texts=[],
            metadata={"format": "HTML"},
        )
        assert "IN, US" in prompt
        assert "Buy now!" in prompt

    def test_prompt_includes_ocr(self, analyzer):
        prompt = analyzer._build_prompt(
            serving_countries=["DE"],
            text_content="",
            ocr_texts=["Jetzt kaufen"],
            metadata={},
        )
        assert "Jetzt kaufen" in prompt

    def test_prompt_truncates_long_text(self, analyzer):
        long_text = "A" * 3000
        prompt = analyzer._build_prompt(
            serving_countries=["US"],
            text_content=long_text,
            ocr_texts=[],
            metadata={},
        )
        assert "..." in prompt
        # Text content in prompt should be capped at ~2000 chars
        assert len(prompt) < 4000


class TestParseResponse:
    def test_valid_json(self, analyzer):
        response = json.dumps({
            "primary_languages": ["German"],
            "secondary_languages": [],
            "detected_currencies": ["EUR"],
            "findings": [
                {
                    "category": "language_mismatch",
                    "severity": "high",
                    "description": "German text in India traffic",
                    "evidence": "Text contains 'Jetzt kaufen'",
                }
            ],
            "risk_score": 0.85,
            "decision": "mismatch",
            "confidence": 0.92,
        })
        result = analyzer._parse_response(response, ["IN"])
        assert result.decision == "mismatch"
        assert result.risk_score == 0.85
        assert result.confidence == 0.92
        assert len(result.findings) == 1
        assert result.findings[0].category == "language_mismatch"
        assert result.primary_languages == ["German"]

    def test_json_in_markdown_fences(self, analyzer):
        response = '```json\n{"primary_languages": ["English"], "risk_score": 0.1, "decision": "match", "confidence": 0.95}\n```'
        result = analyzer._parse_response(response, ["US"])
        assert result.decision == "match"
        assert result.primary_languages == ["English"]

    def test_malformed_json(self, analyzer):
        result = analyzer._parse_response("not json at all", ["US"])
        assert result.decision == "needs_review"
        assert result.error is not None

    def test_low_confidence_overrides_mismatch(self, analyzer):
        response = json.dumps({
            "primary_languages": ["Arabic"],
            "risk_score": 0.7,
            "decision": "mismatch",
            "confidence": 0.4,  # Below 0.6 threshold
        })
        result = analyzer._parse_response(response, ["AE"])
        assert result.decision == "needs_review"  # Overridden due to low confidence

    def test_risk_score_clamped(self, analyzer):
        response = json.dumps({
            "primary_languages": [],
            "risk_score": 1.5,
            "decision": "match",
            "confidence": 2.0,
        })
        result = analyzer._parse_response(response, ["US"])
        assert result.risk_score == 1.0
        assert result.confidence == 1.0


class TestAnalyze:
    def test_not_configured(self):
        with patch("api.analysis.geo_language_mismatch_analyzer.get_secrets_manager") as mock_sm:
            mock_sm.return_value.get.return_value = None
            a = GeminiGeoLinguisticAnalyzer(api_key=None)
            result = a.analyze(
                serving_countries=["IN"],
                text_content="test",
            )
            assert result.error == "Gemini API not configured"
            assert result.decision == "needs_review"

    def test_no_content(self, analyzer):
        result = analyzer.analyze(
            serving_countries=["US"],
            text_content="",
            ocr_texts=[],
            image_paths=None,
        )
        assert result.error == "No content to analyze"

    @patch("google.generativeai.GenerativeModel")
    @patch("google.generativeai.configure")
    def test_successful_analysis(self, mock_configure, mock_model_cls, analyzer):
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "primary_languages": ["English"],
            "secondary_languages": [],
            "detected_currencies": ["$"],
            "findings": [],
            "risk_score": 0.1,
            "decision": "match",
            "confidence": 0.95,
        })
        mock_model.generate_content.return_value = mock_response
        analyzer._model = mock_model

        result = analyzer.analyze(
            serving_countries=["US"],
            text_content="Buy shoes now, only $49.99",
        )
        assert result.success
        assert result.decision == "match"
        assert result.risk_score == 0.1
