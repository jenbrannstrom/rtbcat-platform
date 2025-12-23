"""Traffic repository for RTB traffic data operations.

This module provides database operations for RTB traffic data including
storing bid request size data and retrieving traffic analytics.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from pathlib import Path
from typing import Optional, Any

from .base import BaseRepository

logger = logging.getLogger(__name__)


class TrafficRepository(BaseRepository[dict]):
    """Repository for RTB traffic data.

    Manages storage and retrieval of bid request traffic data
    for size analysis and optimization.
    """

    def __init__(self, db_path: str | Path) -> None:
        """Initialize repository with database path.

        Args:
            db_path: Path to SQLite database file.
        """
        super().__init__(db_path)

    async def store_traffic_data(
        self,
        traffic_data: list[dict],
    ) -> int:
        """Store RTB traffic data records.

        Uses INSERT OR REPLACE to handle duplicates (same buyer_id,
        canonical_size, raw_size, date combination).

        Args:
            traffic_data: List of traffic records with keys:
                - canonical_size: Normalized size category
                - raw_size: Original requested size
                - request_count: Number of requests
                - date: Date string (YYYY-MM-DD)
                - buyer_id: Optional buyer seat ID

        Returns:
            Number of records stored.

        Example:
            >>> traffic = [
            ...     {"canonical_size": "300x250 (Medium Rectangle)",
            ...      "raw_size": "300x250", "request_count": 45000,
            ...      "date": "2025-11-29", "buyer_id": "456"}
            ... ]
            >>> count = await repo.store_traffic_data(traffic)
        """
        if not traffic_data:
            return 0

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _insert_traffic():
                count = 0
                for record in traffic_data:
                    try:
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO rtb_traffic
                            (buyer_id, canonical_size, raw_size, request_count, date)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                record.get("buyer_id"),
                                record["canonical_size"],
                                record["raw_size"],
                                record["request_count"],
                                record["date"],
                            ),
                        )
                        count += 1
                    except (KeyError, sqlite3.Error) as e:
                        logger.warning(f"Failed to insert traffic record: {e}")
                conn.commit()
                return count

            return await loop.run_in_executor(None, _insert_traffic)

    async def get_traffic_data(
        self,
        buyer_id: Optional[str] = None,
        days: int = 7,
    ) -> list[dict]:
        """Get RTB traffic data for analysis.

        Args:
            buyer_id: Optional filter by buyer seat ID.
            days: Number of days of data to retrieve.

        Returns:
            List of traffic records as dictionaries with aggregated
            request counts by canonical_size.

        Example:
            >>> traffic = await repo.get_traffic_data(days=7)
            >>> for record in traffic:
            ...     print(f"{record['canonical_size']}: {record['request_count']}")
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _get_traffic():
                query = """
                    SELECT
                        canonical_size,
                        raw_size,
                        SUM(request_count) as request_count,
                        buyer_id
                    FROM rtb_traffic
                    WHERE date >= date('now', ?)
                """
                params: list[Any] = [f"-{days} days"]

                if buyer_id:
                    query += " AND buyer_id = ?"
                    params.append(buyer_id)

                query += " GROUP BY canonical_size, raw_size, buyer_id"

                cursor = conn.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]

            return await loop.run_in_executor(None, _get_traffic)

    async def get_traffic_summary(
        self,
        buyer_id: Optional[str] = None,
        days: int = 7,
    ) -> dict:
        """Get summary statistics for RTB traffic.

        Args:
            buyer_id: Optional filter by buyer seat ID.
            days: Number of days of data to summarize.

        Returns:
            Dictionary with summary statistics.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _get_summary():
                query = """
                    SELECT
                        COUNT(DISTINCT canonical_size) as unique_sizes,
                        SUM(request_count) as total_requests,
                        MIN(date) as earliest_date,
                        MAX(date) as latest_date
                    FROM rtb_traffic
                    WHERE date >= date('now', ?)
                """
                params: list[Any] = [f"-{days} days"]

                if buyer_id:
                    query += " AND buyer_id = ?"
                    params.append(buyer_id)

                cursor = conn.execute(query, params)
                row = cursor.fetchone()
                if row:
                    return dict(row)
                return {
                    "unique_sizes": 0,
                    "total_requests": 0,
                    "earliest_date": None,
                    "latest_date": None,
                }

            return await loop.run_in_executor(None, _get_summary)

    async def clear_traffic_data(
        self,
        buyer_id: Optional[str] = None,
        days_to_keep: int = 30,
    ) -> int:
        """Clear old traffic data.

        Args:
            buyer_id: Optional filter to clear only specific buyer's data.
            days_to_keep: Number of days of data to retain.

        Returns:
            Number of records deleted.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _clear_traffic():
                query = "DELETE FROM rtb_traffic WHERE date < date('now', ?)"
                params: list[Any] = [f"-{days_to_keep} days"]

                if buyer_id:
                    query += " AND buyer_id = ?"
                    params.append(buyer_id)

                cursor = conn.execute(query, params)
                conn.commit()
                return cursor.rowcount

            return await loop.run_in_executor(None, _clear_traffic)

    async def clear_old_rtb_daily(
        self,
        days_to_keep: int = 90,
    ) -> int:
        """Clear old RTB daily data beyond retention period.

        Args:
            days_to_keep: Number of days of data to retain.

        Returns:
            Number of records deleted.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _clear_old():
                cursor = conn.execute(
                    "DELETE FROM rtb_traffic WHERE date < date('now', ?)",
                    (f"-{days_to_keep} days",),
                )
                conn.commit()
                return cursor.rowcount

            return await loop.run_in_executor(None, _clear_old)
