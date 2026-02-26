"""Postgres repository for thumbnail status queries (SQL only)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from storage.postgres_database import pg_query, pg_query_one, pg_execute


class ThumbnailsRepository:
    """SQL-only repository for thumbnail_status table."""

    async def get_thumbnail_status(self, creative_id: str) -> Optional[dict[str, Any]]:
        """Get thumbnail status for a single creative."""
        return await pg_query_one(
            """
            SELECT creative_id, status, error_reason, video_url, attempted_at, retry_count, next_retry_at, last_error_category
            FROM thumbnail_status
            WHERE creative_id = %s
            """,
            (creative_id,),
        )

    async def list_thumbnail_statuses(
        self, limit: int = 100, status_filter: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """List thumbnail statuses with optional filter."""
        if status_filter:
            return await pg_query(
                """
                SELECT creative_id, status, error_reason, video_url, attempted_at
                FROM thumbnail_status
                WHERE status = %s
                ORDER BY attempted_at DESC
                LIMIT %s
                """,
                (status_filter, limit),
            )
        return await pg_query(
            """
            SELECT creative_id, status, error_reason, video_url, attempted_at
            FROM thumbnail_status
            ORDER BY attempted_at DESC
            LIMIT %s
            """,
            (limit,),
        )

    async def upsert_thumbnail_status(
        self,
        creative_id: str,
        status: str,
        error_reason: Optional[str] = None,
        video_url: Optional[str] = None,
        error_category: Optional[str] = None,
        backoff_seconds: Optional[int] = None,
    ) -> None:
        """Insert or update thumbnail status for a creative."""
        if status == "failed":
            if backoff_seconds is None:
                backoff_seconds = 0
            await pg_execute(
                """
                INSERT INTO thumbnail_status (
                    creative_id, status, error_reason, video_url, attempted_at, retry_count, next_retry_at, last_error_category
                )
                VALUES (
                    %s, %s, %s, %s, CURRENT_TIMESTAMP, 1,
                    CASE WHEN %s > 0 THEN CURRENT_TIMESTAMP + (%s * INTERVAL '1 second') ELSE CURRENT_TIMESTAMP END,
                    %s
                )
                ON CONFLICT(creative_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    error_reason = EXCLUDED.error_reason,
                    video_url = EXCLUDED.video_url,
                    attempted_at = CURRENT_TIMESTAMP,
                    retry_count = thumbnail_status.retry_count + 1,
                    next_retry_at = CASE
                        WHEN %s > 0 THEN CURRENT_TIMESTAMP + (%s * INTERVAL '1 second')
                        ELSE CURRENT_TIMESTAMP
                    END,
                    last_error_category = EXCLUDED.last_error_category
                """,
                (
                    creative_id,
                    status,
                    error_reason,
                    video_url,
                    backoff_seconds,
                    backoff_seconds,
                    error_category,
                    backoff_seconds,
                    backoff_seconds,
                ),
            )
            return

        await pg_execute(
            """
            INSERT INTO thumbnail_status (
                creative_id, status, error_reason, video_url, attempted_at, retry_count, next_retry_at, last_error_category
            )
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, 0, NULL, NULL)
            ON CONFLICT(creative_id) DO UPDATE SET
                status = EXCLUDED.status,
                error_reason = EXCLUDED.error_reason,
                video_url = EXCLUDED.video_url,
                attempted_at = CURRENT_TIMESTAMP,
                retry_count = 0,
                next_retry_at = NULL,
                last_error_category = NULL
            """,
            (creative_id, status, error_reason, video_url),
        )

    async def get_video_creatives_count(self, buyer_id: Optional[str] = None) -> int:
        """Count video creatives, optionally filtered by buyer."""
        if buyer_id:
            row = await pg_query_one(
                "SELECT COUNT(*) as cnt FROM creatives WHERE format = 'VIDEO' AND buyer_id = %s",
                (buyer_id,),
            )
        else:
            row = await pg_query_one(
                "SELECT COUNT(*) as cnt FROM creatives WHERE format = 'VIDEO'"
            )
        return row["cnt"] if row else 0

    async def get_thumbnail_status_counts(
        self, buyer_id: Optional[str] = None
    ) -> dict[str, int]:
        """Get counts of thumbnails by status."""
        if buyer_id:
            rows = await pg_query(
                """
                SELECT
                    COALESCE(ts.status, 'pending') as status,
                    COUNT(*) as count
                FROM creatives c
                LEFT JOIN thumbnail_status ts ON c.id = ts.creative_id
                WHERE c.format = 'VIDEO' AND c.buyer_id = %s
                GROUP BY COALESCE(ts.status, 'pending')
                """,
                (buyer_id,),
            )
        else:
            rows = await pg_query(
                """
                SELECT
                    COALESCE(ts.status, 'pending') as status,
                    COUNT(*) as count
                FROM creatives c
                LEFT JOIN thumbnail_status ts ON c.id = ts.creative_id
                WHERE c.format = 'VIDEO'
                GROUP BY COALESCE(ts.status, 'pending')
                """
            )
        return {row["status"]: row["count"] for row in rows}

    async def get_pending_video_creatives(
        self, limit: int = 50, include_failed: bool = False
    ) -> list[dict[str, Any]]:
        """Get video creatives that need thumbnail generation."""
        if include_failed:
            return await pg_query(
                """
                SELECT c.id, c.raw_data
                FROM creatives c
                LEFT JOIN thumbnail_status ts ON c.id = ts.creative_id
                WHERE c.format = 'VIDEO'
                AND (
                    ts.status IS NULL
                    OR (
                        ts.status = 'failed'
                        AND (ts.next_retry_at IS NULL OR ts.next_retry_at <= CURRENT_TIMESTAMP)
                    )
                )
                LIMIT %s
                """,
                (limit,),
            )
        return await pg_query(
            """
            SELECT c.id, c.raw_data
            FROM creatives c
            LEFT JOIN thumbnail_status ts ON c.id = ts.creative_id
            WHERE c.format = 'VIDEO'
            AND (ts.status IS NULL OR ts.status = 'pending')
            LIMIT %s
            """,
            (limit,),
        )

    async def get_thumbnail_failure_metrics(self) -> list[dict[str, Any]]:
        """Aggregate failure categories from thumbnail_status."""
        return await pg_query(
            """
            SELECT COALESCE(last_error_category, 'other') AS category, COUNT(*) AS count
            FROM thumbnail_status
            WHERE status = 'failed'
            GROUP BY COALESCE(last_error_category, 'other')
            """
        )

    async def get_creative_by_id(self, creative_id: str) -> Optional[dict[str, Any]]:
        """Get a creative by ID."""
        return await pg_query_one(
            "SELECT id, format, raw_data FROM creatives WHERE id = %s",
            (creative_id,),
        )

    async def update_creative_raw_data(
        self, creative_id: str, raw_data: str
    ) -> None:
        """Update creative raw_data JSON."""
        await pg_execute(
            "UPDATE creatives SET raw_data = %s WHERE id = %s",
            (raw_data, creative_id),
        )
