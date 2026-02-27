"""Integration tests for the geo-linguistic API endpoints."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.routers.creative_geo_linguistic import (
    GeoLinguisticReportResponse,
    router,
)


class TestResponseModel:
    """Verify response model can be instantiated with typical data."""

    def test_minimal_response(self):
        resp = GeoLinguisticReportResponse(
            status="completed",
            creative_id="test-123",
        )
        assert resp.status == "completed"
        assert resp.creative_id == "test-123"
        assert resp.decision == "unknown"
        assert resp.risk_score == 0.0

    def test_full_response(self):
        resp = GeoLinguisticReportResponse(
            status="completed",
            run_id="run-abc",
            creative_id="test-123",
            decision="mismatch",
            risk_score=0.85,
            confidence=0.92,
            primary_languages=["German"],
            secondary_languages=["English"],
            detected_currencies=["EUR"],
            findings=[
                {
                    "category": "language_mismatch",
                    "severity": "high",
                    "description": "German text served in India",
                    "evidence": "Contains 'Jetzt kaufen'",
                }
            ],
            serving_countries=["IN"],
            evidence=[],
            error_message=None,
        )
        assert resp.decision == "mismatch"
        assert len(resp.findings) == 1
        assert resp.findings[0].category == "language_mismatch"

    def test_failed_response(self):
        resp = GeoLinguisticReportResponse(
            status="failed",
            creative_id="test-456",
            error_message="Gemini API not configured",
        )
        assert resp.status == "failed"
        assert resp.error_message == "Gemini API not configured"

    def test_response_with_evidence_summary(self):
        resp = GeoLinguisticReportResponse(
            status="completed",
            creative_id="test-789",
            evidence_summary={
                "text_length": 150,
                "image_count": 2,
                "ocr_texts_count": 1,
                "video_frames_count": 0,
                "has_screenshot": True,
                "currencies_detected": ["$"],
                "cta_phrases": ["buy now"],
            },
        )
        assert resp.evidence_summary is not None
        assert resp.evidence_summary.text_length == 150
        assert resp.evidence_summary.has_screenshot is True


class TestRouterRegistered:
    """Verify the router has the expected endpoints."""

    def test_has_analyze_endpoint(self):
        routes = [r.path for r in router.routes]
        assert "/creatives/{creative_id}/analyze-geo-linguistic" in routes

    def test_has_report_endpoint(self):
        routes = [r.path for r in router.routes]
        assert "/creatives/{creative_id}/geo-linguistic-report" in routes

    def test_analyze_is_post(self):
        for r in router.routes:
            if r.path == "/creatives/{creative_id}/analyze-geo-linguistic":
                assert "POST" in r.methods
                break

    def test_report_is_get(self):
        for r in router.routes:
            if r.path == "/creatives/{creative_id}/geo-linguistic-report":
                assert "GET" in r.methods
                break
