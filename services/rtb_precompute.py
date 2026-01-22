"""RTB funnel + drilldown precompute helpers.

Creates and refreshes daily summary tables for RTB analytics endpoints.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from google.cloud import bigquery

from storage.bigquery import build_table_ref, get_bigquery_client, run_query
from storage.postgres import execute_many, pg_transaction_async
from services.precompute_utils import normalize_refresh_dates, record_refresh_log

logger = logging.getLogger(__name__)


RTB_TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS rtb_funnel_daily (
        metric_date TEXT NOT NULL,
        buyer_account_id TEXT NOT NULL,
        reached_queries INTEGER DEFAULT 0,
        impressions INTEGER DEFAULT 0,
        bids INTEGER DEFAULT 0,
        successful_responses INTEGER DEFAULT 0,
        bid_requests INTEGER DEFAULT 0,
        auctions_won INTEGER DEFAULT 0,
        PRIMARY KEY (metric_date, buyer_account_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rtb_publisher_daily (
        metric_date TEXT NOT NULL,
        buyer_account_id TEXT NOT NULL,
        publisher_id TEXT NOT NULL,
        publisher_name TEXT,
        reached_queries INTEGER DEFAULT 0,
        impressions INTEGER DEFAULT 0,
        bids INTEGER DEFAULT 0,
        successful_responses INTEGER DEFAULT 0,
        bid_requests INTEGER DEFAULT 0,
        auctions_won INTEGER DEFAULT 0,
        PRIMARY KEY (metric_date, buyer_account_id, publisher_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rtb_geo_daily (
        metric_date TEXT NOT NULL,
        buyer_account_id TEXT NOT NULL,
        country TEXT NOT NULL,
        reached_queries INTEGER DEFAULT 0,
        impressions INTEGER DEFAULT 0,
        bids INTEGER DEFAULT 0,
        successful_responses INTEGER DEFAULT 0,
        bid_requests INTEGER DEFAULT 0,
        auctions_won INTEGER DEFAULT 0,
        PRIMARY KEY (metric_date, buyer_account_id, country)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rtb_app_daily (
        metric_date TEXT NOT NULL,
        buyer_account_id TEXT NOT NULL,
        app_name TEXT NOT NULL,
        app_id TEXT,
        billing_id TEXT NOT NULL,
        reached_queries INTEGER DEFAULT 0,
        impressions INTEGER DEFAULT 0,
        clicks INTEGER DEFAULT 0,
        spend_micros INTEGER DEFAULT 0,
        PRIMARY KEY (metric_date, buyer_account_id, app_name, billing_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rtb_app_size_daily (
        metric_date TEXT NOT NULL,
        buyer_account_id TEXT NOT NULL,
        app_name TEXT NOT NULL,
        app_id TEXT,
        billing_id TEXT NOT NULL,
        creative_size TEXT NOT NULL,
        creative_format TEXT,
        reached_queries INTEGER DEFAULT 0,
        impressions INTEGER DEFAULT 0,
        clicks INTEGER DEFAULT 0,
        spend_micros INTEGER DEFAULT 0,
        PRIMARY KEY (metric_date, buyer_account_id, app_name, billing_id, creative_size, creative_format)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rtb_app_country_daily (
        metric_date TEXT NOT NULL,
        buyer_account_id TEXT NOT NULL,
        app_name TEXT NOT NULL,
        app_id TEXT,
        billing_id TEXT NOT NULL,
        country TEXT NOT NULL,
        reached_queries INTEGER DEFAULT 0,
        impressions INTEGER DEFAULT 0,
        clicks INTEGER DEFAULT 0,
        spend_micros INTEGER DEFAULT 0,
        PRIMARY KEY (metric_date, buyer_account_id, app_name, billing_id, country)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS rtb_app_creative_daily (
        metric_date TEXT NOT NULL,
        buyer_account_id TEXT NOT NULL,
        app_name TEXT NOT NULL,
        app_id TEXT,
        billing_id TEXT NOT NULL,
        creative_id TEXT NOT NULL,
        creative_size TEXT,
        creative_format TEXT,
        reached_queries INTEGER DEFAULT 0,
        impressions INTEGER DEFAULT 0,
        clicks INTEGER DEFAULT 0,
        spend_micros INTEGER DEFAULT 0,
        PRIMARY KEY (metric_date, buyer_account_id, app_name, billing_id, creative_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_rtb_funnel_date ON rtb_funnel_daily(metric_date)",
    "CREATE INDEX IF NOT EXISTS idx_rtb_publisher_date ON rtb_publisher_daily(metric_date)",
    "CREATE INDEX IF NOT EXISTS idx_rtb_geo_date ON rtb_geo_daily(metric_date)",
    "CREATE INDEX IF NOT EXISTS idx_rtb_app_date ON rtb_app_daily(metric_date)",
    "CREATE INDEX IF NOT EXISTS idx_rtb_app_name ON rtb_app_daily(app_name)",
    "CREATE INDEX IF NOT EXISTS idx_rtb_app_billing ON rtb_app_daily(billing_id)",
    "CREATE INDEX IF NOT EXISTS idx_rtb_app_size_name ON rtb_app_size_daily(app_name)",
    "CREATE INDEX IF NOT EXISTS idx_rtb_app_country_name ON rtb_app_country_daily(app_name)",
    "CREATE INDEX IF NOT EXISTS idx_rtb_app_creative_name ON rtb_app_creative_daily(app_name)",
]


async def refresh_rtb_summaries(
    start_date: str,
    end_date: str,
    buyer_account_id: Optional[str] = None,
) -> dict:
    """Refresh RTB precompute tables for a date range."""
    date_list = normalize_refresh_dates(start_date=start_date, end_date=end_date)
    logger.info(
        "Refreshing RTB summaries for %s to %s (buyer_account_id=%s)",
        start_date,
        end_date,
        buyer_account_id,
    )
    client = get_bigquery_client()
    bidstream_table = build_table_ref(
        client, table_env="BIGQUERY_RTB_BIDSTREAM_TABLE", default_table="rtb_bidstream"
    )
    rtb_daily_table = build_table_ref(
        client, table_env="BIGQUERY_RTB_DAILY_TABLE", default_table="rtb_daily"
    )
    buyer_clause = " AND buyer_account_id = @buyer_account_id" if buyer_account_id else ""
    start_date_value = date.fromisoformat(start_date)
    end_date_value = date.fromisoformat(end_date)

    funnel_rows = run_query(
        client,
        sql=f"""
            SELECT
                metric_date,
                COALESCE(buyer_account_id, '') AS buyer_account_id,
                SUM(reached_queries) AS reached_queries,
                SUM(impressions) AS impressions,
                SUM(bids) AS bids,
                SUM(successful_responses) AS successful_responses,
                SUM(bid_requests) AS bid_requests,
                SUM(auctions_won) AS auctions_won
            FROM `{bidstream_table}`
            WHERE metric_date BETWEEN @start_date AND @end_date{buyer_clause}
            GROUP BY metric_date, COALESCE(buyer_account_id, '')
        """,
        params=[
            bigquery.ScalarQueryParameter("start_date", "DATE", start_date_value),
            bigquery.ScalarQueryParameter("end_date", "DATE", end_date_value),
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
                metric_date,
                COALESCE(buyer_account_id, '') AS buyer_account_id,
                publisher_id,
                MAX(publisher_name) AS publisher_name,
                SUM(reached_queries) AS reached_queries,
                SUM(impressions) AS impressions,
                SUM(bids) AS bids,
                SUM(successful_responses) AS successful_responses,
                SUM(bid_requests) AS bid_requests,
                SUM(auctions_won) AS auctions_won
            FROM `{bidstream_table}`
            WHERE metric_date BETWEEN @start_date AND @end_date
              AND publisher_id IS NOT NULL
              AND publisher_id != ''{buyer_clause}
            GROUP BY metric_date, COALESCE(buyer_account_id, ''), publisher_id
        """,
        params=[
            bigquery.ScalarQueryParameter("start_date", "DATE", start_date_value),
            bigquery.ScalarQueryParameter("end_date", "DATE", end_date_value),
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
                COALESCE(buyer_account_id, '') AS buyer_account_id,
                country,
                SUM(reached_queries) AS reached_queries,
                SUM(impressions) AS impressions,
                SUM(bids) AS bids,
                SUM(successful_responses) AS successful_responses,
                SUM(bid_requests) AS bid_requests,
                SUM(auctions_won) AS auctions_won
            FROM `{bidstream_table}`
            WHERE metric_date BETWEEN @start_date AND @end_date
              AND country IS NOT NULL
              AND country != ''{buyer_clause}
            GROUP BY metric_date, COALESCE(buyer_account_id, ''), country
        """,
        params=[
            bigquery.ScalarQueryParameter("start_date", "DATE", start_date_value),
            bigquery.ScalarQueryParameter("end_date", "DATE", end_date_value),
            *(
                [bigquery.ScalarQueryParameter("buyer_account_id", "STRING", buyer_account_id)]
                if buyer_account_id
                else []
            ),
        ],
    )
    app_rows = run_query(
        client,
        sql=f"""
            SELECT
                metric_date,
                COALESCE(buyer_account_id, '') AS buyer_account_id,
                app_name,
                MAX(app_id) AS app_id,
                COALESCE(billing_id, '') AS billing_id,
                SUM(reached_queries) AS reached_queries,
                SUM(impressions) AS impressions,
                SUM(clicks) AS clicks,
                SUM(spend_micros) AS spend_micros
            FROM `{rtb_daily_table}`
            WHERE metric_date BETWEEN @start_date AND @end_date
              AND app_name IS NOT NULL
              AND app_name != ''{buyer_clause}
            GROUP BY metric_date, COALESCE(buyer_account_id, ''), app_name, COALESCE(billing_id, '')
        """,
        params=[
            bigquery.ScalarQueryParameter("start_date", "DATE", start_date_value),
            bigquery.ScalarQueryParameter("end_date", "DATE", end_date_value),
            *(
                [bigquery.ScalarQueryParameter("buyer_account_id", "STRING", buyer_account_id)]
                if buyer_account_id
                else []
            ),
        ],
    )
    app_size_rows = run_query(
        client,
        sql=f"""
            SELECT
                metric_date,
                COALESCE(buyer_account_id, '') AS buyer_account_id,
                app_name,
                MAX(app_id) AS app_id,
                COALESCE(billing_id, '') AS billing_id,
                creative_size,
                creative_format,
                SUM(reached_queries) AS reached_queries,
                SUM(impressions) AS impressions,
                SUM(clicks) AS clicks,
                SUM(spend_micros) AS spend_micros
            FROM `{rtb_daily_table}`
            WHERE metric_date BETWEEN @start_date AND @end_date
              AND app_name IS NOT NULL
              AND app_name != ''
              AND creative_size IS NOT NULL
              AND creative_size != ''{buyer_clause}
            GROUP BY metric_date, COALESCE(buyer_account_id, ''), app_name, COALESCE(billing_id, ''),
                     creative_size, creative_format
        """,
        params=[
            bigquery.ScalarQueryParameter("start_date", "DATE", start_date_value),
            bigquery.ScalarQueryParameter("end_date", "DATE", end_date_value),
            *(
                [bigquery.ScalarQueryParameter("buyer_account_id", "STRING", buyer_account_id)]
                if buyer_account_id
                else []
            ),
        ],
    )
    app_country_rows = run_query(
        client,
        sql=f"""
            SELECT
                metric_date,
                COALESCE(buyer_account_id, '') AS buyer_account_id,
                app_name,
                MAX(app_id) AS app_id,
                COALESCE(billing_id, '') AS billing_id,
                country,
                SUM(reached_queries) AS reached_queries,
                SUM(impressions) AS impressions,
                SUM(clicks) AS clicks,
                SUM(spend_micros) AS spend_micros
            FROM `{rtb_daily_table}`
            WHERE metric_date BETWEEN @start_date AND @end_date
              AND app_name IS NOT NULL
              AND app_name != ''
              AND country IS NOT NULL
              AND country != ''{buyer_clause}
            GROUP BY metric_date, COALESCE(buyer_account_id, ''), app_name, COALESCE(billing_id, ''), country
        """,
        params=[
            bigquery.ScalarQueryParameter("start_date", "DATE", start_date_value),
            bigquery.ScalarQueryParameter("end_date", "DATE", end_date_value),
            *(
                [bigquery.ScalarQueryParameter("buyer_account_id", "STRING", buyer_account_id)]
                if buyer_account_id
                else []
            ),
        ],
    )
    app_creative_rows = run_query(
        client,
        sql=f"""
            SELECT
                metric_date,
                COALESCE(buyer_account_id, '') AS buyer_account_id,
                app_name,
                MAX(app_id) AS app_id,
                COALESCE(billing_id, '') AS billing_id,
                creative_id,
                creative_size,
                creative_format,
                SUM(reached_queries) AS reached_queries,
                SUM(impressions) AS impressions,
                SUM(clicks) AS clicks,
                SUM(spend_micros) AS spend_micros
            FROM `{rtb_daily_table}`
            WHERE metric_date BETWEEN @start_date AND @end_date
              AND app_name IS NOT NULL
              AND app_name != ''
              AND creative_id IS NOT NULL
              AND creative_id != ''{buyer_clause}
            GROUP BY metric_date, COALESCE(buyer_account_id, ''), app_name, COALESCE(billing_id, ''),
                     creative_id, creative_size, creative_format
        """,
        params=[
            bigquery.ScalarQueryParameter("start_date", "DATE", start_date_value),
            bigquery.ScalarQueryParameter("end_date", "DATE", end_date_value),
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
        for stmt in RTB_TABLES_SQL:
            conn.execute(stmt)

        delete_params = [start_date, end_date]
        buyer_filter = ""
        if buyer_account_id:
            buyer_filter = " AND buyer_account_id = %s"
            delete_params.append(buyer_account_id)

        for table in (
            "rtb_funnel_daily",
            "rtb_publisher_daily",
            "rtb_geo_daily",
            "rtb_app_daily",
            "rtb_app_size_daily",
            "rtb_app_country_daily",
            "rtb_app_creative_daily",
        ):
            conn.execute(
                f"DELETE FROM {table} WHERE metric_date BETWEEN %s AND %s{buyer_filter}",
                tuple(delete_params),
            )

        execute_many(
            conn,
            sql=(
                "INSERT INTO rtb_funnel_daily "
                "(metric_date, buyer_account_id, reached_queries, impressions, bids, "
                "successful_responses, bid_requests, auctions_won) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
            ),
            rows=[
                (
                    _format_date(row.metric_date),
                    row.buyer_account_id,
                    row.reached_queries,
                    row.impressions,
                    row.bids,
                    row.successful_responses,
                    row.bid_requests,
                    row.auctions_won,
                )
                for row in funnel_rows
            ],
        )
        execute_many(
            conn,
            sql=(
                "INSERT INTO rtb_publisher_daily "
                "(metric_date, buyer_account_id, publisher_id, publisher_name, reached_queries, "
                "impressions, bids, successful_responses, bid_requests, auctions_won) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            ),
            rows=[
                (
                    _format_date(row.metric_date),
                    row.buyer_account_id,
                    row.publisher_id,
                    row.publisher_name,
                    row.reached_queries,
                    row.impressions,
                    row.bids,
                    row.successful_responses,
                    row.bid_requests,
                    row.auctions_won,
                )
                for row in publisher_rows
            ],
        )
        execute_many(
            conn,
            sql=(
                "INSERT INTO rtb_geo_daily "
                "(metric_date, buyer_account_id, country, reached_queries, impressions, bids, "
                "successful_responses, bid_requests, auctions_won) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
            ),
            rows=[
                (
                    _format_date(row.metric_date),
                    row.buyer_account_id,
                    row.country,
                    row.reached_queries,
                    row.impressions,
                    row.bids,
                    row.successful_responses,
                    row.bid_requests,
                    row.auctions_won,
                )
                for row in geo_rows
            ],
        )
        execute_many(
            conn,
            sql=(
                "INSERT INTO rtb_app_daily "
                "(metric_date, buyer_account_id, app_name, app_id, billing_id, reached_queries, "
                "impressions, clicks, spend_micros) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
            ),
            rows=[
                (
                    _format_date(row.metric_date),
                    row.buyer_account_id,
                    row.app_name,
                    row.app_id,
                    row.billing_id,
                    row.reached_queries,
                    row.impressions,
                    row.clicks,
                    row.spend_micros,
                )
                for row in app_rows
            ],
        )
        execute_many(
            conn,
            sql=(
                "INSERT INTO rtb_app_size_daily "
                "(metric_date, buyer_account_id, app_name, app_id, billing_id, creative_size, "
                "creative_format, reached_queries, impressions, clicks, spend_micros) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            ),
            rows=[
                (
                    _format_date(row.metric_date),
                    row.buyer_account_id,
                    row.app_name,
                    row.app_id,
                    row.billing_id,
                    row.creative_size,
                    row.creative_format,
                    row.reached_queries,
                    row.impressions,
                    row.clicks,
                    row.spend_micros,
                )
                for row in app_size_rows
            ],
        )
        execute_many(
            conn,
            sql=(
                "INSERT INTO rtb_app_country_daily "
                "(metric_date, buyer_account_id, app_name, app_id, billing_id, country, "
                "reached_queries, impressions, clicks, spend_micros) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            ),
            rows=[
                (
                    _format_date(row.metric_date),
                    row.buyer_account_id,
                    row.app_name,
                    row.app_id,
                    row.billing_id,
                    row.country,
                    row.reached_queries,
                    row.impressions,
                    row.clicks,
                    row.spend_micros,
                )
                for row in app_country_rows
            ],
        )
        execute_many(
            conn,
            sql=(
                "INSERT INTO rtb_app_creative_daily "
                "(metric_date, buyer_account_id, app_name, app_id, billing_id, creative_id, "
                "creative_size, creative_format, reached_queries, impressions, clicks, spend_micros) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            ),
            rows=[
                (
                    _format_date(row.metric_date),
                    row.buyer_account_id,
                    row.app_name,
                    row.app_id,
                    row.billing_id,
                    row.creative_id,
                    row.creative_size,
                    row.creative_format,
                    row.reached_queries,
                    row.impressions,
                    row.clicks,
                    row.spend_micros,
                )
                for row in app_creative_rows
            ],
        )

        record_refresh_log(
            conn,
            cache_name="rtb_summaries",
            buyer_account_id=buyer_account_id,
            dates=date_list,
        )

        return {
            "start_date": start_date,
            "end_date": end_date,
            "buyer_account_id": buyer_account_id,
            "dates": date_list,
        }

    return await pg_transaction_async(_run)
