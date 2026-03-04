"""Exception observability fallback tests for ThumbnailsService."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import pytest

from services.thumbnails_service import ThumbnailsService


def test_generate_thumbnail_ffmpeg_logs_warning_on_execution_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = ThumbnailsService()
    monkeypatch.setattr(service, "_get_ffmpeg_path", lambda: "ffmpeg")

    def _raise(*_args, **_kwargs):
        raise OSError("ffmpeg spawn failed")

    monkeypatch.setattr(subprocess, "run", _raise)

    with caplog.at_level(logging.WARNING):
        result = service._generate_thumbnail_ffmpeg(
            "https://example.com/video.mp4",
            Path("/tmp/example-thumb.jpg"),
            timeout=3,
        )

    assert result["success"] is False
    assert result["error_reason"].startswith("ffmpeg_exception:")
    assert "Thumbnail ffmpeg execution failed" in caplog.text


def test_extract_video_url_from_vast_logs_debug_and_uses_regex_fallback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    service = ThumbnailsService()
    malformed_vast = "<VAST><bad xml https://cdn.example.com/creative.mp4"

    with caplog.at_level(logging.DEBUG):
        url, parse_failed = service._extract_video_url_from_vast(malformed_vast)

    assert parse_failed is True
    assert url == "https://cdn.example.com/creative.mp4"
    assert "falling back to regex scan" in caplog.text.lower()


@pytest.mark.asyncio
async def test_get_retry_count_logs_warning_and_defaults_zero_on_bad_value(
    caplog: pytest.LogCaptureFixture,
) -> None:
    class _Repo:
        async def get_thumbnail_status(self, creative_id: str):
            del creative_id
            return {"retry_count": "not-a-number"}

    service = ThumbnailsService(repo=_Repo())
    with caplog.at_level(logging.WARNING):
        retry_count = await service._get_retry_count("creative-1")

    assert retry_count == 0
    assert "Invalid thumbnail retry_count encountered" in caplog.text
