"""Postgres repository for admin diagnostics and stats (SQL only)."""

from __future__ import annotations

from typing import Any

from storage.postgres_database import pg_execute, pg_query, pg_query_one


class AdminRepository:
    """SQL-only repository for admin endpoints."""

    async def get_active_buyer_ids(self) -> list[str]:
        rows = await pg_query(
            "SELECT DISTINCT buyer_id FROM buyer_seats WHERE active = 1 ORDER BY buyer_id"
        )
        return [row["buyer_id"] for row in rows]

    async def get_latest_gmail_import_date(self, buyer_id: str) -> Any:
        row = await pg_query_one(
            "SELECT MAX(report_date) as latest FROM gmail_import_runs WHERE buyer_account_id = %s",
            (buyer_id,),
        )
        return row["latest"] if row else None

    async def get_gmail_import_runs(self, buyer_id: str, report_date: Any) -> list[dict[str, Any]]:
        return await pg_query(
            """
            SELECT report_kind, success
            FROM gmail_import_runs
            WHERE buyer_account_id = %s AND report_date = %s
            """,
            (buyer_id, report_date),
        )

    async def list_buyer_seats_with_creative_count(self) -> list[dict[str, Any]]:
        return await pg_query(
            """
            SELECT bs.buyer_id, bs.bidder_id, bs.display_name, bs.active,
                   COALESCE(c.cnt, 0) as creative_count,
                   bs.last_synced, bs.service_account_id
            FROM buyer_seats bs
            LEFT JOIN (
                SELECT account_id, COUNT(*) as cnt FROM creatives GROUP BY account_id
            ) c ON c.account_id = bs.buyer_id
            ORDER BY bs.display_name, bs.buyer_id
            """
        )

    async def list_campaign_samples(self, limit: int = 20) -> list[dict[str, Any]]:
        return await pg_query(
            "SELECT id, name, creative_ids FROM campaigns LIMIT %s",
            (limit,),
        )

    async def get_thumbnail_status_summary(self) -> list[dict[str, Any]]:
        return await pg_query(
            """
            SELECT
                format,
                COUNT(*) as total,
                SUM(
                    CASE WHEN thumbnail_url IS NOT NULL AND thumbnail_url != '' THEN 1 ELSE 0 END
                ) as with_thumbnail
            FROM creatives
            GROUP BY format
            """
        )

    async def get_import_history_by_buyer(self) -> list[dict[str, Any]]:
        return await pg_query(
            """
            SELECT
                buyer_id,
                COUNT(*) as import_count,
                MAX(imported_at) as last_import,
                SUM(rows_imported) as total_records
            FROM import_history
            GROUP BY buyer_id
            ORDER BY last_import DESC
            """
        )

    async def get_creative_id_samples(self, limit: int = 5) -> list[dict[str, Any]]:
        return await pg_query(
            "SELECT id, pg_typeof(id)::text as type, account_id FROM creatives LIMIT %s",
            (limit,),
        )

    async def count_inactive_seats(self) -> int:
        row = await pg_query_one(
            "SELECT COUNT(*) as cnt FROM buyer_seats WHERE active = 0"
        )
        return row["cnt"] if row else 0

    async def activate_inactive_seats(self) -> None:
        await pg_execute("UPDATE buyer_seats SET active = 1 WHERE active = 0")
