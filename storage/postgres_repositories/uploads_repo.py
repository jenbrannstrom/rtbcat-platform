"""Uploads repository - SQL queries for import history and upload tracking."""

from __future__ import annotations

from typing import Any, Optional

from storage.postgres_database import pg_query, pg_query_one, pg_execute


class UploadsRepository:
    """SQL-only repository for upload tracking and import history."""

    REPORT_TYPE_CASE_SQL = """
        CASE
            WHEN report_type IN ('quality', 'catscan-quality') THEN 'quality'
            WHEN report_type IN ('bidsinauction', 'catscan-bidsinauction') THEN 'bidsinauction'
            WHEN report_type IN ('pipeline-geo', 'catscan-pipeline-geo') THEN 'pipeline-geo'
            WHEN report_type IN ('pipeline-publisher', 'pipeline', 'catscan-pipeline') THEN 'pipeline-publisher'
            WHEN report_type IN ('bid-filtering', 'catscan-bid-filtering') THEN 'bid-filtering'
            ELSE NULL
        END
    """

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

    async def get_active_import_accounts(
        self,
        allowed_bidder_ids: Optional[list[str]] = None,
        buyer_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Return active buyer accounts that should appear in import tracking."""
        if buyer_id:
            return await pg_query(
                """
                SELECT buyer_id, bidder_id, display_name
                FROM buyer_seats
                WHERE active = true AND buyer_id = %s
                ORDER BY buyer_id
                """,
                (buyer_id,),
            )

        if allowed_bidder_ids is None:
            return await pg_query(
                """
                SELECT buyer_id, bidder_id, display_name
                FROM buyer_seats
                WHERE active = true
                ORDER BY buyer_id
                """
            )

        return await pg_query(
            """
            SELECT buyer_id, bidder_id, display_name
            FROM buyer_seats
            WHERE active = true
              AND bidder_id = ANY(%s)
            ORDER BY buyer_id
            """,
            (allowed_bidder_ids,),
        )

    async def get_latest_import_matrix_runs(
        self,
        start_date: str,
        buyer_ids: list[str],
    ) -> list[dict[str, Any]]:
        """Return latest ingestion run per buyer_id and canonical CSV type."""
        if not buyer_ids:
            return []

        return await pg_query(
            f"""
            WITH normalized AS (
                SELECT
                    COALESCE(NULLIF(buyer_id, ''), NULLIF(bidder_id, '')) AS account_id,
                    {self.REPORT_TYPE_CASE_SQL} AS csv_type,
                    status,
                    COALESCE(NULLIF(import_trigger, ''), 'manual') AS import_trigger,
                    started_at,
                    finished_at,
                    error_summary
                FROM ingestion_runs
                WHERE COALESCE(finished_at, started_at) >= %s::timestamptz
                  AND COALESCE(NULLIF(buyer_id, ''), NULLIF(bidder_id, '')) = ANY(%s)
            ),
            ranked AS (
                SELECT
                    account_id,
                    csv_type,
                    status,
                    import_trigger,
                    started_at,
                    finished_at,
                    error_summary,
                    ROW_NUMBER() OVER (
                        PARTITION BY account_id, csv_type
                        ORDER BY COALESCE(finished_at, started_at) DESC, started_at DESC
                    ) AS rn
                FROM normalized
                WHERE account_id IS NOT NULL
                  AND csv_type IS NOT NULL
            )
            SELECT
                account_id,
                csv_type,
                status,
                import_trigger,
                started_at,
                finished_at,
                error_summary
            FROM ranked
            WHERE rn = 1
            """,
            (start_date, buyer_ids),
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

    async def record_import_history(
        self,
        batch_id: str,
        filename: Optional[str],
        rows_read: int,
        rows_imported: int,
        rows_skipped: int,
        rows_duplicate: int,
        date_range_start: Optional[str],
        date_range_end: Optional[str],
        columns_found: Optional[str],
        columns_missing: Optional[str],
        total_reached: int,
        total_impressions: int,
        total_spend_usd: float,
        status: str,
        error_message: Optional[str],
        file_size_bytes: int,
        date_gaps: Optional[str] = None,
        date_gap_warning: Optional[str] = None,
        buyer_id: Optional[str] = None,
        bidder_id: Optional[str] = None,
        import_trigger: str = "manual",
    ) -> None:
        """Record an import in import_history table."""
        await pg_execute(
            """
            INSERT INTO import_history (
                batch_id, filename, rows_read, rows_imported, rows_skipped, rows_duplicate,
                date_range_start, date_range_end, columns_found, columns_missing,
                total_reached, total_impressions, total_spend_usd, status, error_message,
                file_size_bytes, date_gaps, date_gap_warning, buyer_id, bidder_id, import_trigger
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                batch_id,
                filename,
                rows_read,
                rows_imported,
                rows_skipped,
                rows_duplicate,
                date_range_start,
                date_range_end,
                columns_found,
                columns_missing,
                total_reached,
                total_impressions,
                total_spend_usd,
                status,
                error_message,
                file_size_bytes,
                date_gaps,
                date_gap_warning,
                buyer_id,
                bidder_id,
                import_trigger,
            ),
        )

    async def start_ingestion_run(
        self,
        run_id: str,
        source_type: str,
        buyer_id: Optional[str] = None,
        bidder_id: Optional[str] = None,
        report_type: Optional[str] = None,
        filename: Optional[str] = None,
        import_trigger: str = "manual",
    ) -> None:
        """Insert a new ingestion_runs row with status='running'."""
        await pg_execute(
            """
            INSERT INTO ingestion_runs (
                run_id, source_type, buyer_id, bidder_id, status,
                report_type, filename, import_trigger
            ) VALUES (%s, %s, %s, %s, 'running', %s, %s, %s)
            """,
            (run_id, source_type, buyer_id, bidder_id, report_type, filename, import_trigger),
        )

    async def finish_ingestion_run(
        self,
        run_id: str,
        status: str,
        row_count: int = 0,
        error_summary: Optional[str] = None,
        report_type: Optional[str] = None,
    ) -> None:
        """Finalize an ingestion run. Only updates if finished_at IS NULL (no double-write)."""
        await pg_execute(
            """
            UPDATE ingestion_runs
            SET status = %s,
                row_count = %s,
                error_summary = %s,
                report_type = COALESCE(%s, report_type),
                finished_at = CURRENT_TIMESTAMP
            WHERE run_id = %s AND finished_at IS NULL
            """,
            (status, row_count, error_summary, report_type, run_id),
        )

    async def get_current_date(self) -> Optional[str]:
        """Get current date from database."""
        row = await pg_query_one("SELECT CURRENT_DATE as dt")
        return str(row["dt"]) if row and row["dt"] else None

    async def update_daily_upload_summary(
        self,
        upload_date: str,
        rows_imported: int,
        file_size_bytes: int,
        success: bool = True,
    ) -> None:
        """Update daily upload summary with a new import."""
        if success:
            await pg_execute("""
                INSERT INTO daily_upload_summary (
                    upload_date, total_uploads, successful_uploads, failed_uploads,
                    total_rows_written, total_file_size_bytes, min_rows, max_rows, avg_rows_per_upload
                ) VALUES (%s, 1, 1, 0, %s, %s, %s, %s, %s)
                ON CONFLICT(upload_date) DO UPDATE SET
                    total_uploads = daily_upload_summary.total_uploads + 1,
                    successful_uploads = daily_upload_summary.successful_uploads + 1,
                    total_rows_written = daily_upload_summary.total_rows_written + EXCLUDED.total_rows_written,
                    total_file_size_bytes = daily_upload_summary.total_file_size_bytes + EXCLUDED.total_file_size_bytes,
                    min_rows = LEAST(daily_upload_summary.min_rows, EXCLUDED.min_rows),
                    max_rows = GREATEST(daily_upload_summary.max_rows, EXCLUDED.max_rows),
                    avg_rows_per_upload = (daily_upload_summary.total_rows_written + EXCLUDED.total_rows_written) / (daily_upload_summary.total_uploads + 1)
            """, (
                upload_date,
                rows_imported,
                file_size_bytes,
                rows_imported,
                rows_imported,
                rows_imported,
            ))
        else:
            await pg_execute("""
                INSERT INTO daily_upload_summary (
                    upload_date, total_uploads, successful_uploads, failed_uploads,
                    total_rows_written, total_file_size_bytes
                ) VALUES (%s, 1, 0, 1, 0, %s)
                ON CONFLICT(upload_date) DO UPDATE SET
                    total_uploads = daily_upload_summary.total_uploads + 1,
                    failed_uploads = daily_upload_summary.failed_uploads + 1,
                    total_file_size_bytes = daily_upload_summary.total_file_size_bytes + EXCLUDED.total_file_size_bytes
            """, (upload_date, file_size_bytes))
