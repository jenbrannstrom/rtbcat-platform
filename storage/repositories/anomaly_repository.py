"""Anomaly Repository for import anomalies and fraud detection.

Handles storage and retrieval of import anomalies, fraud signals,
and suspicious app detection.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

from .base import BaseRepository

logger = logging.getLogger(__name__)


class AnomalyRepository(BaseRepository):
    """Repository for import anomalies and fraud detection.

    Handles:
    - Storing anomalies detected during imports
    - Querying fraud signals by app
    - Summarizing anomaly patterns
    """

    async def save_import_anomalies(self, import_id: str, anomalies: list[dict]) -> int:
        """Store anomalies from import for later analysis.

        Args:
            import_id: Unique identifier for the import batch.
            anomalies: List of anomaly dictionaries with keys:
                - row: Row number in import
                - type: Anomaly type (e.g., 'clicks_exceed_impressions')
                - details: Dict with creative_id, app_id, app_name, etc.

        Returns:
            Number of anomalies saved.
        """
        if not anomalies:
            return 0

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _insert_anomalies():
                count = 0
                for a in anomalies:
                    try:
                        details = a.get("details", {})
                        conn.execute(
                            """
                            INSERT INTO import_anomalies
                            (import_id, row_number, anomaly_type, creative_id, app_id, app_name, details)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                import_id,
                                a.get("row"),
                                a.get("type"),
                                str(details.get("creative_id")) if details.get("creative_id") else None,
                                details.get("app_id"),
                                details.get("app_name"),
                                json.dumps(details),
                            ),
                        )
                        count += 1
                    except sqlite3.Error as e:
                        logger.warning(f"Failed to insert anomaly: {e}")
                conn.commit()
                return count

            return await loop.run_in_executor(None, _insert_anomalies)

    async def get_fraud_apps(self, limit: int = 50) -> list[dict]:
        """Get apps with most fraud signals.

        Identifies apps that have multiple fraud-related anomalies such as
        clicks exceeding impressions, extremely high CTR, or spend without
        impressions.

        Args:
            limit: Maximum number of apps to return.

        Returns:
            List of app dictionaries with:
                - app_id: App identifier
                - app_name: App display name
                - anomaly_count: Total anomalies for this app
                - anomaly_types: Number of distinct anomaly types
                - types_list: List of anomaly type strings
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    """
                    SELECT
                        app_id, app_name,
                        COUNT(*) as anomaly_count,
                        COUNT(DISTINCT anomaly_type) as anomaly_types,
                        GROUP_CONCAT(DISTINCT anomaly_type) as types_list
                    FROM import_anomalies
                    WHERE anomaly_type IN ('clicks_exceed_impressions', 'extremely_high_ctr', 'zero_impressions_with_spend')
                    AND app_id IS NOT NULL
                    GROUP BY app_id
                    ORDER BY anomaly_count DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
                return cursor.fetchall()

            rows = await loop.run_in_executor(None, _query)

        return [
            {
                "app_id": row["app_id"],
                "app_name": row["app_name"],
                "anomaly_count": row["anomaly_count"],
                "anomaly_types": row["anomaly_types"],
                "types_list": row["types_list"].split(",") if row["types_list"] else [],
            }
            for row in rows
        ]

    async def get_anomaly_summary(self) -> dict[str, int]:
        """Get summary of all import anomalies.

        Returns:
            Dictionary mapping anomaly_type to count, sorted by count descending.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    """
                    SELECT anomaly_type, COUNT(*) as count
                    FROM import_anomalies
                    GROUP BY anomaly_type
                    ORDER BY count DESC
                    """
                )
                return cursor.fetchall()

            rows = await loop.run_in_executor(None, _query)

        return {row["anomaly_type"]: row["count"] for row in rows}

    async def get_anomalies_for_creative(
        self, creative_id: str, limit: int = 100
    ) -> list[dict]:
        """Get anomalies for a specific creative.

        Args:
            creative_id: Creative ID to query.
            limit: Maximum results.

        Returns:
            List of anomaly dictionaries.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    """
                    SELECT import_id, row_number, anomaly_type, app_id, app_name, details, created_at
                    FROM import_anomalies
                    WHERE creative_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (creative_id, limit),
                )
                return [dict(row) for row in cursor.fetchall()]

            return await loop.run_in_executor(None, _query)

    async def clear_old_anomalies(self, days_to_keep: int = 90) -> int:
        """Clear anomalies older than specified days.

        Args:
            days_to_keep: Number of days of anomalies to retain.

        Returns:
            Number of anomalies deleted.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _delete():
                cursor = conn.execute(
                    """
                    DELETE FROM import_anomalies
                    WHERE created_at < datetime('now', ?)
                    """,
                    (f"-{days_to_keep} days",),
                )
                conn.commit()
                return cursor.rowcount

            return await loop.run_in_executor(None, _delete)
