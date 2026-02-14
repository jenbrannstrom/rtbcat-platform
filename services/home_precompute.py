"""Home page precompute helpers.

Creates and refreshes daily summary tables for fast Home page queries.
"""

from __future__ import annotations

import logging
from datetime import datetime
import uuid
from typing import Optional, Sequence

from google.cloud import bigquery

from services.precompute_utils import (
    normalize_refresh_dates,
    record_refresh_log_postgres,
    record_refresh_run_postgres,
    refresh_window,
)
from storage.bigquery import build_table_ref, coerce_dates, get_bigquery_client, run_query
from storage.postgres import execute_many, pg_transaction_async

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
    "CREATE INDEX IF NOT EXISTS idx_home_seat_date_buyer ON home_seat_daily(metric_date, buyer_account_id)",
    "CREATE INDEX IF NOT EXISTS idx_home_pub_date ON home_publisher_daily(metric_date)",
    "CREATE INDEX IF NOT EXISTS idx_home_pub_date_buyer_pub ON home_publisher_daily(metric_date, buyer_account_id, publisher_id)",
    "CREATE INDEX IF NOT EXISTS idx_home_geo_date ON home_geo_daily(metric_date)",
    "CREATE INDEX IF NOT EXISTS idx_home_geo_date_buyer_country ON home_geo_daily(metric_date, buyer_account_id, country)",
    "CREATE INDEX IF NOT EXISTS idx_home_config_date ON home_config_daily(metric_date)",
    "CREATE INDEX IF NOT EXISTS idx_home_config_date_buyer_billing ON home_config_daily(metric_date, buyer_account_id, billing_id)",
    "CREATE INDEX IF NOT EXISTS idx_home_size_date ON home_size_daily(metric_date)",
    "CREATE INDEX IF NOT EXISTS idx_home_size_date_buyer_size ON home_size_daily(metric_date, buyer_account_id, creative_size)",
]


