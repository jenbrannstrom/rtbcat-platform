"""Data migration utilities for RTBcat storage.

This module provides one-time migration functions for updating existing data
to match new schema requirements or data formats.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sqlite3
from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from storage.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)


async def migrate_canonical_sizes(store: "SQLiteStore") -> int:
    """Migrate existing creatives to populate canonical_size fields.

    Updates all creatives that have width/height but no canonical_size,
    computing the normalized size values. For VIDEO creatives, it also
    parses VAST XML to extract dimensions.

    Args:
        store: SQLiteStore instance with database connection.

    Returns:
        Number of creatives updated.
    """
    from utils.size_normalization import canonical_size as compute_canonical_size
    from utils.size_normalization import get_size_category

    def _parse_video_dimensions(raw_data: dict) -> tuple[Optional[int], Optional[int]]:
        """Extract width and height from video VAST XML."""
        video_data = raw_data.get("video")
        if not video_data:
            return None, None
        vast_xml = video_data.get("vastXml")
        if not vast_xml:
            return None, None
        match = re.search(
            r'<MediaFile[^>]*\s+width=["\'](\d+)["\'][^>]*\s+height=["\'](\d+)["\']',
            vast_xml,
        )
        if match:
            return int(match.group(1)), int(match.group(2))
        match = re.search(
            r'<MediaFile[^>]*\s+height=["\'](\d+)["\'][^>]*\s+width=["\'](\d+)["\']',
            vast_xml,
        )
        if match:
            return int(match.group(2)), int(match.group(1))
        return None, None

    async with store._connection() as conn:
        loop = asyncio.get_event_loop()

        def _get_unmigrated_with_dims():
            cursor = conn.execute(
                """
                SELECT id, width, height FROM creatives
                WHERE width IS NOT NULL AND height IS NOT NULL AND canonical_size IS NULL
                """
            )
            return cursor.fetchall()

        def _get_unmigrated_videos():
            cursor = conn.execute(
                """
                SELECT id, raw_data FROM creatives
                WHERE format = 'VIDEO' AND (width IS NULL OR height IS NULL)
                AND canonical_size IS NULL
                """
            )
            return cursor.fetchall()

        rows_with_dims = await loop.run_in_executor(None, _get_unmigrated_with_dims)
        rows_videos = await loop.run_in_executor(None, _get_unmigrated_videos)

        updates = []
        updates_with_dims = []

        for row in rows_with_dims:
            creative_id, width, height = row
            canonical = compute_canonical_size(width, height)
            category = get_size_category(canonical)
            updates.append((canonical, category, creative_id))

        for row in rows_videos:
            creative_id, raw_data_str = row
            if not raw_data_str:
                continue
            raw_data = json.loads(raw_data_str)
            width, height = _parse_video_dimensions(raw_data)
            if width is not None and height is not None:
                canonical = compute_canonical_size(width, height)
                category = get_size_category(canonical)
                updates_with_dims.append((canonical, category, width, height, creative_id))

        if not updates and not updates_with_dims:
            return 0

        if updates:
            await loop.run_in_executor(
                None,
                lambda: conn.executemany(
                    """
                    UPDATE creatives
                    SET canonical_size = ?, size_category = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    updates,
                ),
            )

        if updates_with_dims:
            await loop.run_in_executor(
                None,
                lambda: conn.executemany(
                    """
                    UPDATE creatives
                    SET canonical_size = ?, size_category = ?, width = ?, height = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    updates_with_dims,
                ),
            )

        await loop.run_in_executor(None, conn.commit)

    total = len(updates) + len(updates_with_dims)
    logger.info(f"Migrated canonical sizes for {total} creatives ({len(updates_with_dims)} from VAST XML)")
    return total


async def migrate_add_buyer_seats(store: "SQLiteStore") -> int:
    """Migrate existing creatives to populate buyer_id from account_id.

    Args:
        store: SQLiteStore instance with database connection.

    Returns:
        Number of creatives updated with buyer_id.
    """
    from storage.schema import MIGRATIONS

    async with store._connection() as conn:
        loop = asyncio.get_event_loop()

        # Run pending schema migrations
        for migration in MIGRATIONS:
            try:
                await loop.run_in_executor(None, lambda m=migration: conn.execute(m))
                await loop.run_in_executor(None, conn.commit)
            except sqlite3.OperationalError:
                pass

        def _get_creatives_needing_buyer_id():
            cursor = conn.execute(
                "SELECT id, name, account_id FROM creatives WHERE buyer_id IS NULL"
            )
            return cursor.fetchall()

        rows = await loop.run_in_executor(None, _get_creatives_needing_buyer_id)

        if not rows:
            logger.info("No creatives need buyer_id migration")
            return 0

        updates = []
        for row in rows:
            creative_id, name, account_id = row
            buyer_id = account_id
            if buyer_id:
                updates.append((buyer_id, creative_id))

        if updates:
            await loop.run_in_executor(
                None,
                lambda: conn.executemany(
                    """
                    UPDATE creatives SET buyer_id = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?
                    """,
                    updates,
                ),
            )
            await loop.run_in_executor(None, conn.commit)

        logger.info(f"Migrated buyer_id for {len(updates)} creatives")
        return len(updates)
