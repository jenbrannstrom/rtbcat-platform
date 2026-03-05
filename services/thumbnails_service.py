"""Thumbnails Service - Business logic for thumbnail generation.

Handles thumbnail generation orchestration, file paths, and ffmpeg calls.
SQL operations delegated to ThumbnailsRepository.
"""

from __future__ import annotations

import json
import logging
import math
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree

from services.url_safety import is_safe_public_http_url
from storage.postgres_repositories.thumbnails_repo import ThumbnailsRepository

logger = logging.getLogger(__name__)


@dataclass
class ThumbnailResult:
    """Result of a thumbnail generation attempt."""
    creative_id: str
    status: str  # 'success', 'failed', 'skipped'
    error_reason: Optional[str] = None
    thumbnail_url: Optional[str] = None


@dataclass
class ThumbnailStatusSummary:
    """Summary of thumbnail generation status."""
    total_videos: int
    with_thumbnails: int
    pending: int
    failed: int
    coverage_percent: float
    ffmpeg_available: bool


class ThumbnailsService:
    """Service for thumbnail generation and status management."""

    def __init__(self, repo: Optional[ThumbnailsRepository] = None):
        self.repo = repo or ThumbnailsRepository()
        self._thumbnails_dir: Optional[Path] = None
        self._base_retry_seconds = 60
        self._max_retry_seconds = 6 * 3600

    @property
    def thumbnails_dir(self) -> Path:
        """Get the thumbnails directory, creating if needed."""
        if self._thumbnails_dir is None:
            self._thumbnails_dir = Path.home() / ".catscan" / "thumbnails"
            self._thumbnails_dir.mkdir(parents=True, exist_ok=True)
        return self._thumbnails_dir

    def check_ffmpeg(self) -> bool:
        """Check if ffmpeg is available."""
        ffmpeg_path = self._get_ffmpeg_path()
        return ffmpeg_path is not None and shutil.which(ffmpeg_path) is not None

    def _get_ffmpeg_path(self) -> Optional[str]:
        """Get the ffmpeg executable path."""
        # Check common locations
        for path in ["ffmpeg", "/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg"]:
            if shutil.which(path):
                return path
        return None

    async def get_status_summary(
        self, buyer_id: Optional[str] = None
    ) -> ThumbnailStatusSummary:
        """Get summary of thumbnail generation status."""
        total_videos = await self.repo.get_video_creatives_count(buyer_id)
        status_counts = await self.repo.get_thumbnail_status_counts(buyer_id)

        with_thumbnails = status_counts.get("success", 0)
        failed = status_counts.get("failed", 0)
        pending = total_videos - with_thumbnails - failed

        coverage = (with_thumbnails / total_videos * 100) if total_videos > 0 else 0.0

        return ThumbnailStatusSummary(
            total_videos=total_videos,
            with_thumbnails=with_thumbnails,
            pending=pending,
            failed=failed,
            coverage_percent=round(coverage, 1),
            ffmpeg_available=self.check_ffmpeg(),
        )

    async def generate_thumbnail(self, creative_id: str) -> ThumbnailResult:
        """Generate thumbnail for a single video creative."""
        if not self.check_ffmpeg():
            category = "ffmpeg"
            await self.repo.upsert_thumbnail_status(
                creative_id=creative_id,
                status="failed",
                error_reason="ffmpeg_not_available",
                error_category=category,
                backoff_seconds=self._compute_backoff_seconds(1),
            )
            return ThumbnailResult(
                creative_id=creative_id,
                status="failed",
                error_reason="ffmpeg_not_available",
            )

        # Get creative data
        creative = await self.repo.get_creative_by_id(creative_id)
        if not creative:
            return ThumbnailResult(
                creative_id=creative_id,
                status="failed",
                error_reason="creative_not_found",
            )

        if creative["format"] != "VIDEO":
            return ThumbnailResult(
                creative_id=creative_id,
                status="skipped",
                error_reason="not_video",
            )

        # Extract video URL
        raw_value = creative.get("raw_data")
        if isinstance(raw_value, dict):
            raw_data = raw_value
        elif isinstance(raw_value, str):
            raw_data = json.loads(raw_value) if raw_value else {}
        else:
            raw_data = {}
        video_data = raw_data.get("video", {})
        video_url = (
            video_data.get("videoUrl")
            or video_data.get("video_url")
            or raw_data.get("videoUrl")
            or raw_data.get("video_url")
        )
        vast_xml = (
            video_data.get("vastXml")
            or video_data.get("videoVastXml")
            or video_data.get("vast_xml")
            or video_data.get("video_vast_xml")
            or raw_data.get("vastXml")
            or raw_data.get("videoVastXml")
            or raw_data.get("vast_xml")
            or raw_data.get("video_vast_xml")
        )

        if not video_url and vast_xml:
            video_url, parse_failed = self._extract_video_url_from_vast(vast_xml)
        else:
            parse_failed = False

        if not video_url:
            error_reason = "parse_vast_failed" if parse_failed else "no_url"
            category = self._classify_error_category(error_reason)
            await self.repo.upsert_thumbnail_status(
                creative_id=creative_id,
                status="failed",
                error_reason=error_reason,
                error_category=category,
                backoff_seconds=self._compute_backoff_seconds(1),
            )
            return ThumbnailResult(
                creative_id=creative_id,
                status="failed",
                error_reason="no_url",
            )

        if not is_safe_public_http_url(video_url):
            logger.warning("Blocked thumbnail generation for unsafe video URL", extra={"creative_id": creative_id})
            await self.repo.upsert_thumbnail_status(
                creative_id=creative_id,
                status="failed",
                error_reason="unsafe_video_url",
                error_category="other",
                backoff_seconds=self._compute_backoff_seconds(1),
            )
            return ThumbnailResult(
                creative_id=creative_id,
                status="failed",
                error_reason="unsafe_video_url",
            )

        # Generate thumbnail
        thumb_path = self.thumbnails_dir / f"{creative_id}.jpg"
        result = self._generate_thumbnail_ffmpeg(video_url, thumb_path)

        if result["success"]:
            # Update creative raw_data with local thumbnail path
            video_data["localThumbnailPath"] = str(thumb_path)
            raw_data["video"] = video_data
            await self.repo.update_creative_raw_data(creative_id, json.dumps(raw_data))

            await self.repo.upsert_thumbnail_status(
                creative_id=creative_id,
                status="success",
                video_url=video_url,
            )

            return ThumbnailResult(
                creative_id=creative_id,
                status="success",
                thumbnail_url=f"/api/thumbnails/{creative_id}.jpg",
            )
        else:
            error_reason = result["error_reason"]
            category = self._classify_error_category(error_reason)
            retries = await self._get_retry_count(creative_id)
            await self.repo.upsert_thumbnail_status(
                creative_id=creative_id,
                status="failed",
                error_reason=error_reason,
                video_url=video_url,
                error_category=category,
                backoff_seconds=self._compute_backoff_seconds(retries + 1),
            )

            return ThumbnailResult(
                creative_id=creative_id,
                status="failed",
                error_reason=result["error_reason"],
            )

    async def generate_batch(
        self, limit: int = 50, force: bool = False
    ) -> list[ThumbnailResult]:
        """Generate thumbnails for multiple video creatives."""
        if not self.check_ffmpeg():
            return []

        creatives = await self.repo.get_pending_video_creatives(
            limit=limit, include_failed=force
        )

        results = []
        for creative in creatives:
            result = await self.generate_thumbnail(creative["id"])
            results.append(result)

        return results

    def _generate_thumbnail_ffmpeg(
        self, video_url: str, output_path: Path, timeout: int = 15
    ) -> dict:
        """Generate thumbnail from video URL using ffmpeg."""
        ffmpeg_path = self._get_ffmpeg_path()
        if not ffmpeg_path:
            return {"success": False, "error_reason": "ffmpeg_not_found"}

        try:
            cmd = [
                ffmpeg_path,
                "-y",  # Overwrite output
                "-i", video_url,
                "-ss", "00:00:01",  # Seek to 1 second
                "-frames:v", "1",  # Extract 1 frame
                "-q:v", "2",  # High quality
                "-vf", "scale=320:-1",  # Scale to 320px width
                "-update", "1",  # Required by ffmpeg 7.x for single-image output
                str(output_path),
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode == 0 and output_path.exists():
                return {"success": True}
            else:
                stderr = result.stderr or ""
                return {"success": False, "error_reason": self._classify_ffmpeg_error(stderr)}

        except subprocess.TimeoutExpired:
            return {"success": False, "error_reason": "timeout"}
        except Exception as e:
            logger.warning(
                "Thumbnail ffmpeg execution failed; returning classified ffmpeg_exception",
                extra={"output_path": str(output_path)},
                exc_info=True,
            )
            return {"success": False, "error_reason": f"ffmpeg_exception:{str(e)[:80]}"}

    def _extract_video_url_from_vast(self, vast_xml: str) -> tuple[Optional[str], bool]:
        """Extract video URL from VAST XML."""
        parse_failed = False
        try:
            root = ElementTree.fromstring(vast_xml)
            # Try common VAST paths
            for path in [
                ".//MediaFile",
                ".//MediaFiles/MediaFile",
                ".//Creative/Linear/MediaFiles/MediaFile",
            ]:
                media_files = root.findall(path)
                for mf in media_files:
                    url = mf.text.strip() if mf.text else None
                    if url and url.startswith("http"):
                        return url, False
        except Exception:
            logger.debug(
                "Failed to parse VAST XML for media extraction; falling back to regex scan",
                exc_info=True,
            )
            parse_failed = True

        # Fallback: regex for URL
        match = re.search(r'https?://[^\s<>"]+\.mp4', vast_xml)
        return (match.group(0), parse_failed) if match else (None, parse_failed)

    def get_thumbnail_path(self, creative_id: str) -> Optional[Path]:
        """Get path to thumbnail file if it exists."""
        thumb_path = self.thumbnails_dir / f"{creative_id}.jpg"
        return thumb_path if thumb_path.exists() else None

    async def get_failure_metrics(self) -> dict[str, int]:
        """Get standardized failure category metrics."""
        rows = await self.repo.get_thumbnail_failure_metrics()
        metrics = {"no_url": 0, "timeout": 0, "ffmpeg": 0, "parse": 0, "other": 0}
        for row in rows:
            category = str(row.get("category") or "other")
            count = int(row.get("count") or 0)
            if category in metrics:
                metrics[category] += count
            else:
                metrics["other"] += count
        return metrics

    async def _get_retry_count(self, creative_id: str) -> int:
        current = await self.repo.get_thumbnail_status(creative_id)
        if not current:
            return 0
        value = current.get("retry_count")
        try:
            return int(value or 0)
        except Exception:
            logger.warning(
                "Invalid thumbnail retry_count encountered; defaulting to zero",
                extra={"creative_id": creative_id, "retry_count": value},
                exc_info=True,
            )
            return 0

    def _compute_backoff_seconds(self, retry_count: int) -> int:
        # Exponential backoff with cap: 60s, 120s, 240s, ...
        power = max(0, retry_count - 1)
        seconds = int(self._base_retry_seconds * math.pow(2, power))
        return min(seconds, self._max_retry_seconds)

    @staticmethod
    def _classify_ffmpeg_error(stderr: str) -> str:
        message = (stderr or "").lower()
        if "timed out" in message:
            return "timeout"
        if "invalid data found" in message or "could not find codec" in message:
            return "parse_media_error"
        if "connection" in message or "http error" in message:
            return "network_error"
        if "ffmpeg" in message and "not found" in message:
            return "ffmpeg_not_found"
        return "ffmpeg_failure"

    @staticmethod
    def _classify_error_category(error_reason: Optional[str]) -> str:
        value = (error_reason or "").lower()
        if "no_url" in value:
            return "no_url"
        if "timeout" in value:
            return "timeout"
        if "parse" in value or "xml" in value or "json" in value:
            return "parse"
        if "ffmpeg" in value:
            return "ffmpeg"
        return "other"
