"""Thumbnails Service - Business logic for thumbnail generation.

Handles thumbnail generation orchestration, file paths, and ffmpeg calls.
SQL operations delegated to ThumbnailsRepository.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from xml.etree import ElementTree

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
        raw_data = json.loads(creative["raw_data"]) if creative["raw_data"] else {}
        video_data = raw_data.get("video", {})
        video_url = video_data.get("videoUrl")

        if not video_url and video_data.get("vastXml"):
            video_url = self._extract_video_url_from_vast(video_data["vastXml"])

        if not video_url:
            await self.repo.upsert_thumbnail_status(
                creative_id=creative_id,
                status="failed",
                error_reason="no_url",
            )
            return ThumbnailResult(
                creative_id=creative_id,
                status="failed",
                error_reason="no_video_url",
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
                thumbnail_url=f"/thumbnails/{creative_id}.jpg",
            )
        else:
            await self.repo.upsert_thumbnail_status(
                creative_id=creative_id,
                status="failed",
                error_reason=result["error_reason"],
                video_url=video_url,
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
                "-vframes", "1",  # Extract 1 frame
                "-q:v", "2",  # High quality
                "-vf", "scale=320:-1",  # Scale to 320px width
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
                error_msg = result.stderr[:200] if result.stderr else "unknown_error"
                return {"success": False, "error_reason": error_msg}

        except subprocess.TimeoutExpired:
            return {"success": False, "error_reason": "timeout"}
        except Exception as e:
            return {"success": False, "error_reason": str(e)[:100]}

    def _extract_video_url_from_vast(self, vast_xml: str) -> Optional[str]:
        """Extract video URL from VAST XML."""
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
                        return url
        except Exception:
            pass

        # Fallback: regex for URL
        match = re.search(r'https?://[^\s<>"]+\.mp4', vast_xml)
        return match.group(0) if match else None

    def get_thumbnail_path(self, creative_id: str) -> Optional[Path]:
        """Get path to thumbnail file if it exists."""
        thumb_path = self.thumbnails_dir / f"{creative_id}.jpg"
        return thumb_path if thumb_path.exists() else None
