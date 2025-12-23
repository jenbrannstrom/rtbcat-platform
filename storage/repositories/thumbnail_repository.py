"""Thumbnail repository for tracking thumbnail generation status.

This module provides database operations for tracking thumbnail generation
status for video and HTML creatives.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Optional

from .base import BaseRepository
from ..models import ThumbnailStatus


class ThumbnailRepository(BaseRepository[ThumbnailStatus]):
    """Repository for thumbnail generation status tracking.

    Tracks the status of thumbnail generation for video and HTML creatives,
    including success/failure status and error reasons.
    """

    def __init__(self, db_path: str | Path) -> None:
        """Initialize repository with database path.

        Args:
            db_path: Path to SQLite database file.
        """
        super().__init__(db_path)

    async def record_status(
        self,
        creative_id: str,
        status: str,
        error_reason: Optional[str] = None,
        video_url: Optional[str] = None,
    ) -> None:
        """Record the thumbnail generation status for a creative.

        Args:
            creative_id: The creative ID
            status: Status value ('success', 'failed', 'pending', 'skipped')
            error_reason: Optional error reason ('url_expired', 'no_url', 'timeout', 'network_error', 'invalid_format')
            video_url: Optional video URL that was attempted (for debugging)
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _record():
                conn.execute(
                    """
                    INSERT INTO thumbnail_status (creative_id, status, error_reason, video_url, attempted_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(creative_id) DO UPDATE SET
                        status = excluded.status,
                        error_reason = excluded.error_reason,
                        video_url = excluded.video_url,
                        attempted_at = CURRENT_TIMESTAMP
                    """,
                    (creative_id, status, error_reason, video_url),
                )
                conn.commit()

            await loop.run_in_executor(None, _record)

    async def get_status(self, creative_id: str) -> Optional[dict]:
        """Get the thumbnail status for a single creative.

        Args:
            creative_id: The creative ID

        Returns:
            Dict with status info or None if not found
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _get():
                cursor = conn.execute(
                    """
                    SELECT creative_id, status, error_reason, video_url, attempted_at
                    FROM thumbnail_status
                    WHERE creative_id = ?
                    """,
                    (creative_id,),
                )
                row = cursor.fetchone()
                if row:
                    return {
                        "creative_id": row["creative_id"],
                        "status": row["status"],
                        "error_reason": row["error_reason"],
                        "video_url": row["video_url"],
                        "attempted_at": row["attempted_at"],
                    }
                return None

            return await loop.run_in_executor(None, _get)

    async def get_statuses(
        self, creative_ids: Optional[list[str]] = None
    ) -> dict[str, dict]:
        """Get thumbnail statuses for multiple creatives.

        Args:
            creative_ids: Optional list of creative IDs. If None, returns all.

        Returns:
            Dict mapping creative_id to status info
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _get_all():
                if creative_ids:
                    placeholders = ",".join("?" * len(creative_ids))
                    cursor = conn.execute(
                        f"""
                        SELECT creative_id, status, error_reason, video_url, attempted_at
                        FROM thumbnail_status
                        WHERE creative_id IN ({placeholders})
                        """,
                        creative_ids,
                    )
                else:
                    cursor = conn.execute(
                        """
                        SELECT creative_id, status, error_reason, video_url, attempted_at
                        FROM thumbnail_status
                        """
                    )

                result = {}
                for row in cursor.fetchall():
                    result[row["creative_id"]] = {
                        "status": row["status"],
                        "error_reason": row["error_reason"],
                        "video_url": row["video_url"],
                        "attempted_at": row["attempted_at"],
                    }
                return result

            return await loop.run_in_executor(None, _get_all)

    async def get_video_creatives_needing_thumbnails(
        self, limit: int = 100, force_retry_failed: bool = False
    ) -> list[dict]:
        """Get video creatives that need thumbnail generation.

        Args:
            limit: Maximum number of creatives to return
            force_retry_failed: If True, include failed status for retry

        Returns:
            List of creative dicts with id, raw_data
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _get():
                if force_retry_failed:
                    # Retry failed ones, skip successful
                    query = """
                        SELECT c.id, c.raw_data
                        FROM creatives c
                        LEFT JOIN thumbnail_status ts ON c.id = ts.creative_id
                        WHERE c.format = 'VIDEO'
                        AND (ts.status IS NULL OR ts.status = 'failed')
                        LIMIT ?
                    """
                else:
                    # Skip any that already have a status
                    query = """
                        SELECT c.id, c.raw_data
                        FROM creatives c
                        LEFT JOIN thumbnail_status ts ON c.id = ts.creative_id
                        WHERE c.format = 'VIDEO'
                        AND ts.status IS NULL
                        LIMIT ?
                    """

                cursor = conn.execute(query, (limit,))
                results = []
                for row in cursor.fetchall():
                    raw_data = row["raw_data"]
                    if raw_data:
                        try:
                            raw_data = json.loads(raw_data)
                        except json.JSONDecodeError:
                            raw_data = {}
                    else:
                        raw_data = {}
                    results.append({
                        "id": row["id"],
                        "raw_data": raw_data,
                    })
                return results

            return await loop.run_in_executor(None, _get)

    async def get_html_creatives_pending_thumbnails(
        self, limit: int = 100, force_retry_failed: bool = False
    ) -> list[dict]:
        """Get HTML creatives that need thumbnail extraction.

        Args:
            limit: Maximum number of creatives to return.
            force_retry_failed: If True, include previously failed extractions.

        Returns:
            List of creatives with id, raw_data containing HTML snippet.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _get_pending():
                if force_retry_failed:
                    query = """
                        SELECT c.id, c.raw_data
                        FROM creatives c
                        LEFT JOIN thumbnail_status ts ON c.id = ts.creative_id
                        WHERE c.format = 'HTML'
                        AND (ts.status IS NULL OR ts.status = 'failed')
                        LIMIT ?
                    """
                else:
                    query = """
                        SELECT c.id, c.raw_data
                        FROM creatives c
                        LEFT JOIN thumbnail_status ts ON c.id = ts.creative_id
                        WHERE c.format = 'HTML'
                        AND ts.status IS NULL
                        LIMIT ?
                    """

                cursor = conn.execute(query, (limit,))
                results = []
                for row in cursor.fetchall():
                    raw_data = row["raw_data"]
                    if raw_data:
                        try:
                            raw_data = json.loads(raw_data)
                        except json.JSONDecodeError:
                            raw_data = {}
                    else:
                        raw_data = {}
                    results.append({
                        "id": row["id"],
                        "raw_data": raw_data,
                    })
                return results

            return await loop.run_in_executor(None, _get_pending)

    async def get_stats(self) -> dict:
        """Get summary statistics for thumbnail generation.

        Returns:
            Dict with counts by status and error_reason
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _get_stats():
                # Count by status
                cursor = conn.execute(
                    """
                    SELECT status, COUNT(*) as count
                    FROM thumbnail_status
                    GROUP BY status
                    """
                )
                status_counts = {row["status"]: row["count"] for row in cursor.fetchall()}

                # Count by error_reason (for failed)
                cursor = conn.execute(
                    """
                    SELECT error_reason, COUNT(*) as count
                    FROM thumbnail_status
                    WHERE status = 'failed'
                    GROUP BY error_reason
                    """
                )
                error_counts = {row["error_reason"] or "unknown": row["count"] for row in cursor.fetchall()}

                # Total video creatives
                cursor = conn.execute(
                    "SELECT COUNT(*) as count FROM creatives WHERE format = 'VIDEO'"
                )
                total_videos = cursor.fetchone()["count"]

                # Total HTML creatives
                cursor = conn.execute(
                    "SELECT COUNT(*) as count FROM creatives WHERE format = 'HTML'"
                )
                total_html = cursor.fetchone()["count"]

                return {
                    "total_videos": total_videos,
                    "total_html": total_html,
                    "status_counts": status_counts,
                    "error_counts": error_counts,
                    "success_count": status_counts.get("success", 0),
                    "failed_count": status_counts.get("failed", 0),
                    "pending_count": status_counts.get("pending", 0),
                    "skipped_count": status_counts.get("skipped", 0),
                    "unprocessed_count": (total_videos + total_html) - sum(status_counts.values()),
                }

            return await loop.run_in_executor(None, _get_stats)
