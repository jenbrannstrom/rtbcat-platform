"""Pretargeting config breakdown precompute helpers.

Creates and refreshes daily config breakdown tables for fast UI queries.
"""

from __future__ import annotations

import logging
from typing import Optional, Sequence

from google.cloud import bigquery

from services.precompute_utils import (
    normalize_refresh_dates,
    record_refresh_log_postgres,
    refresh_window,
)

from storage.bigquery import build_table_ref, coerce_dates, get_bigquery_client, run_query
from storage.postgres import execute_many, pg_transaction_async

logger = logging.getLogger(__name__)


def _ensure_tables(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS config_size_daily (
            metric_date TEXT NOT NULL,
            buyer_account_id TEXT NOT NULL,
            billing_id TEXT NOT NULL,
            creative_size TEXT NOT NULL,
            reached_queries INTEGER DEFAULT 0,
            impressions INTEGER DEFAULT 0,
            spend_micros INTEGER DEFAULT 0,
            PRIMARY KEY (metric_date, buyer_account_id, billing_id, creative_size)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS config_geo_daily (
            metric_date TEXT NOT NULL,
            buyer_account_id TEXT NOT NULL,
            billing_id TEXT NOT NULL,
            country TEXT NOT NULL,
            reached_queries INTEGER DEFAULT 0,
            impressions INTEGER DEFAULT 0,
            spend_micros INTEGER DEFAULT 0,
            PRIMARY KEY (metric_date, buyer_account_id, billing_id, country)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS config_publisher_daily (
            metric_date TEXT NOT NULL,
            buyer_account_id TEXT NOT NULL,
            billing_id TEXT NOT NULL,
            publisher_id TEXT NOT NULL,
            publisher_name TEXT,
            reached_queries INTEGER DEFAULT 0,
            impressions INTEGER DEFAULT 0,
            spend_micros INTEGER DEFAULT 0,
            PRIMARY KEY (metric_date, buyer_account_id, billing_id, publisher_id)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS config_creative_daily (
            metric_date TEXT NOT NULL,
            buyer_account_id TEXT NOT NULL,
            billing_id TEXT NOT NULL,
            creative_id TEXT NOT NULL,
            reached_queries INTEGER DEFAULT 0,
            impressions INTEGER DEFAULT 0,
            spend_micros INTEGER DEFAULT 0,
            PRIMARY KEY (metric_date, buyer_account_id, billing_id, creative_id)
        )
        """
    )

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cfg_size_date ON config_size_daily(metric_date)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cfg_size_date_buyer_billing_size "
        "ON config_size_daily(metric_date, buyer_account_id, billing_id, creative_size)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cfg_size_billing ON config_size_daily(billing_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cfg_geo_date ON config_geo_daily(metric_date)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cfg_geo_date_buyer_billing_country "
        "ON config_geo_daily(metric_date, buyer_account_id, billing_id, country)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cfg_geo_billing ON config_geo_daily(billing_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cfg_pub_date ON config_publisher_daily(metric_date)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cfg_pub_date_buyer_billing_pub "
        "ON config_publisher_daily(metric_date, buyer_account_id, billing_id, publisher_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cfg_pub_billing ON config_publisher_daily(billing_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cfg_creative_date ON config_creative_daily(metric_date)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cfg_creative_date_buyer_billing_creative "
        "ON config_creative_daily(metric_date, buyer_account_id, billing_id, creative_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cfg_creative_billing ON config_creative_daily(billing_id)"
    )


async def refresh_config_breakdowns(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    buyer_account_id: Optional[str] = None,
    dates: Optional[Sequence[str]] = None,
    days: Optional[int] = None,
) -> dict:
    """Refresh config breakdown tables for a date range.

    Args:
        start_date: inclusive YYYY-MM-DD
        end_date: inclusive YYYY-MM-DD
        buyer_account_id: optional seat scope
        dates: Optional list of YYYY-MM-DD strings to refresh.
        days: Optional max-days window (inclusive, counting back from today).
    """
    date_list = normalize_refresh_dates(
        dates=dates,
        start_date=start_date,
        end_date=end_date,
        days=days,
    )
    refresh_start, refresh_end = refresh_window(date_list)
    logger.info(
        "Refreshing config breakdowns for %s to %s (buyer_account_id=%s)",
        refresh_start,
        refresh_end,
        buyer_account_id,
    )

    client = get_bigquery_client()
    rtb_daily_table = build_table_ref(
        client, table_env="BIGQUERY_RTB_DAILY_TABLE", default_table="rtb_daily"
    )
    dates_param = coerce_dates(date_list)
    buyer_clause = " AND buyer_account_id = @buyer_account_id" if buyer_account_id else ""
    buyer_clause_q = " AND q.buyer_account_id = @buyer_account_id" if buyer_account_id else ""

    size_rows = run_query(
        client,
        sql=f"""
            SELECT
                metric_date,
                buyer_account_id,
                billing_id,
                creative_size,
                SUM(reached_queries) AS reached_queries,
                SUM(impressions) AS impressions,
                SUM(spend_micros) AS spend_micros
            FROM `{rtb_daily_table}`
            WHERE metric_date IN UNNEST(@dates)
              AND billing_id IS NOT NULL
              AND billing_id != ''
              AND buyer_account_id IS NOT NULL
              AND buyer_account_id != ''
              AND creative_size IS NOT NULL
              AND creative_size != ''{buyer_clause}
            GROUP BY metric_date, buyer_account_id, billing_id, creative_size
        """,
        params=[
            bigquery.ArrayQueryParameter("dates", "DATE", dates_param),
            *(
                [bigquery.ScalarQueryParameter("buyer_account_id", "STRING", buyer_account_id)]
                if buyer_account_id
                else []
            ),
        ],
    )
    geo_rows = run_query(
        client,
        sql=f"""
            SELECT
                metric_date,
                buyer_account_id,
                billing_id,
                country,
                SUM(reached_queries) AS reached_queries,
                SUM(impressions) AS impressions,
                SUM(spend_micros) AS spend_micros
            FROM `{rtb_daily_table}`
            WHERE metric_date IN UNNEST(@dates)
              AND billing_id IS NOT NULL
              AND billing_id != ''
              AND buyer_account_id IS NOT NULL
              AND buyer_account_id != ''
              AND country IS NOT NULL
              AND country != ''{buyer_clause}
            GROUP BY metric_date, buyer_account_id, billing_id, country
        """,
        params=[
            bigquery.ArrayQueryParameter("dates", "DATE", dates_param),
            *(
                [bigquery.ScalarQueryParameter("buyer_account_id", "STRING", buyer_account_id)]
                if buyer_account_id
                else []
            ),
        ],
    )
    publisher_rows = run_query(
        client,
        sql=f"""
            SELECT
                q.metric_date,
                q.buyer_account_id,
                q.billing_id,
                b.publisher_id,
                MAX(b.publisher_name) AS publisher_name,
                SUM(q.reached_queries) AS reached_queries,
                SUM(q.impressions) AS impressions,
                SUM(q.spend_micros) AS spend_micros
            FROM `{rtb_daily_table}` q
            JOIN `{rtb_daily_table}` b
              ON q.metric_date = b.metric_date
             AND q.hour = b.hour
             AND q.creative_id = b.creative_id
             AND q.buyer_account_id = b.buyer_account_id
             AND q.country = b.country
            WHERE q.metric_date IN UNNEST(@dates)
              AND q.billing_id IS NOT NULL
              AND q.billing_id != ''
              AND q.buyer_account_id IS NOT NULL
              AND q.buyer_account_id != ''
              AND b.publisher_id IS NOT NULL
              AND b.publisher_id != ''{buyer_clause_q}
            GROUP BY q.metric_date, q.buyer_account_id, q.billing_id, b.publisher_id
        """,
        params=[
            bigquery.ArrayQueryParameter("dates", "DATE", dates_param),
            *(
                [bigquery.ScalarQueryParameter("buyer_account_id", "STRING", buyer_account_id)]
                if buyer_account_id
                else []
            ),
        ],
    )
    creative_rows = run_query(
        client,
        sql=f"""
            SELECT
                metric_date,
                buyer_account_id,
                billing_id,
                creative_id,
                SUM(reached_queries) AS reached_queries,
                SUM(impressions) AS impressions,
                SUM(spend_micros) AS spend_micros
            FROM `{rtb_daily_table}`
            WHERE metric_date IN UNNEST(@dates)
              AND billing_id IS NOT NULL
              AND billing_id != ''
              AND buyer_account_id IS NOT NULL
              AND buyer_account_id != ''
              AND creative_id IS NOT NULL
              AND creative_id != ''{buyer_clause}
            GROUP BY metric_date, buyer_account_id, billing_id, creative_id
        """,
        params=[
            bigquery.ArrayQueryParameter("dates", "DATE", dates_param),
            *(
                [bigquery.ScalarQueryParameter("buyer_account_id", "STRING", buyer_account_id)]
                if buyer_account_id
                else []
            ),
        ],
    )

    def _format_date(value) -> str:
        return value.isoformat() if hasattr(value, "isoformat") else str(value)

    def _run(conn):
        _ensure_tables(conn)

        delete_params = [date_list]
        buyer_filter = ""
        if buyer_account_id:
            buyer_filter = " AND buyer_account_id = %s"
            delete_params.append(buyer_account_id)

        for table in (
            "config_size_daily",
            "config_geo_daily",
            "config_publisher_daily",
            "config_creative_daily",
        ):
            conn.execute(
                f"DELETE FROM {table} WHERE metric_date = ANY(%s){buyer_filter}",
                tuple(delete_params),
            )

        execute_many(
            conn,
            sql=(
                "INSERT INTO config_size_daily "
                "(metric_date, buyer_account_id, billing_id, creative_size, reached_queries, "
                "impressions, spend_micros) VALUES (%s, %s, %s, %s, %s, %s, %s)"
            ),
            rows=[
                (
                    _format_date(row.metric_date),
                    row.buyer_account_id,
                    row.billing_id,
                    row.creative_size,
                    row.reached_queries,
                    row.impressions,
                    row.spend_micros,
                )
                for row in size_rows
            ],
        )
        execute_many(
            conn,
            sql=(
                "INSERT INTO config_geo_daily "
                "(metric_date, buyer_account_id, billing_id, country, reached_queries, impressions, "
                "spend_micros) VALUES (%s, %s, %s, %s, %s, %s, %s)"
            ),
            rows=[
                (
                    _format_date(row.metric_date),
                    row.buyer_account_id,
                    row.billing_id,
                    row.country,
                    row.reached_queries,
                    row.impressions,
                    row.spend_micros,
                )
                for row in geo_rows
            ],
        )
        execute_many(
            conn,
            sql=(
                "INSERT INTO config_publisher_daily "
                "(metric_date, buyer_account_id, billing_id, publisher_id, publisher_name, "
                "reached_queries, impressions, spend_micros) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
            ),
            rows=[
                (
                    _format_date(row.metric_date),
                    row.buyer_account_id,
                    row.billing_id,
                    row.publisher_id,
                    row.publisher_name,
                    row.reached_queries,
                    row.impressions,
                    row.spend_micros,
                )
                for row in publisher_rows
            ],
        )
        execute_many(
            conn,
            sql=(
                "INSERT INTO config_creative_daily "
                "(metric_date, buyer_account_id, billing_id, creative_id, reached_queries, "
                "impressions, spend_micros) VALUES (%s, %s, %s, %s, %s, %s, %s)"
            ),
            rows=[
                (
                    _format_date(row.metric_date),
                    row.buyer_account_id,
                    row.billing_id,
                    row.creative_id,
                    row.reached_queries,
                    row.impressions,
                    row.spend_micros,
                )
                for row in creative_rows
            ],
        )

        record_refresh_log_postgres(
            conn,
            cache_name="config_breakdowns",
            buyer_account_id=buyer_account_id,
            dates=date_list,
        )

    await pg_transaction_async(_run)

    # Return monitoring data for scheduled refresh
    return {
        "start_date": refresh_start,
        "end_date": refresh_end,
        "buyer_account_id": buyer_account_id,
        "dates": date_list,
    }
