"""Creatives repository - SQL queries for creative records."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from storage.postgres_database import pg_query, pg_query_one


class CreativesRepository:
    """SQL-only repository for creative queries."""

    async def get_newly_uploaded_creatives(
        self,
        period_start: datetime,
        period_end: datetime,
        limit: int,
        creative_format: Optional[str] = None,
        buyer_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get creatives first seen within a period, with spend/impressions totals."""
        query = """
            SELECT c.*,
                (SELECT SUM(spend_micros) FROM rtb_daily WHERE creative_id = c.id) as total_spend_micros,
                (SELECT SUM(impressions) FROM rtb_daily WHERE creative_id = c.id) as total_impressions
            FROM creatives c
            WHERE c.first_seen_at >= %s
              AND c.first_seen_at <= %s
        """
        params: list[Any] = [period_start, period_end]

        if creative_format:
            query += " AND c.format = %s"
            params.append(creative_format.upper())

        if buyer_id:
            query += " AND c.buyer_id = %s"
            params.append(buyer_id)

        query += " ORDER BY c.first_seen_at DESC LIMIT %s"
        params.append(limit)

        return await pg_query(query, tuple(params))

    async def get_newly_uploaded_creatives_count(
        self,
        period_start: datetime,
        period_end: datetime,
        creative_format: Optional[str] = None,
        buyer_id: Optional[str] = None,
    ) -> int:
        """Get total count for newly uploaded creatives in a period."""
        query = """
            SELECT COUNT(*) as cnt FROM creatives c
            WHERE c.first_seen_at >= %s
              AND c.first_seen_at <= %s
        """
        params: list[Any] = [period_start, period_end]

        if creative_format:
            query += " AND c.format = %s"
            params.append(creative_format.upper())
        if buyer_id:
            query += " AND c.buyer_id = %s"
            params.append(buyer_id)

        row = await pg_query_one(query, tuple(params))
        return row["cnt"] if row else 0
