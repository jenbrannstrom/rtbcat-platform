"""Tests for the CreativeEvidenceService."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from services.creative_evidence_service import CreativeEvidenceService, EvidenceResult


@pytest.fixture
def service():
    return CreativeEvidenceService()


class TestCollectHtmlEvidence:
    def test_extracts_text_from_snippet(self, service):
        raw_data = {
            "html": {"snippet": "<div>Buy shoes now for <b>$49.99</b></div>"},
            "advertiserName": "ShoeStore",
        }
        result = service.collect_evidence("c1", raw_data, "HTML")
        assert "Buy shoes now" in result.text_content
        assert "$49.99" in result.text_content
        assert "ShoeStore" in result.text_content
        assert "$" in result.currencies or "$49.99" in result.text_content

    def test_extracts_image_urls(self, service):
        raw_data = {
            "html": {
                "snippet": '<img src="https://example.com/banner.jpg" /><img src="data:image/png" />'
            }
        }
        result = service.collect_evidence("c2", raw_data, "HTML")
        assert "https://example.com/banner.jpg" in result.image_urls
        # data: URLs should be filtered out
        assert len(result.image_urls) == 1

    def test_empty_snippet(self, service):
        raw_data = {"html": {"snippet": ""}}
        result = service.collect_evidence("c3", raw_data, "HTML")
        assert result.text_content == ""


class TestCollectVideoEvidence:
    def test_extracts_text_from_vast(self, service):
        vast_xml = """
        <VAST version="3.0">
          <Ad>
            <InLine>
              <AdTitle>Summer Sale</AdTitle>
              <Description>Get 50% off</Description>
              <Creatives>
                <Creative>
                  <Linear>
                    <MediaFiles>
                      <MediaFile>https://example.com/video.mp4</MediaFile>
                    </MediaFiles>
                  </Linear>
                </Creative>
              </Creatives>
            </InLine>
          </Ad>
        </VAST>
        """
        raw_data = {"video": {"vastXml": vast_xml}}
        result = service.collect_evidence("c4", raw_data, "VIDEO")
        assert "Summer Sale" in result.text_content
        assert "Get 50% off" in result.text_content


class TestCollectNativeEvidence:
    def test_extracts_all_fields(self, service):
        raw_data = {
            "native": {
                "headline": "Amazing Deals",
                "body": "Shop the best prices",
                "callToAction": "Buy Now",
                "advertiserName": "DealStore",
                "image": {"url": "https://example.com/img.jpg"},
                "logo": {"url": "https://example.com/logo.png"},
            }
        }
        result = service.collect_evidence("c5", raw_data, "NATIVE")
        assert "Amazing Deals" in result.text_content
        assert "Shop the best prices" in result.text_content
        assert "Buy Now" in result.text_content
        assert "DealStore" in result.text_content
        assert "https://example.com/img.jpg" in result.image_urls
        assert "https://example.com/logo.png" in result.image_urls

    def test_cta_detection(self, service):
        raw_data = {
            "native": {
                "headline": "Buy Now and Save",
                "body": "Shop now for the best deals",
            }
        }
        result = service.collect_evidence("c6", raw_data, "NATIVE")
        assert "buy now" in result.cta_phrases or "shop now" in result.cta_phrases


class TestCollectImageEvidence:
    def test_extracts_image_url(self, service):
        raw_data = {
            "image": {"url": "https://example.com/banner.png"},
            "advertiserName": "TestBrand",
        }
        result = service.collect_evidence("c7", raw_data, "IMAGE")
        assert "https://example.com/banner.png" in result.image_urls
        assert result.text_content == "TestBrand"


class TestCurrencyDetection:
    def test_detects_dollar_sign(self, service):
        raw_data = {"html": {"snippet": "<div>Only $9.99</div>"}}
        result = service.collect_evidence("c8", raw_data, "HTML")
        assert "$" in result.currencies

    def test_detects_currency_code(self, service):
        raw_data = {"html": {"snippet": "<div>Price: 100 AED</div>"}}
        result = service.collect_evidence("c9", raw_data, "HTML")
        assert "AED" in result.currencies

    def test_detects_euro_symbol(self, service):
        raw_data = {"html": {"snippet": "<div>Nur 19,99€</div>"}}
        result = service.collect_evidence("c10", raw_data, "HTML")
        assert "€" in result.currencies


class TestVideoFrameExtraction:
    @patch("shutil.which", return_value=None)
    def test_no_ffmpeg_returns_empty(self, mock_which, service):
        frames = service._extract_video_frames("c11", "https://example.com/video.mp4")
        assert frames == []

    @patch("services.creative_evidence_service.is_safe_public_http_url", return_value=True)
    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    @patch("subprocess.run")
    def test_with_ffmpeg_extracts_frames(
        self,
        mock_run,
        mock_which,
        mock_is_safe_url,
        service,
        tmp_path,
    ):
        service._evidence_dir = tmp_path

        # Mock ffprobe returning no duration (fallback to single frame)
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")

        frames = service._extract_video_frames("c12", "https://example.com/video.mp4")
        # Should attempt extraction even with ffprobe failure
        assert mock_is_safe_url.called
        assert mock_run.called


def test_extract_video_url_from_vast_logs_debug_and_uses_regex_fallback(service, caplog):
    malformed_vast = "<VAST><bad xml https://cdn.example.com/video.mp4"
    with caplog.at_level(logging.DEBUG):
        url = service._extract_video_url_from_vast(malformed_vast)
    assert url == "https://cdn.example.com/video.mp4"
    assert "falling back to regex" in caplog.text.lower()
