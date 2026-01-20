"""RTB funnel + drilldown precompute helpers.

Creates and refreshes daily summary tables for RTB analytics endpoints.
"""

from __future__ import annotations

import logging
from typing import Optional

from storage.database import db_transaction_async

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
    logger.info(
        "Refreshing RTB summaries for %s to %s (buyer_account_id=%s)",
        start_date,
        end_date,
        buyer_account_id,
    )

    def _run(conn):
        for stmt in RTB_TABLES_SQL:
            conn.execute(stmt)

        params = [start_date, end_date]
        buyer_filter = ""
        if buyer_account_id:
            buyer_filter = " AND buyer_account_id = ?"
            params.append(buyer_account_id)

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
                f"""
                DELETE FROM {table}
                WHERE metric_date BETWEEN ? AND ?{buyer_filter}
                """,
                tuple(params),
            )

        seat_params = [start_date, end_date]
        seat_filter = ""
        if buyer_account_id:
            seat_filter = " AND buyer_account_id = ?"
            seat_params.append(buyer_account_id)

        conn.execute(
            f"""
            INSERT OR REPLACE INTO rtb_funnel_daily (
                metric_date, buyer_account_id, reached_queries, impressions, bids,
                successful_responses, bid_requests, auctions_won
            )
            SELECT
                metric_date,
                COALESCE(buyer_account_id, ''),
                SUM(reached_queries),
                SUM(impressions),
                SUM(bids),
                SUM(successful_responses),
                SUM(bid_requests),
                SUM(auctions_won)
            FROM rtb_bidstream
            WHERE metric_date BETWEEN ? AND ?{seat_filter}
            GROUP BY metric_date, COALESCE(buyer_account_id, '')
            """,
            tuple(seat_params),
        )

        conn.execute(
            f"""
            INSERT OR REPLACE INTO rtb_publisher_daily (
                metric_date, buyer_account_id, publisher_id, publisher_name,
                reached_queries, impressions, bids, successful_responses,
                bid_requests, auctions_won
            )
            SELECT
                metric_date,
                COALESCE(buyer_account_id, ''),
                publisher_id,
                MAX(publisher_name),
                SUM(reached_queries),
                SUM(impressions),
                SUM(bids),
                SUM(successful_responses),
                SUM(bid_requests),
                SUM(auctions_won)
            FROM rtb_bidstream
            WHERE metric_date BETWEEN ? AND ?
              AND publisher_id IS NOT NULL
              AND publisher_id != ''{seat_filter}
            GROUP BY metric_date, COALESCE(buyer_account_id, ''), publisher_id
            """,
            tuple(seat_params),
        )

        conn.execute(
            f"""
            INSERT OR REPLACE INTO rtb_geo_daily (
                metric_date, buyer_account_id, country,
                reached_queries, impressions, bids, successful_responses,
                bid_requests, auctions_won
            )
            SELECT
                metric_date,
                COALESCE(buyer_account_id, ''),
                country,
                SUM(reached_queries),
                SUM(impressions),
                SUM(bids),
                SUM(successful_responses),
                SUM(bid_requests),
                SUM(auctions_won)
            FROM rtb_bidstream
            WHERE metric_date BETWEEN ? AND ?
              AND country IS NOT NULL
              AND country != ''{seat_filter}
            GROUP BY metric_date, COALESCE(buyer_account_id, ''), country
            """,
            tuple(seat_params),
        )

        conn.execute(
            f"""
            INSERT OR REPLACE INTO rtb_app_daily (
                metric_date, buyer_account_id, app_name, app_id, billing_id,
                reached_queries, impressions, clicks, spend_micros
            )
            SELECT
                metric_date,
                COALESCE(buyer_account_id, ''),
                app_name,
                MAX(app_id),
                COALESCE(billing_id, ''),
                SUM(reached_queries),
                SUM(impressions),
                SUM(clicks),
                SUM(spend_micros)
            FROM rtb_daily
            WHERE metric_date BETWEEN ? AND ?
              AND app_name IS NOT NULL
              AND app_name != ''{seat_filter}
            GROUP BY metric_date, COALESCE(buyer_account_id, ''), app_name, COALESCE(billing_id, '')
            """,
            tuple(seat_params),
        )

        conn.execute(
            f"""
            INSERT OR REPLACE INTO rtb_app_size_daily (
                metric_date, buyer_account_id, app_name, app_id, billing_id,
                creative_size, creative_format, reached_queries, impressions,
                clicks, spend_micros
            )
            SELECT
                metric_date,
                COALESCE(buyer_account_id, ''),
                app_name,
                MAX(app_id),
                COALESCE(billing_id, ''),
                creative_size,
                creative_format,
                SUM(reached_queries),
                SUM(impressions),
                SUM(clicks),
                SUM(spend_micros)
            FROM rtb_daily
            WHERE metric_date BETWEEN ? AND ?
              AND app_name IS NOT NULL
              AND app_name != ''
              AND creative_size IS NOT NULL
              AND creative_size != ''{seat_filter}
            GROUP BY metric_date, COALESCE(buyer_account_id, ''), app_name, COALESCE(billing_id, ''),
                     creative_size, creative_format
            """,
            tuple(seat_params),
        )

        conn.execute(
            f"""
            INSERT OR REPLACE INTO rtb_app_country_daily (
                metric_date, buyer_account_id, app_name, app_id, billing_id,
                country, reached_queries, impressions, clicks, spend_micros
            )
            SELECT
                metric_date,
                COALESCE(buyer_account_id, ''),
                app_name,
                MAX(app_id),
                COALESCE(billing_id, ''),
                country,
                SUM(reached_queries),
                SUM(impressions),
                SUM(clicks),
                SUM(spend_micros)
            FROM rtb_daily
            WHERE metric_date BETWEEN ? AND ?
              AND app_name IS NOT NULL
              AND app_name != ''
              AND country IS NOT NULL
              AND country != ''{seat_filter}
            GROUP BY metric_date, COALESCE(buyer_account_id, ''), app_name, COALESCE(billing_id, ''), country
            """,
            tuple(seat_params),
        )

        conn.execute(
            f"""
            INSERT OR REPLACE INTO rtb_app_creative_daily (
                metric_date, buyer_account_id, app_name, app_id, billing_id,
                creative_id, creative_size, creative_format, reached_queries,
                impressions, clicks, spend_micros
            )
            SELECT
                metric_date,
                COALESCE(buyer_account_id, ''),
                app_name,
                MAX(app_id),
                COALESCE(billing_id, ''),
                creative_id,
                creative_size,
                creative_format,
                SUM(reached_queries),
                SUM(impressions),
                SUM(clicks),
                SUM(spend_micros)
            FROM rtb_daily
            WHERE metric_date BETWEEN ? AND ?
              AND app_name IS NOT NULL
              AND app_name != ''
              AND creative_id IS NOT NULL
              AND creative_id != ''{seat_filter}
            GROUP BY metric_date, COALESCE(buyer_account_id, ''), app_name, COALESCE(billing_id, ''),
                     creative_id, creative_size, creative_format
            """,
            tuple(seat_params),
        )

        return {
            "start_date": start_date,
            "end_date": end_date,
            "buyer_account_id": buyer_account_id,
        }

    return await db_transaction_async(_run)
