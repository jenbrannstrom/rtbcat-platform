"""Postgres repository for analytics common/spend queries (SQL only)."""

from __future__ import annotations

from typing import Any, Optional

from storage.postgres_database import pg_query, pg_query_one


class AnalyticsRepository:
    """SQL-only repository for analytics queries."""

    # =========================================================================
    # Precompute Status
    # =========================================================================

    async def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        row = await pg_query_one(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = %s
            ) as exists
            """,
            (table_name,),
        )
        return row["exists"] if row else False

    async def get_precompute_row_count(
        self,
        table_name: str,
        days: int,
        filters: Optional[list[str]] = None,
        params: Optional[list] = None,
    ) -> int:
        """Get row count from a precompute table for the requested date range."""
        where_clauses = ["metric_date::date >= (CURRENT_DATE + %s::interval)"]
        query_params: list = [f"-{days} days"]
        if filters:
            where_clauses.extend(filters)
            if params:
                query_params.extend(params)

        row = await pg_query_one(
            f"""
            SELECT COUNT(*) as cnt
            FROM {table_name}
            WHERE {" AND ".join(where_clauses)}
            """,
            tuple(query_params),
        )
        return row["cnt"] or 0 if row else 0

    # =========================================================================
    # Bidder/Billing ID Lookups
    # =========================================================================

    async def get_current_bidder_id(self) -> Optional[str]:
        """Get the bidder_id from the most recently synced pretargeting config."""
        row = await pg_query_one(
            """
            SELECT bidder_id FROM pretargeting_configs
            WHERE bidder_id IS NOT NULL
            ORDER BY synced_at DESC
            LIMIT 1
            """
        )
        return row["bidder_id"] if row else None

    async def get_billing_ids_for_bidder(self, bidder_id: str) -> list[str]:
        """Get billing IDs for a specific bidder."""
        rows = await pg_query(
            """
            SELECT DISTINCT TRIM(billing_id) as billing_id
            FROM pretargeting_configs
            WHERE billing_id IS NOT NULL AND bidder_id = %s
            """,
            (bidder_id,),
        )
        return [row["billing_id"] for row in rows]

    async def get_all_billing_ids(self) -> list[str]:
        """Get all billing IDs (fallback when no bidder filter)."""
        rows = await pg_query(
            """
            SELECT DISTINCT TRIM(billing_id) as billing_id
            FROM pretargeting_configs
            WHERE billing_id IS NOT NULL
            """
        )
        return [row["billing_id"] for row in rows]

    async def get_bidder_id_for_buyer(self, buyer_id: str) -> Optional[str]:
        """Get the bidder_id for a buyer seat."""
        row = await pg_query_one(
            "SELECT bidder_id FROM buyer_seats WHERE buyer_id = %s",
            (buyer_id,),
        )
        return row["bidder_id"] if row else None

    # =========================================================================
    # Spend Stats
    # =========================================================================

    async def get_spend_stats_by_billing_id(
        self, days: int, billing_id: str
    ) -> dict[str, Any]:
        """Get spend stats filtered by a specific billing_id."""
        row = await pg_query_one(
            """
            SELECT
                COALESCE(SUM(impressions), 0) as total_impressions,
                COALESCE(SUM(spend_micros), 0) as total_spend_micros
            FROM rtb_app_daily
            WHERE metric_date::date >= (CURRENT_DATE + %s::interval)
              AND billing_id = %s
            """,
            (f"-{days} days", billing_id),
        )
        return dict(row) if row else {"total_impressions": 0, "total_spend_micros": 0}

    async def get_spend_stats_by_billing_ids(
        self, days: int, billing_ids: list[str]
    ) -> dict[str, Any]:
        """Get spend stats filtered by multiple billing_ids."""
        row = await pg_query_one(
            """
            SELECT
                COALESCE(SUM(impressions), 0) as total_impressions,
                COALESCE(SUM(spend_micros), 0) as total_spend_micros
            FROM rtb_app_daily
            WHERE metric_date::date >= (CURRENT_DATE + %s::interval)
              AND billing_id = ANY(%s)
            """,
            (f"-{days} days", billing_ids),
        )
        return dict(row) if row else {"total_impressions": 0, "total_spend_micros": 0}

    async def get_spend_stats_all(self, days: int) -> dict[str, Any]:
        """Get spend stats without billing_id filter."""
        row = await pg_query_one(
            """
            SELECT
                COALESCE(SUM(impressions), 0) as total_impressions,
                COALESCE(SUM(spend_micros), 0) as total_spend_micros
            FROM rtb_app_daily
            WHERE metric_date::date >= (CURRENT_DATE + %s::interval)
            """,
            (f"-{days} days",),
        )
        return dict(row) if row else {"total_impressions": 0, "total_spend_micros": 0}
