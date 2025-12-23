"""Creative repository for CRUD operations on creatives.

This module provides database operations for creative records including
save, get, list, delete, and migration utilities.
"""

from __future__ import annotations

import asyncio
import json
import re
import sqlite3
from pathlib import Path
from typing import Optional, Any

from .base import BaseRepository
from ..models import Creative
from utils.size_normalization import canonical_size as compute_canonical_size
from utils.size_normalization import get_size_category


class CreativeRepository(BaseRepository[Creative]):
    """Repository for creative database operations."""

    def __init__(self, db_path: str | Path) -> None:
        """Initialize repository with database path.

        Args:
            db_path: Path to SQLite database file.
        """
        super().__init__(db_path)

    async def save(self, creative: Creative) -> None:
        """Save or update a creative record.

        Args:
            creative: The Creative to save.
        """
        # Compute canonical size if not already set
        canonical = creative.canonical_size
        category = creative.size_category
        if canonical is None and creative.width is not None and creative.height is not None:
            canonical = compute_canonical_size(creative.width, creative.height)
            category = get_size_category(canonical)

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    """
                    INSERT OR REPLACE INTO creatives (
                        id, name, format, account_id, buyer_id, approval_status,
                        width, height, canonical_size, size_category,
                        final_url, display_url,
                        utm_source, utm_medium, utm_campaign,
                        utm_content, utm_term, advertiser_name,
                        campaign_id, cluster_id, raw_data,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (
                        creative.id,
                        creative.name,
                        creative.format,
                        creative.account_id,
                        creative.buyer_id,
                        creative.approval_status,
                        creative.width,
                        creative.height,
                        canonical,
                        category,
                        creative.final_url,
                        creative.display_url,
                        creative.utm_source,
                        creative.utm_medium,
                        creative.utm_campaign,
                        creative.utm_content,
                        creative.utm_term,
                        creative.advertiser_name,
                        creative.campaign_id,
                        creative.cluster_id,
                        json.dumps(creative.raw_data),
                    ),
                ),
            )
            await loop.run_in_executor(None, conn.commit)

    async def save_batch(self, creatives: list[Creative]) -> int:
        """Batch save multiple creatives.

        Args:
            creatives: List of Creative objects to save.

        Returns:
            Number of creatives saved.
        """
        def _compute_size_fields(c: Creative) -> tuple:
            """Compute canonical size fields for a creative."""
            canonical = c.canonical_size
            category = c.size_category
            if canonical is None and c.width is not None and c.height is not None:
                canonical = compute_canonical_size(c.width, c.height)
                category = get_size_category(canonical)
            return canonical, category

        data = [
            (
                c.id, c.name, c.format, c.account_id, c.buyer_id, c.approval_status,
                c.width, c.height,
                *_compute_size_fields(c),
                c.final_url, c.display_url,
                c.utm_source, c.utm_medium, c.utm_campaign,
                c.utm_content, c.utm_term, c.advertiser_name,
                c.campaign_id, c.cluster_id, json.dumps(c.raw_data),
            )
            for c in creatives
        ]

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: conn.executemany(
                    """
                    INSERT OR REPLACE INTO creatives (
                        id, name, format, account_id, buyer_id, approval_status,
                        width, height, canonical_size, size_category,
                        final_url, display_url,
                        utm_source, utm_medium, utm_campaign,
                        utm_content, utm_term, advertiser_name,
                        campaign_id, cluster_id, raw_data,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    data,
                ),
            )
            await loop.run_in_executor(None, conn.commit)

        return len(creatives)

    async def get(self, creative_id: str) -> Optional[Creative]:
        """Get a creative by ID.

        Args:
            creative_id: The creative ID.

        Returns:
            Creative object or None if not found.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    """
                    SELECT c.*, bs.display_name as seat_name
                    FROM creatives c
                    LEFT JOIN buyer_seats bs ON c.account_id = bs.buyer_id
                    WHERE c.id = ?
                    """,
                    (creative_id,),
                )
                return cursor.fetchone()

            row = await loop.run_in_executor(None, _query)

            if row:
                return self._row_to_creative(row)
            return None

    async def list(
        self,
        buyer_id: Optional[str] = None,
        campaign_id: Optional[str] = None,
        cluster_id: Optional[str] = None,
        format: Optional[str] = None,
        canonical_size: Optional[str] = None,
        size_category: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Creative]:
        """List creatives with optional filtering.

        Args:
            buyer_id: Filter by buyer seat ID.
            campaign_id: Filter by campaign ID.
            cluster_id: Filter by cluster ID.
            format: Filter by creative format.
            canonical_size: Filter by canonical size.
            size_category: Filter by size category.
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of Creative objects.
        """
        conditions = []
        params: list[Any] = []

        if buyer_id:
            conditions.append("c.account_id = ?")
            params.append(buyer_id)
        if campaign_id:
            conditions.append("c.campaign_id = ?")
            params.append(campaign_id)
        if cluster_id:
            conditions.append("c.cluster_id = ?")
            params.append(cluster_id)
        if format:
            conditions.append("c.format = ?")
            params.append(format)
        if canonical_size:
            conditions.append("c.canonical_size = ?")
            params.append(canonical_size)
        if size_category:
            conditions.append("c.size_category = ?")
            params.append(size_category)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.extend([limit, offset])

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    f"""
                    SELECT c.*, bs.display_name as seat_name
                    FROM creatives c
                    LEFT JOIN buyer_seats bs ON c.account_id = bs.buyer_id
                    WHERE {where_clause}
                    ORDER BY c.updated_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    params,
                )
                return cursor.fetchall()

            rows = await loop.run_in_executor(None, _query)

        return [self._row_to_creative(row) for row in rows]

    async def delete(self, creative_id: str) -> bool:
        """Delete a creative by ID.

        Args:
            creative_id: The creative ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _delete():
                cursor = conn.execute(
                    "DELETE FROM creatives WHERE id = ?",
                    (creative_id,),
                )
                conn.commit()
                return cursor.rowcount > 0

            return await loop.run_in_executor(None, _delete)

    async def update_cluster(
        self,
        creative_id: str,
        cluster_id: Optional[str],
    ) -> bool:
        """Update the cluster assignment for a creative.

        Args:
            creative_id: The creative ID.
            cluster_id: The new cluster ID (or None to unassign).

        Returns:
            True if updated, False if creative not found.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _update():
                cursor = conn.execute(
                    """
                    UPDATE creatives
                    SET cluster_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (cluster_id, creative_id),
                )
                conn.commit()
                return cursor.rowcount > 0

            return await loop.run_in_executor(None, _update)

    async def update_campaign(
        self,
        creative_id: str,
        campaign_id: Optional[str],
    ) -> bool:
        """Update the campaign assignment for a creative.

        Args:
            creative_id: The creative ID.
            campaign_id: The new campaign ID (or None to unassign).

        Returns:
            True if updated, False if creative not found.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _update():
                cursor = conn.execute(
                    """
                    UPDATE creatives
                    SET campaign_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (campaign_id, creative_id),
                )
                conn.commit()
                return cursor.rowcount > 0

            return await loop.run_in_executor(None, _update)

    async def get_available_sizes(self) -> list[str]:
        """Get all unique canonical sizes in the database.

        Returns:
            List of canonical size strings.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    """
                    SELECT DISTINCT canonical_size
                    FROM creatives
                    WHERE canonical_size IS NOT NULL
                    ORDER BY canonical_size
                    """
                )
                return [row["canonical_size"] for row in cursor.fetchall()]

            return await loop.run_in_executor(None, _query)

    async def get_unclustered_ids(self, buyer_id: Optional[str] = None) -> list[str]:
        """Get IDs of creatives not assigned to any campaign.

        Args:
            buyer_id: Optional filter by buyer ID.

        Returns:
            List of creative IDs.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _get_unclustered():
                if buyer_id:
                    cursor = conn.execute(
                        """
                        SELECT c.id FROM creatives c
                        LEFT JOIN creative_campaigns cc ON c.id = cc.creative_id
                        WHERE cc.creative_id IS NULL AND c.buyer_id = ?
                        """,
                        (buyer_id,)
                    )
                else:
                    cursor = conn.execute(
                        """
                        SELECT c.id FROM creatives c
                        LEFT JOIN creative_campaigns cc ON c.id = cc.creative_id
                        WHERE cc.creative_id IS NULL
                        """
                    )
                return [row['id'] for row in cursor.fetchall()]

            return await loop.run_in_executor(None, _get_unclustered)

    def _parse_video_dimensions(self, raw_data: dict) -> tuple[Optional[int], Optional[int]]:
        """Extract width and height from video VAST XML.

        Args:
            raw_data: The raw_data dict containing video information.

        Returns:
            Tuple of (width, height) or (None, None) if not found.
        """
        video_data = raw_data.get("video")
        if not video_data:
            return None, None

        vast_xml = video_data.get("vastXml")
        if not vast_xml:
            return None, None

        # Parse MediaFile tag: <MediaFile width="720" height="1280" ...>
        match = re.search(
            r'<MediaFile[^>]*\s+width=["\'](\d+)["\'][^>]*\s+height=["\'](\d+)["\']',
            vast_xml,
        )
        if match:
            return int(match.group(1)), int(match.group(2))

        # Try alternate attribute order: height before width
        match = re.search(
            r'<MediaFile[^>]*\s+height=["\'](\d+)["\'][^>]*\s+width=["\'](\d+)["\']',
            vast_xml,
        )
        if match:
            return int(match.group(2)), int(match.group(1))

        return None, None

    def _row_to_creative(self, row: sqlite3.Row) -> Creative:
        """Convert a database row to a Creative object."""
        row_dict = dict(row)

        # Parse raw_data first - needed for video dimension extraction
        raw_data = json.loads(row_dict["raw_data"]) if row_dict.get("raw_data") else {}

        # Get dimensions from database
        width = row_dict.get("width")
        height = row_dict.get("height")

        # For VIDEO format, try to extract dimensions from VAST XML if not set
        creative_format = row_dict.get("format")
        if creative_format == "VIDEO" and (width is None or height is None):
            video_width, video_height = self._parse_video_dimensions(raw_data)
            if video_width is not None and video_height is not None:
                width = video_width
                height = video_height

        # Compute canonical size on-the-fly if not stored (migration support)
        canonical = row_dict.get("canonical_size")
        category = row_dict.get("size_category")
        if canonical is None and width is not None and height is not None:
            canonical = compute_canonical_size(width, height)
            category = get_size_category(canonical)

        return Creative(
            id=row_dict["id"],
            name=row_dict["name"],
            format=row_dict["format"],
            account_id=row_dict.get("account_id"),
            buyer_id=row_dict.get("buyer_id"),
            approval_status=row_dict.get("approval_status"),
            width=width,
            height=height,
            canonical_size=canonical,
            size_category=category,
            final_url=row_dict.get("final_url"),
            display_url=row_dict.get("display_url"),
            utm_source=row_dict.get("utm_source"),
            utm_medium=row_dict.get("utm_medium"),
            utm_campaign=row_dict.get("utm_campaign"),
            utm_content=row_dict.get("utm_content"),
            utm_term=row_dict.get("utm_term"),
            advertiser_name=row_dict.get("advertiser_name"),
            campaign_id=row_dict.get("campaign_id"),
            cluster_id=row_dict.get("cluster_id"),
            seat_name=row_dict.get("seat_name"),
            raw_data=raw_data,
            created_at=row_dict.get("created_at"),
            updated_at=row_dict.get("updated_at"),
        )
