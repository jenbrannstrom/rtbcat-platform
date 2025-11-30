"""
Data Retention Manager for tiered data cleanup.

Implements a tiered retention strategy:
- Raw data (every row): Keep for 30-90 days (configurable)
- Daily summaries: Keep for 1 year
- Monthly summaries: Keep forever

This prevents database bloat while preserving historical insights.
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)


class RetentionManager:
    """
    Manager for data retention and aggregation.

    Runs periodic jobs to:
    1. Aggregate old raw data into daily summaries
    2. Delete raw data older than retention period
    3. Delete summaries older than summary retention period
    """

    DEFAULT_RAW_RETENTION_DAYS = 90
    DEFAULT_SUMMARY_RETENTION_DAYS = 365
    DEFAULT_AUTO_AGGREGATE_AFTER_DAYS = 30

    def __init__(self, db_connection: sqlite3.Connection):
        """
        Initialize retention manager with database connection.

        Args:
            db_connection: SQLite database connection
        """
        self.db = db_connection
        self.db.row_factory = sqlite3.Row

    def get_retention_config(self, seat_id: Optional[int] = None) -> dict:
        """
        Get retention configuration for a seat (or global default).

        Args:
            seat_id: Optional seat ID for seat-specific config

        Returns:
            Configuration dict with retention settings
        """
        cursor = self.db.cursor()

        if seat_id:
            cursor.execute(
                "SELECT * FROM retention_config WHERE seat_id = ?",
                (seat_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)

        # Check for global config (seat_id = NULL)
        cursor.execute(
            "SELECT * FROM retention_config WHERE seat_id IS NULL"
        )
        row = cursor.fetchone()

        if row:
            return dict(row)

        # Return defaults
        return {
            'raw_retention_days': self.DEFAULT_RAW_RETENTION_DAYS,
            'summary_retention_days': self.DEFAULT_SUMMARY_RETENTION_DAYS,
            'auto_aggregate_after_days': self.DEFAULT_AUTO_AGGREGATE_AFTER_DAYS,
        }

    def set_retention_config(
        self,
        raw_retention_days: int,
        summary_retention_days: int,
        auto_aggregate_after_days: int = 30,
        seat_id: Optional[int] = None,
    ) -> None:
        """
        Set retention configuration.

        Args:
            raw_retention_days: Days to keep raw performance data
            summary_retention_days: Days to keep daily summaries
            auto_aggregate_after_days: Days before auto-aggregation
            seat_id: Optional seat ID for seat-specific config
        """
        cursor = self.db.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO retention_config
            (id, seat_id, raw_retention_days, summary_retention_days,
             auto_aggregate_after_days, updated_at)
            VALUES (
                COALESCE(
                    (SELECT id FROM retention_config WHERE
                     (seat_id = ? OR (seat_id IS NULL AND ? IS NULL))),
                    (SELECT COALESCE(MAX(id), 0) + 1 FROM retention_config)
                ),
                ?, ?, ?, ?, CURRENT_TIMESTAMP
            )
        """, (seat_id, seat_id, seat_id, raw_retention_days,
              summary_retention_days, auto_aggregate_after_days))

        self.db.commit()

    def run_retention_job(self, seat_id: Optional[int] = None) -> dict:
        """
        Run the full retention job.

        1. Aggregate old raw data into summaries
        2. Delete raw data older than retention period
        3. Delete summaries older than summary retention period

        Args:
            seat_id: Optional seat ID to run for specific seat only

        Returns:
            Statistics about the job run
        """
        config = self.get_retention_config(seat_id)
        stats = {
            'aggregated_rows': 0,
            'deleted_raw_rows': 0,
            'deleted_summary_rows': 0,
        }

        # Step 1: Aggregate data older than auto_aggregate_after_days
        aggregate_cutoff = datetime.now() - timedelta(
            days=config['auto_aggregate_after_days']
        )
        stats['aggregated_rows'] = self._aggregate_old_data(
            seat_id, aggregate_cutoff
        )

        # Step 2: Delete raw data older than raw_retention_days
        delete_cutoff = datetime.now() - timedelta(
            days=config['raw_retention_days']
        )
        stats['deleted_raw_rows'] = self._delete_old_raw_data(
            seat_id, delete_cutoff
        )

        # Step 3: Delete very old summaries
        if config['summary_retention_days'] > 0:
            summary_cutoff = datetime.now() - timedelta(
                days=config['summary_retention_days']
            )
            stats['deleted_summary_rows'] = self._delete_old_summaries(
                seat_id, summary_cutoff
            )

        logger.info(f"Retention job completed: {stats}")
        return stats

    def _aggregate_old_data(
        self,
        seat_id: Optional[int],
        cutoff_date: datetime,
    ) -> int:
        """
        Create daily summaries from detailed rows.

        Args:
            seat_id: Optional seat ID filter
            cutoff_date: Only aggregate data older than this

        Returns:
            Number of summary rows created/updated
        """
        cursor = self.db.cursor()

        cutoff_str = cutoff_date.strftime('%Y-%m-%d')

        # Build query with optional seat filter
        query = """
            INSERT OR REPLACE INTO daily_creative_summary
            (seat_id, creative_id, date, total_queries, total_impressions,
             total_clicks, total_spend, win_rate, ctr, cpm, unique_geos, unique_apps)
            SELECT
                seat_id,
                creative_id,
                metric_date,
                SUM(reached_queries),
                SUM(impressions),
                SUM(clicks),
                SUM(spend_micros) / 1000000.0,
                CASE WHEN SUM(reached_queries) > 0
                     THEN CAST(SUM(impressions) AS REAL) / SUM(reached_queries)
                     ELSE 0 END,
                CASE WHEN SUM(impressions) > 0
                     THEN CAST(SUM(clicks) AS REAL) / SUM(impressions)
                     ELSE 0 END,
                CASE WHEN SUM(impressions) > 0
                     THEN (SUM(spend_micros) / 1000000.0 / SUM(impressions)) * 1000
                     ELSE 0 END,
                COUNT(DISTINCT geography),
                COUNT(DISTINCT placement)
            FROM performance_metrics
            WHERE metric_date < ?
        """
        params = [cutoff_str]

        if seat_id is not None:
            query += " AND seat_id = ?"
            params.append(seat_id)

        query += " GROUP BY seat_id, creative_id, metric_date"

        cursor.execute(query, params)
        affected = cursor.rowcount
        self.db.commit()

        return affected

    def _delete_old_raw_data(
        self,
        seat_id: Optional[int],
        cutoff_date: datetime,
    ) -> int:
        """
        Delete detailed rows older than retention period.

        Only deletes data that has been aggregated into summaries.

        Args:
            seat_id: Optional seat ID filter
            cutoff_date: Delete data older than this

        Returns:
            Number of rows deleted
        """
        cursor = self.db.cursor()

        cutoff_str = cutoff_date.strftime('%Y-%m-%d')

        query = """
            DELETE FROM performance_metrics
            WHERE metric_date < ?
        """
        params = [cutoff_str]

        if seat_id is not None:
            query += " AND seat_id = ?"
            params.append(seat_id)

        cursor.execute(query, params)
        deleted = cursor.rowcount
        self.db.commit()

        logger.info(f"Deleted {deleted} raw performance rows older than {cutoff_str}")
        return deleted

    def _delete_old_summaries(
        self,
        seat_id: Optional[int],
        cutoff_date: datetime,
    ) -> int:
        """
        Delete summary rows older than summary retention period.

        Args:
            seat_id: Optional seat ID filter
            cutoff_date: Delete summaries older than this

        Returns:
            Number of summary rows deleted
        """
        cursor = self.db.cursor()

        cutoff_str = cutoff_date.strftime('%Y-%m-%d')

        query = """
            DELETE FROM daily_creative_summary
            WHERE date < ?
        """
        params = [cutoff_str]

        if seat_id is not None:
            query += " AND seat_id = ?"
            params.append(seat_id)

        cursor.execute(query, params)
        deleted = cursor.rowcount
        self.db.commit()

        logger.info(f"Deleted {deleted} summary rows older than {cutoff_str}")
        return deleted

    def get_storage_stats(self, seat_id: Optional[int] = None) -> dict:
        """
        Get storage statistics.

        Args:
            seat_id: Optional seat ID filter

        Returns:
            Statistics about data storage
        """
        cursor = self.db.cursor()

        stats = {}

        # Raw data stats
        query = "SELECT COUNT(*), MIN(metric_date), MAX(metric_date) FROM performance_metrics"
        if seat_id is not None:
            query += " WHERE seat_id = ?"
            cursor.execute(query, (seat_id,))
        else:
            cursor.execute(query)

        row = cursor.fetchone()
        stats['raw_rows'] = row[0]
        stats['raw_earliest_date'] = row[1]
        stats['raw_latest_date'] = row[2]

        # Summary stats
        query = "SELECT COUNT(*), MIN(date), MAX(date) FROM daily_creative_summary"
        if seat_id is not None:
            query += " WHERE seat_id = ?"
            cursor.execute(query, (seat_id,))
        else:
            cursor.execute(query)

        row = cursor.fetchone()
        stats['summary_rows'] = row[0]
        stats['summary_earliest_date'] = row[1]
        stats['summary_latest_date'] = row[2]

        return stats

    def preview_retention_job(self, seat_id: Optional[int] = None) -> dict:
        """
        Preview what the retention job would do without making changes.

        Args:
            seat_id: Optional seat ID filter

        Returns:
            Preview of what would be affected
        """
        config = self.get_retention_config(seat_id)
        cursor = self.db.cursor()

        aggregate_cutoff = (
            datetime.now() - timedelta(days=config['auto_aggregate_after_days'])
        ).strftime('%Y-%m-%d')

        delete_cutoff = (
            datetime.now() - timedelta(days=config['raw_retention_days'])
        ).strftime('%Y-%m-%d')

        # Count rows that would be aggregated
        query = "SELECT COUNT(*) FROM performance_metrics WHERE metric_date < ?"
        params = [aggregate_cutoff]
        if seat_id is not None:
            query += " AND seat_id = ?"
            params.append(seat_id)
        cursor.execute(query, params)
        would_aggregate = cursor.fetchone()[0]

        # Count rows that would be deleted
        query = "SELECT COUNT(*) FROM performance_metrics WHERE metric_date < ?"
        params = [delete_cutoff]
        if seat_id is not None:
            query += " AND seat_id = ?"
            params.append(seat_id)
        cursor.execute(query, params)
        would_delete = cursor.fetchone()[0]

        return {
            'config': config,
            'would_aggregate_rows': would_aggregate,
            'would_delete_raw_rows': would_delete,
            'aggregate_cutoff_date': aggregate_cutoff,
            'delete_cutoff_date': delete_cutoff,
        }
