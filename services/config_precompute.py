"""Pretargeting config breakdown precompute helpers.

Creates and refreshes daily config breakdown tables for fast UI queries.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = os.path.expanduser("~/.catscan/catscan.db")


def _ensure_tables(conn: sqlite3.Connection) -> None:
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
        "CREATE INDEX IF NOT EXISTS idx_cfg_size_billing ON config_size_daily(billing_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cfg_geo_date ON config_geo_daily(metric_date)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cfg_geo_billing ON config_geo_daily(billing_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cfg_pub_date ON config_publisher_daily(metric_date)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cfg_pub_billing ON config_publisher_daily(billing_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cfg_creative_date ON config_creative_daily(metric_date)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cfg_creative_billing ON config_creative_daily(billing_id)"
    )


async def refresh_config_breakdowns(
    start_date: str,
    end_date: str,
    buyer_account_id: Optional[str] = None,
    db_path: str = DB_PATH,
) -> None:
    """Refresh config breakdown tables for a date range.

    Args:
        start_date: inclusive YYYY-MM-DD
        end_date: inclusive YYYY-MM-DD
        buyer_account_id: optional seat scope
    """
    logger.info(
        "Refreshing config breakdowns for %s to %s (buyer_account_id=%s)",
        start_date,
        end_date,
        buyer_account_id,
    )
    conn = sqlite3.connect(db_path)
    try:
        _ensure_tables(conn)

        params = [start_date, end_date]
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
                WHERE metric_date BETWEEN ? AND ?{seat_clause}
                """,
                tuple(params),
            )

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
            WHERE metric_date BETWEEN ? AND ?
              AND billing_id IS NOT NULL
              AND billing_id != ''
              AND buyer_account_id IS NOT NULL
              AND buyer_account_id != ''
              AND creative_size IS NOT NULL
              AND creative_size != ''{seat_clause}
            GROUP BY metric_date, buyer_account_id, billing_id, creative_size
            """,
            tuple(params),
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
            WHERE metric_date BETWEEN ? AND ?
              AND billing_id IS NOT NULL
              AND billing_id != ''
              AND buyer_account_id IS NOT NULL
              AND buyer_account_id != ''
              AND country IS NOT NULL
              AND country != ''{seat_clause}
            GROUP BY metric_date, buyer_account_id, billing_id, country
            """,
            tuple(params),
        )

        conn.execute(
            f"""
            INSERT OR REPLACE INTO config_publisher_daily (
                metric_date, buyer_account_id, billing_id, publisher_id, publisher_name,
                reached_queries, impressions, spend_micros
            )
            SELECT
                metric_date,
                buyer_account_id,
                billing_id,
                publisher_id,
                MAX(publisher_name),
                SUM(reached_queries),
                SUM(impressions),
                SUM(spend_micros)
            FROM rtb_daily
            WHERE metric_date BETWEEN ? AND ?
              AND billing_id IS NOT NULL
              AND billing_id != ''
              AND buyer_account_id IS NOT NULL
              AND buyer_account_id != ''
              AND publisher_id IS NOT NULL
              AND publisher_id != ''{seat_clause}
            GROUP BY metric_date, buyer_account_id, billing_id, publisher_id
            """,
            tuple(params),
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
            WHERE metric_date BETWEEN ? AND ?
              AND billing_id IS NOT NULL
              AND billing_id != ''
              AND buyer_account_id IS NOT NULL
              AND buyer_account_id != ''
              AND creative_id IS NOT NULL
              AND creative_id != ''{seat_clause}
            GROUP BY metric_date, buyer_account_id, billing_id, creative_id
            """,
            tuple(params),
        )

        conn.commit()
    finally:
        conn.close()
