"""Pretargeting config breakdown precompute helpers.

Creates and refreshes daily config breakdown tables for fast UI queries.
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
            creative_size TEXT,
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
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cfg_creative_date_buyer_billing_size "
        "ON config_creative_daily(metric_date, buyer_account_id, billing_id, creative_size)"
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS fact_delivery_daily (
            metric_date DATE NOT NULL,
            buyer_account_id TEXT NOT NULL,
            billing_id TEXT NOT NULL DEFAULT '',
            country TEXT NOT NULL DEFAULT '',
            publisher_id TEXT NOT NULL DEFAULT '',
            publisher_name TEXT NOT NULL DEFAULT '',
            reached_queries BIGINT NOT NULL DEFAULT 0,
            impressions BIGINT NOT NULL DEFAULT 0,
            clicks BIGINT NOT NULL DEFAULT 0,
            spend_micros BIGINT NOT NULL DEFAULT 0,
            source_used TEXT NOT NULL,
            source_priority INTEGER NOT NULL DEFAULT 1,
            data_scope TEXT NOT NULL DEFAULT 'billing',
            confidence NUMERIC(5,4) NOT NULL DEFAULT 1.0000,
            PRIMARY KEY (
                metric_date, buyer_account_id, billing_id, country, publisher_id, source_used, data_scope
            )
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_fact_delivery_buyer_date ON fact_delivery_daily(buyer_account_id, metric_date)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_fact_delivery_billing_date ON fact_delivery_daily(billing_id, metric_date)"
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS fact_dimension_gaps_daily (
            metric_date DATE NOT NULL,
            buyer_account_id TEXT NOT NULL,
            total_rows BIGINT NOT NULL DEFAULT 0,
            missing_country_rows BIGINT NOT NULL DEFAULT 0,
            missing_publisher_rows BIGINT NOT NULL DEFAULT 0,
            missing_billing_rows BIGINT NOT NULL DEFAULT 0,
            country_missing_pct NUMERIC(5,2) NOT NULL DEFAULT 100.00,
            publisher_missing_pct NUMERIC(5,2) NOT NULL DEFAULT 100.00,
            billing_missing_pct NUMERIC(5,2) NOT NULL DEFAULT 100.00,
            availability_state TEXT NOT NULL DEFAULT 'unavailable',
            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (metric_date, buyer_account_id)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_fact_dimension_gaps_buyer_date ON fact_dimension_gaps_daily(buyer_account_id, metric_date)"
    )


def _refresh_canonical_reconciliation(
    conn,
    *,
    date_list: list[str],
    buyer_account_id: Optional[str],
) -> None:
    """Rebuild canonical delivery facts from raw + API precompute tables."""
    delete_params = [date_list]
    buyer_filter = ""
    if buyer_account_id:
        buyer_filter = " AND buyer_account_id = %s"
        delete_params.append(buyer_account_id)

    conn.execute(
        f"DELETE FROM fact_delivery_daily WHERE metric_date::text = ANY(%s){buyer_filter}",
        tuple(delete_params),
    )
    conn.execute(
        f"DELETE FROM fact_dimension_gaps_daily WHERE metric_date::text = ANY(%s){buyer_filter}",
        tuple(delete_params),
    )

    # Billing-scoped geo facts from CSV-quality data.
    insert_params = [date_list]
    if buyer_account_id:
        insert_params.append(buyer_account_id)
    conn.execute(
        f"""
        INSERT INTO fact_delivery_daily (
            metric_date, buyer_account_id, billing_id, country, publisher_id, publisher_name,
            reached_queries, impressions, clicks, spend_micros,
            source_used, source_priority, data_scope, confidence
        )
        SELECT
            metric_date,
            buyer_account_id,
            billing_id,
            country,
            '',
            '',
            SUM(reached_queries),
            SUM(impressions),
            SUM(clicks),
            SUM(spend_micros),
            'csv',
            1,
            'billing',
            1.0000
        FROM rtb_daily
        WHERE metric_date::text = ANY(%s)
          AND billing_id IS NOT NULL AND billing_id != ''
          AND buyer_account_id IS NOT NULL AND buyer_account_id != ''
          AND country IS NOT NULL AND country != ''{buyer_filter}
        GROUP BY metric_date, buyer_account_id, billing_id, country
        """,
        tuple(insert_params),
    )

    # Billing-scoped publisher facts from CSV-quality data.
    conn.execute(
        f"""
        INSERT INTO fact_delivery_daily (
            metric_date, buyer_account_id, billing_id, country, publisher_id, publisher_name,
            reached_queries, impressions, clicks, spend_micros,
            source_used, source_priority, data_scope, confidence
        )
        SELECT
            metric_date,
            buyer_account_id,
            billing_id,
            '',
            publisher_id,
            COALESCE(MAX(publisher_name), ''),
            SUM(reached_queries),
            SUM(impressions),
            SUM(clicks),
            SUM(spend_micros),
            'csv',
            1,
            'billing',
            1.0000
        FROM rtb_daily
        WHERE metric_date::text = ANY(%s)
          AND billing_id IS NOT NULL AND billing_id != ''
          AND buyer_account_id IS NOT NULL AND buyer_account_id != ''
          AND publisher_id IS NOT NULL AND publisher_id != ''{buyer_filter}
        GROUP BY metric_date, buyer_account_id, billing_id, publisher_id
        """,
        tuple(insert_params),
    )

    # Buyer-level fallback geo facts from API pipeline (no fake billing joins).
    conn.execute(
        f"""
        INSERT INTO fact_delivery_daily (
            metric_date, buyer_account_id, billing_id, country, publisher_id, publisher_name,
            reached_queries, impressions, clicks, spend_micros,
            source_used, source_priority, data_scope, confidence
        )
        SELECT
            g.metric_date,
            g.buyer_account_id,
            '',
            g.country,
            '',
            '',
            SUM(g.reached_queries),
            SUM(g.impressions),
            0,
            0,
            'api',
            2,
            'buyer_fallback',
            0.6000
        FROM rtb_geo_daily g
        WHERE g.metric_date::text = ANY(%s)
          AND g.country IS NOT NULL AND g.country != ''{buyer_filter}
          AND NOT EXISTS (
              SELECT 1
              FROM fact_delivery_daily f
              WHERE f.metric_date = g.metric_date
                AND f.buyer_account_id = g.buyer_account_id
                AND f.country != ''
                AND f.data_scope = 'billing'
          )
        GROUP BY g.metric_date, g.buyer_account_id, g.country
        """,
        tuple(insert_params),
    )

    # Buyer-level fallback publisher facts from API pipeline.
    conn.execute(
        f"""
        INSERT INTO fact_delivery_daily (
            metric_date, buyer_account_id, billing_id, country, publisher_id, publisher_name,
            reached_queries, impressions, clicks, spend_micros,
            source_used, source_priority, data_scope, confidence
        )
        SELECT
            p.metric_date,
            p.buyer_account_id,
            '',
            '',
            p.publisher_id,
            COALESCE(MAX(p.publisher_name), ''),
            SUM(p.reached_queries),
            SUM(p.impressions),
            0,
            0,
            'api',
            2,
            'buyer_fallback',
            0.6000
        FROM rtb_publisher_daily p
        WHERE p.metric_date::text = ANY(%s)
          AND p.publisher_id IS NOT NULL AND p.publisher_id != ''{buyer_filter}
          AND NOT EXISTS (
              SELECT 1
              FROM fact_delivery_daily f
              WHERE f.metric_date = p.metric_date
                AND f.buyer_account_id = p.buyer_account_id
                AND f.publisher_id != ''
                AND f.data_scope = 'billing'
          )
        GROUP BY p.metric_date, p.buyer_account_id, p.publisher_id
        """,
        tuple(insert_params),
    )

    # Daily dimension gap summary from CSV stream.
    conn.execute(
        f"""
        INSERT INTO fact_dimension_gaps_daily (
            metric_date, buyer_account_id,
            total_rows, missing_country_rows, missing_publisher_rows, missing_billing_rows,
            country_missing_pct, publisher_missing_pct, billing_missing_pct,
            availability_state, updated_at
        )
        SELECT
            metric_date,
            buyer_account_id,
            COUNT(*) AS total_rows,
            SUM(CASE WHEN country IS NULL OR country = '' THEN 1 ELSE 0 END) AS missing_country_rows,
            SUM(CASE WHEN publisher_id IS NULL OR publisher_id = '' THEN 1 ELSE 0 END) AS missing_publisher_rows,
            SUM(CASE WHEN billing_id IS NULL OR billing_id = '' THEN 1 ELSE 0 END) AS missing_billing_rows,
            CASE WHEN COUNT(*) = 0 THEN 100.00 ELSE ROUND(SUM(CASE WHEN country IS NULL OR country = '' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) END AS country_missing_pct,
            CASE WHEN COUNT(*) = 0 THEN 100.00 ELSE ROUND(SUM(CASE WHEN publisher_id IS NULL OR publisher_id = '' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) END AS publisher_missing_pct,
            CASE WHEN COUNT(*) = 0 THEN 100.00 ELSE ROUND(SUM(CASE WHEN billing_id IS NULL OR billing_id = '' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) END AS billing_missing_pct,
            CASE
                WHEN COUNT(*) = 0 THEN 'unavailable'
                WHEN ROUND(SUM(CASE WHEN country IS NULL OR country = '' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) > 50
                  OR ROUND(SUM(CASE WHEN publisher_id IS NULL OR publisher_id = '' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) > 50
                THEN 'degraded'
                ELSE 'healthy'
            END AS availability_state,
            CURRENT_TIMESTAMP
        FROM rtb_daily
        WHERE metric_date::text = ANY(%s)
          AND buyer_account_id IS NOT NULL AND buyer_account_id != ''{buyer_filter}
        GROUP BY metric_date, buyer_account_id
        """,
        tuple(insert_params),
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
    run_id = str(uuid.uuid4())
    run_started_at = datetime.utcnow().isoformat()

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
             -- Join safety: keep seat identity in the join so publisher attribution
             -- never crosses buyer seats when dimension values overlap.
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
                ANY_VALUE(creative_size) AS creative_size,
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

        # Postgres fallback: fill config_publisher_daily from local rtb_daily
        # rows where BOTH billing_id and publisher_id are present on the same
        # row.  ON CONFLICT DO NOTHING ensures BQ-sourced data takes priority.
        fallback_params: list = [date_list]
        fallback_buyer = ""
        if buyer_account_id:
            fallback_buyer = " AND buyer_account_id = %s"
            fallback_params.append(buyer_account_id)
        conn.execute(
            f"""
            INSERT INTO config_publisher_daily
                (metric_date, buyer_account_id, billing_id, publisher_id,
                 publisher_name, reached_queries, impressions, spend_micros)
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
            WHERE metric_date::text = ANY(%s)
              AND billing_id IS NOT NULL AND billing_id != ''
              AND publisher_id IS NOT NULL AND publisher_id != ''
              AND buyer_account_id IS NOT NULL AND buyer_account_id != ''{fallback_buyer}
            GROUP BY metric_date, buyer_account_id, billing_id, publisher_id
            ON CONFLICT (metric_date, buyer_account_id, billing_id, publisher_id)
                DO NOTHING
            """,
            tuple(fallback_params),
        )

        execute_many(
            conn,
            sql=(
                "INSERT INTO config_creative_daily "
                "(metric_date, buyer_account_id, billing_id, creative_id, creative_size, "
                "reached_queries, impressions, spend_micros) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
            ),
            rows=[
                (
                    _format_date(row.metric_date),
                    row.buyer_account_id,
                    row.billing_id,
                    row.creative_id,
                    row.creative_size,
                    row.reached_queries,
                    row.impressions,
                    row.spend_micros,
                )
                for row in creative_rows
            ],
        )

        _refresh_canonical_reconciliation(
            conn,
            date_list=date_list,
            buyer_account_id=buyer_account_id,
        )

        record_refresh_log_postgres(
            conn,
            cache_name="config_breakdowns",
            buyer_account_id=buyer_account_id,
            dates=date_list,
        )

        return {
            "row_counts": {
                "config_size_daily": len(size_rows),
                "config_geo_daily": len(geo_rows),
                "config_publisher_daily": len(publisher_rows),
                "config_creative_daily": len(creative_rows),
            }
        }

    async def _record_run_rows(status: str, row_counts: dict[str, int], error_text: Optional[str]) -> None:
        def _write(conn):
            for table_name, row_count in row_counts.items():
                record_refresh_run_postgres(
                    conn,
                    run_id=run_id,
                    cache_name="config_breakdowns",
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
                "Failed to write precompute_refresh_runs rows for run_id=%s cache=config_breakdowns",
                run_id,
            )

    try:
        run_meta = await pg_transaction_async(_run)
    except Exception as exc:
        await _record_run_rows(status="failed", row_counts={"__all__": 0}, error_text=str(exc))
        raise

    row_counts = (run_meta or {}).get("row_counts", {})
    await _record_run_rows(status="success", row_counts=row_counts, error_text=None)

    # Return monitoring data for scheduled refresh
    return {
        "start_date": refresh_start,
        "end_date": refresh_end,
        "buyer_account_id": buyer_account_id,
        "dates": date_list,
        "refresh_run_id": run_id,
    }
