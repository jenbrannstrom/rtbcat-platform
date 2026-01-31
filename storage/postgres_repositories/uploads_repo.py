"""Uploads repository - SQL queries for import history and upload tracking."""

from __future__ import annotations

from typing import Any, Optional

from storage.postgres_database import pg_query, pg_query_one


class UploadsRepository:
    """SQL-only repository for upload tracking and import history."""

    async def get_daily_upload_summaries(self, limit: int) -> list[dict[str, Any]]:
        """Get daily upload summary records."""
        return await pg_query(
            """SELECT * FROM daily_upload_summary
            ORDER BY upload_date DESC
            LIMIT %s""",
            (limit,),
        )

    async def get_import_history(
        self,
        limit: int,
        offset: int,
        bidder_id: Optional[str] = None,
        allowed_bidder_ids: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Get import history records with optional filtering."""
        if bidder_id:
            return await pg_query(
                """SELECT * FROM import_history
                WHERE bidder_id = %s
                ORDER BY imported_at DESC
                LIMIT %s OFFSET %s""",
                (bidder_id, limit, offset),
            )
        elif allowed_bidder_ids is None:
            return await pg_query(
                """SELECT * FROM import_history
                ORDER BY imported_at DESC
                LIMIT %s OFFSET %s""",
                (limit, offset),
            )
        else:
            return await pg_query(
                """SELECT * FROM import_history
                WHERE bidder_id = ANY(%s)
                ORDER BY imported_at DESC
                LIMIT %s OFFSET %s""",
                (allowed_bidder_ids, limit, offset),
            )

    async def get_daily_imports(
        self,
        start_date: str,
        allowed_bidder_ids: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Get imports grouped by date for the grid view."""
        if allowed_bidder_ids is None:
            return await pg_query(
                """
                SELECT
                    date(imported_at) as import_date,
                    rows_imported,
                    status,
                    error_message,
                    filename
                FROM import_history
                WHERE date(imported_at) >= %s
                ORDER BY imported_at ASC
                """,
                (start_date,),
            )
        else:
            return await pg_query(
                """
                SELECT
                    date(imported_at) as import_date,
                    rows_imported,
                    status,
                    error_message,
                    filename
                FROM import_history
                WHERE date(imported_at) >= %s
                  AND bidder_id = ANY(%s)
                ORDER BY imported_at ASC
                """,
                (start_date, allowed_bidder_ids),
            )

    async def get_account_upload_stats(
        self,
        allowed_bidder_ids: Optional[list[str]] = None,
    ) -> list[dict[str, Any]]:
        """Get upload statistics grouped by bidder_id."""
        if allowed_bidder_ids is None:
            return await pg_query("""
                SELECT
                    bidder_id,
                    COUNT(*) as upload_count,
                    SUM(rows_imported) as total_rows,
                    MAX(imported_at) as latest_upload,
                    STRING_AGG(DISTINCT billing_ids_found, ',') as all_billing_ids
                FROM import_history
                WHERE bidder_id IS NOT NULL
                GROUP BY bidder_id
                ORDER BY latest_upload DESC
            """)
        else:
            return await pg_query(
                """
                SELECT
                    bidder_id,
                    COUNT(*) as upload_count,
                    SUM(rows_imported) as total_rows,
                    MAX(imported_at) as latest_upload,
                    STRING_AGG(DISTINCT billing_ids_found, ',') as all_billing_ids
                FROM import_history
                WHERE bidder_id = ANY(%s)
                GROUP BY bidder_id
                ORDER BY latest_upload DESC
                """,
                (allowed_bidder_ids,),
            )

    async def get_unassigned_uploads_count(self) -> int:
        """Get count of imports without bidder_id."""
        row = await pg_query_one(
            "SELECT COUNT(*) as cnt FROM import_history WHERE bidder_id IS NULL"
        )
        return row["cnt"] if row else 0

    async def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        row = await pg_query_one(
            """SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = %s
            ) as exists""",
            (table_name,),
        )
        return row["exists"] if row else False