async def refresh_home_summaries(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    buyer_account_id: Optional[str] = None,
    dates: Optional[Sequence[str]] = None,
    days: Optional[int] = None,
) -> dict:
    """Refresh Home page summary tables for a date range.

    Args:
        start_date: YYYY-MM-DD
        end_date: YYYY-MM-DD
        buyer_account_id: Optional seat ID to scope refresh.
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
        "Refreshing home summaries for %s to %s (buyer_account_id=%s)",
        refresh_start,
        refresh_end,
        buyer_account_id,
    )
    run_id = str(uuid.uuid4())
    run_started_at = datetime.utcnow().isoformat()
    client = get_bigquery_client()
    bidstream_table = build_table_ref(
        client, table_env="BIGQUERY_RTB_BIDSTREAM_TABLE", default_table="rtb_bidstream"
    )
    rtb_daily_table = build_table_ref(
        client, table_env="BIGQUERY_RTB_DAILY_TABLE", default_table="rtb_daily"
    )
    dates_param = coerce_dates(date_list)
    buyer_clause = " AND buyer_account_id = @buyer_account_id" if buyer_account_id else ""

    seat_rows = run_query(
        client,
        sql=f"""
            SELECT
                metric_date,
                buyer_account_id,
                SUM(reached_queries) AS reached_queries,
                SUM(impressions) AS impressions,
                SUM(bids) AS bids,
                SUM(successful_responses) AS successful_responses,
                SUM(bid_requests) AS bid_requests,
                SUM(auctions_won) AS auctions_won
            FROM `{bidstream_table}`
            WHERE metric_date IN UNNEST(@dates)
              AND buyer_account_id IS NOT NULL
              AND buyer_account_id != ''{buyer_clause}
            GROUP BY metric_date, buyer_account_id
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
                metric_date,
                buyer_account_id,
                publisher_id,
                MAX(publisher_name) AS publisher_name,
                SUM(reached_queries) AS reached_queries,
                SUM(impressions) AS impressions,
                SUM(bids) AS bids,
                SUM(successful_responses) AS successful_responses,
                SUM(bid_requests) AS bid_requests,
                SUM(auctions_won) AS auctions_won
            FROM `{bidstream_table}`
            WHERE metric_date IN UNNEST(@dates)
              AND buyer_account_id IS NOT NULL
              AND buyer_account_id != ''
              AND publisher_id IS NOT NULL
              AND publisher_id != ''{buyer_clause}
            GROUP BY metric_date, buyer_account_id, publisher_id
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
                country,
                SUM(reached_queries) AS reached_queries,
                SUM(impressions) AS impressions,
                SUM(bids) AS bids,
                SUM(successful_responses) AS successful_responses,
                SUM(bid_requests) AS bid_requests,
                SUM(auctions_won) AS auctions_won
            FROM `{bidstream_table}`
            WHERE metric_date IN UNNEST(@dates)
              AND buyer_account_id IS NOT NULL
              AND buyer_account_id != ''
              AND country IS NOT NULL
              AND country != ''{buyer_clause}
            GROUP BY metric_date, buyer_account_id, country
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
    config_rows = run_query(
        client,
        sql=f"""
            SELECT
                metric_date,
                buyer_account_id,
                billing_id,
                SUM(reached_queries) AS reached_queries,
                SUM(impressions) AS impressions,
                SUM(bids_in_auction) AS bids_in_auction,
                SUM(auctions_won) AS auctions_won
            FROM `{rtb_daily_table}`
            WHERE metric_date IN UNNEST(@dates)
              AND buyer_account_id IS NOT NULL
              AND buyer_account_id != ''
              AND billing_id IS NOT NULL
              AND billing_id != ''{buyer_clause}
            GROUP BY metric_date, buyer_account_id, billing_id
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
    size_rows = run_query(
        client,
        sql=f"""
            SELECT
                metric_date,
                buyer_account_id,
                creative_size,
                SUM(reached_queries) AS reached_queries,
                SUM(impressions) AS impressions
            FROM `{rtb_daily_table}`
            WHERE metric_date IN UNNEST(@dates)
              AND buyer_account_id IS NOT NULL
              AND buyer_account_id != ''
              AND creative_size IS NOT NULL
              AND creative_size != ''{buyer_clause}
            GROUP BY metric_date, buyer_account_id, creative_size
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
        for stmt in HOME_TABLES_SQL:
            conn.execute(stmt)

        delete_params = [date_list]
        buyer_filter = ""
        if buyer_account_id:
            buyer_filter = " AND buyer_account_id = %s"
            delete_params.append(buyer_account_id)

        for table in (
            "home_seat_daily",
            "home_publisher_daily",
            "home_geo_daily",
            "home_config_daily",
            "home_size_daily",
        ):
            conn.execute(
                f"DELETE FROM {table} WHERE metric_date = ANY(%s){buyer_filter}",
                tuple(delete_params),
            )

        execute_many(
            conn,
            sql=(
                "INSERT INTO home_seat_daily "
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
                for row in seat_rows
            ],
        )
        execute_many(
            conn,
            sql=(
                "INSERT INTO home_publisher_daily "
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
                "INSERT INTO home_geo_daily "
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
                "INSERT INTO home_config_daily "
                "(metric_date, buyer_account_id, billing_id, reached_queries, impressions, "
                "bids_in_auction, auctions_won) VALUES (%s, %s, %s, %s, %s, %s, %s)"
            ),
            rows=[
                (
                    _format_date(row.metric_date),
                    row.buyer_account_id,
                    row.billing_id,
                    row.reached_queries,
                    row.impressions,
                    row.bids_in_auction,
                    row.auctions_won,
                )
                for row in config_rows
            ],
        )

        # Gap-fill: ensure every ACTIVE config from active buyers has at least
        # a zero-row in home_config_daily for each date in the refresh window.
        # ON CONFLICT DO NOTHING preserves real traffic data from BQ.
        gap_fill_params: list = [date_list]
        gap_fill_buyer = ""
        if buyer_account_id:
            gap_fill_buyer = " AND pc.bidder_id = %s"
            gap_fill_params.append(buyer_account_id)
        conn.execute(
            f"""
            INSERT INTO home_config_daily
                (metric_date, buyer_account_id, billing_id,
                 reached_queries, impressions, bids_in_auction, auctions_won)
            SELECT d::date, pc.bidder_id, pc.billing_id, 0, 0, 0, 0
            FROM pretargeting_configs pc
            JOIN buyer_seats bs ON bs.bidder_id = pc.bidder_id AND bs.active = true
            CROSS JOIN UNNEST(%s::text[]) AS d
            WHERE pc.state = 'ACTIVE'
              AND pc.billing_id IS NOT NULL
              AND pc.billing_id != ''{gap_fill_buyer}
            ON CONFLICT (metric_date, buyer_account_id, billing_id) DO NOTHING
            """,
            tuple(gap_fill_params),
        )

        execute_many(
            conn,
            sql=(
                "INSERT INTO home_size_daily "
                "(metric_date, buyer_account_id, creative_size, reached_queries, impressions) "
                "VALUES (%s, %s, %s, %s, %s)"
            ),
            rows=[
                (
                    _format_date(row.metric_date),
                    row.buyer_account_id,
                    row.creative_size,
                    row.reached_queries,
                    row.impressions,
                )
                for row in size_rows
            ],
        )

        record_refresh_log_postgres(
            conn,
            cache_name="home_summaries",
            buyer_account_id=buyer_account_id,
            dates=date_list,
        )

        return {
            "start_date": refresh_start,
            "end_date": refresh_end,
            "buyer_account_id": buyer_account_id,
            "dates": date_list,
            "row_counts": {
                "home_seat_daily": len(seat_rows),
                "home_publisher_daily": len(publisher_rows),
                "home_geo_daily": len(geo_rows),
                "home_config_daily": len(config_rows) + len(gap_fill_params),
                "home_size_daily": len(size_rows),
            },
        }

    async def _record_run_rows(status: str, row_counts: dict[str, int], error_text: Optional[str]) -> None:
        def _write(conn):
            for table_name, row_count in row_counts.items():
                record_refresh_run_postgres(
                    conn,
                    run_id=run_id,
                    cache_name="home_summaries",
                    table_name=table_name,
                    buyer_account_id=buyer_account_id,
                    dates=date_list,
                    status=status,
                    row_count=row_count,
                    error_text=error_text,
                    started_at=run_started_at,
                    finished_at=datetime.utcnow().isoformat(),
                )

        try:
            await pg_transaction_async(_write)
        except Exception:
            logger.exception(
                "Failed to write precompute_refresh_runs rows for run_id=%s cache=home_summaries",
                run_id,
            )

    try:
        result = await pg_transaction_async(_run)
    except Exception as exc:
        await _record_run_rows(status="failed", row_counts={"__all__": 0}, error_text=str(exc))
        raise

    row_counts = result.pop("row_counts", {})
    await _record_run_rows(status="success", row_counts=row_counts, error_text=None)
    result["refresh_run_id"] = run_id
    return result
