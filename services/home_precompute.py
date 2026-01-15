"""Home page precompute helpers.

Creates and refreshes daily summary tables for fast Home page queries.
"""

from __future__ import annotations

import logging
from typing import Optional

from storage.database import db_transaction_async

logger = logging.getLogger(__name__)


HOME_TABLES_SQL = [
    """
    CREATE TABLE IF NOT EXISTS home_seat_daily (
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
    CREATE TABLE IF NOT EXISTS home_publisher_daily (
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
    CREATE TABLE IF NOT EXISTS home_geo_daily (
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
    CREATE TABLE IF NOT EXISTS home_config_daily (
        metric_date TEXT NOT NULL,
        buyer_account_id TEXT NOT NULL,
        billing_id TEXT NOT NULL,
        reached_queries INTEGER DEFAULT 0,
        impressions INTEGER DEFAULT 0,
        bids_in_auction INTEGER DEFAULT 0,
        auctions_won INTEGER DEFAULT 0,
        PRIMARY KEY (metric_date, buyer_account_id, billing_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS home_size_daily (
        metric_date TEXT NOT NULL,
        buyer_account_id TEXT NOT NULL,
        creative_size TEXT NOT NULL,
        reached_queries INTEGER DEFAULT 0,
        impressions INTEGER DEFAULT 0,
        PRIMARY KEY (metric_date, buyer_account_id, creative_size)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_home_seat_date ON home_seat_daily(metric_date)",
    "CREATE INDEX IF NOT EXISTS idx_home_pub_date ON home_publisher_daily(metric_date)",
    "CREATE INDEX IF NOT EXISTS idx_home_geo_date ON home_geo_daily(metric_date)",
    "CREATE INDEX IF NOT EXISTS idx_home_config_date ON home_config_daily(metric_date)",
    "CREATE INDEX IF NOT EXISTS idx_home_size_date ON home_size_daily(metric_date)",
]


async def refresh_home_summaries(
    start_date: str,
    end_date: str,
    buyer_account_id: Optional[str] = None,
) -> dict:
    """Refresh Home page summary tables for a date range.

    Args:
        start_date: YYYY-MM-DD
        end_date: YYYY-MM-DD
        buyer_account_id: Optional seat ID to scope refresh.
    """
    logger.info(
        "Refreshing home summaries for %s to %s (buyer_account_id=%s)",
        start_date,
        end_date,
        buyer_account_id,
    )

    def _run(conn):
        for stmt in HOME_TABLES_SQL:
            conn.execute(stmt)

        params = [start_date, end_date]
        buyer_filter = ""
        if buyer_account_id:
            buyer_filter = " AND buyer_account_id = ?"
            params.append(buyer_account_id)

        conn.execute(
            f"""
            DELETE FROM home_seat_daily
            WHERE metric_date BETWEEN ? AND ?{buyer_filter}
            """,
            tuple(params),
        )
        conn.execute(
            f"""
            DELETE FROM home_publisher_daily
            WHERE metric_date BETWEEN ? AND ?{buyer_filter}
            """,
            tuple(params),
        )
        conn.execute(
            f"""
            DELETE FROM home_geo_daily
            WHERE metric_date BETWEEN ? AND ?{buyer_filter}
            """,
            tuple(params),
        )
        conn.execute(
            f"""
            DELETE FROM home_config_daily
            WHERE metric_date BETWEEN ? AND ?{buyer_filter}
            """,
            tuple(params),
        )
        conn.execute(
            f"""
            DELETE FROM home_size_daily
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
            INSERT OR REPLACE INTO home_seat_daily (
                metric_date, buyer_account_id, reached_queries, impressions, bids,
                successful_responses, bid_requests, auctions_won
            )
            SELECT
                metric_date,
                buyer_account_id,
                SUM(reached_queries),
                SUM(impressions),
                SUM(bids),
                SUM(successful_responses),
                SUM(bid_requests),
                SUM(auctions_won)
            FROM rtb_bidstream
            WHERE metric_date BETWEEN ? AND ?
              AND buyer_account_id IS NOT NULL
              AND buyer_account_id != ''{seat_filter}
            GROUP BY metric_date, buyer_account_id
            """,
            tuple(seat_params),
        )

        conn.execute(
            f"""
            INSERT OR REPLACE INTO home_publisher_daily (
                metric_date, buyer_account_id, publisher_id, publisher_name,
                reached_queries, impressions, bids, successful_responses,
                bid_requests, auctions_won
            )
            SELECT
                metric_date,
                buyer_account_id,
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
              AND buyer_account_id IS NOT NULL
              AND buyer_account_id != ''
              AND publisher_id IS NOT NULL
              AND publisher_id != ''{seat_filter}
            GROUP BY metric_date, buyer_account_id, publisher_id
            """,
            tuple(seat_params),
        )

        conn.execute(
            f"""
            INSERT OR REPLACE INTO home_geo_daily (
                metric_date, buyer_account_id, country,
                reached_queries, impressions, bids, successful_responses,
                bid_requests, auctions_won
            )
            SELECT
                metric_date,
                buyer_account_id,
                country,
                SUM(reached_queries),
                SUM(impressions),
                SUM(bids),
                SUM(successful_responses),
                SUM(bid_requests),
                SUM(auctions_won)
            FROM rtb_bidstream
            WHERE metric_date BETWEEN ? AND ?
              AND buyer_account_id IS NOT NULL
              AND buyer_account_id != ''
              AND country IS NOT NULL
              AND country != ''{seat_filter}
            GROUP BY metric_date, buyer_account_id, country
            """,
            tuple(seat_params),
        )

        conn.execute(
            f"""
            INSERT OR REPLACE INTO home_config_daily (
                metric_date, buyer_account_id, billing_id,
                reached_queries, impressions, bids_in_auction, auctions_won
            )
            SELECT
                metric_date,
                buyer_account_id,
                billing_id,
                SUM(reached_queries),
                SUM(impressions),
                SUM(bids_in_auction),
                SUM(auctions_won)
            FROM rtb_daily
            WHERE metric_date BETWEEN ? AND ?
              AND buyer_account_id IS NOT NULL
              AND buyer_account_id != ''
              AND billing_id IS NOT NULL
              AND billing_id != ''{seat_filter}
            GROUP BY metric_date, buyer_account_id, billing_id
            """,
            tuple(seat_params),
        )

        conn.execute(
            f"""
            INSERT OR REPLACE INTO home_size_daily (
                metric_date, buyer_account_id, creative_size,
                reached_queries, impressions
            )
            SELECT
                metric_date,
                buyer_account_id,
                creative_size,
                SUM(reached_queries),
                SUM(impressions)
            FROM rtb_daily
            WHERE metric_date BETWEEN ? AND ?
              AND buyer_account_id IS NOT NULL
              AND buyer_account_id != ''
              AND creative_size IS NOT NULL
              AND creative_size != ''{seat_filter}
            GROUP BY metric_date, buyer_account_id, creative_size
            """,
            tuple(seat_params),
        )

        return {
            "start_date": start_date,
            "end_date": end_date,
            "buyer_account_id": buyer_account_id,
        }

    return await db_transaction_async(_run)
