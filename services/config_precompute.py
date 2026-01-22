"""Pretargeting config breakdown precompute helpers.

Creates and refreshes daily config breakdown tables for fast UI queries.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from typing import Optional, Sequence

from services.precompute_utils import (
    normalize_refresh_dates,
    record_refresh_log,
    refresh_window,
)

from storage.database import db_transaction_async

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

    def _run(conn):
        _ensure_tables(conn)

        date_placeholders = ",".join("?" * len(date_list))
        date_clause = f"metric_date IN ({date_placeholders})"
        date_clause_q = f"q.metric_date IN ({date_placeholders})"

        params = list(date_list)
        seat_clause = ""
        if buyer_account_id:
            seat_clause = " AND buyer_account_id = ?"
            params.append(buyer_account_id)

        for table in (
            "config_size_daily",
            "config_geo_daily",
            "config_publisher_daily",
            "config_creative_daily",
        ):
            conn.execute(
                f"""
                DELETE FROM {table}
                WHERE {date_clause}{seat_clause}
                """,
                tuple(params),
            )

        buyer_clause = ""
        buyer_clause_q = ""
        query_params = list(date_list)
        query_params_q = list(date_list)
        if buyer_account_id:
            buyer_clause = " AND buyer_account_id = ?"
            buyer_clause_q = " AND q.buyer_account_id = ?"
            query_params.append(buyer_account_id)
            query_params_q.append(buyer_account_id)

        conn.execute(
            f"""
            INSERT OR REPLACE INTO config_size_daily (
                metric_date, buyer_account_id, billing_id, creative_size,
                reached_queries, impressions, spend_micros
            )
            SELECT
                metric_date,
                buyer_account_id,
                billing_id,
                creative_size,
                SUM(reached_queries),
                SUM(impressions),
                SUM(spend_micros)
            FROM rtb_daily
            WHERE {date_clause}
              AND billing_id IS NOT NULL
              AND billing_id != ''
              AND buyer_account_id IS NOT NULL
              AND buyer_account_id != ''
              AND creative_size IS NOT NULL
              AND creative_size != ''{buyer_clause}
            GROUP BY metric_date, buyer_account_id, billing_id, creative_size
            """,
            tuple(query_params),
        )

        conn.execute(
            f"""
            INSERT OR REPLACE INTO config_geo_daily (
                metric_date, buyer_account_id, billing_id, country,
                reached_queries, impressions, spend_micros
            )
            SELECT
                metric_date,
                buyer_account_id,
                billing_id,
                country,
                SUM(reached_queries),
                SUM(impressions),
                SUM(spend_micros)
            FROM rtb_daily
            WHERE {date_clause}
              AND billing_id IS NOT NULL
              AND billing_id != ''
              AND buyer_account_id IS NOT NULL
              AND buyer_account_id != ''
              AND country IS NOT NULL
              AND country != ''{buyer_clause}
            GROUP BY metric_date, buyer_account_id, billing_id, country
            """,
            tuple(query_params),
        )

        conn.execute(
            f"""
            INSERT OR REPLACE INTO config_publisher_daily (
                metric_date, buyer_account_id, billing_id, publisher_id, publisher_name,
                reached_queries, impressions, spend_micros
            )
            SELECT
                q.metric_date,
                q.buyer_account_id,
                q.billing_id,
                b.publisher_id,
                MAX(b.publisher_name),
                SUM(q.reached_queries),
                SUM(q.impressions),
                SUM(q.spend_micros)
            FROM rtb_daily q
            JOIN rtb_daily b
              ON q.metric_date = b.metric_date
             AND q.hour = b.hour
             AND q.creative_id = b.creative_id
             AND q.buyer_account_id = b.buyer_account_id
             AND q.country = b.country
            WHERE {date_clause_q}
              AND q.billing_id IS NOT NULL
              AND q.billing_id != ''
              AND q.buyer_account_id IS NOT NULL
              AND q.buyer_account_id != ''
              AND b.publisher_id IS NOT NULL
              AND b.publisher_id != ''{buyer_clause_q}
            GROUP BY q.metric_date, q.buyer_account_id, q.billing_id, b.publisher_id
            """,
            tuple(query_params_q),
        )

        conn.execute(
            f"""
            INSERT OR REPLACE INTO config_creative_daily (
                metric_date, buyer_account_id, billing_id, creative_id,
                reached_queries, impressions, spend_micros
            )
            SELECT
                metric_date,
                buyer_account_id,
                billing_id,
                creative_id,
                SUM(reached_queries),
                SUM(impressions),
                SUM(spend_micros)
            FROM rtb_daily
            WHERE {date_clause}
              AND billing_id IS NOT NULL
              AND billing_id != ''
              AND buyer_account_id IS NOT NULL
              AND buyer_account_id != ''
              AND creative_id IS NOT NULL
              AND creative_id != ''{buyer_clause}
            GROUP BY metric_date, buyer_account_id, billing_id, creative_id
            """,
            tuple(query_params),
        )

        record_refresh_log(
            conn,
            cache_name="config_breakdowns",
            buyer_account_id=buyer_account_id,
            dates=date_list,
        )

        return {
            "start_date": refresh_start,
            "end_date": refresh_end,
            "buyer_account_id": buyer_account_id,
            "dates": date_list,
        }

    return await db_transaction_async(_run)
