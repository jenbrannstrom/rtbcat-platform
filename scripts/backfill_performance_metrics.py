#!/usr/bin/env python3
"""Backfill performance_metrics from rtb_daily in an idempotent way."""

from __future__ import annotations

import argparse
import os
from datetime import date, timedelta

import psycopg
from psycopg.rows import dict_row


def get_conn() -> psycopg.Connection:
    dsn = (
        os.getenv("POSTGRES_DSN")
        or os.getenv("POSTGRES_SERVING_DSN")
        or os.getenv("DATABASE_URL")
        or ""
    )
    if not dsn:
        raise RuntimeError("Set POSTGRES_DSN, POSTGRES_SERVING_DSN, or DATABASE_URL")
    return psycopg.connect(dsn, row_factory=dict_row)


def ensure_performance_metrics_table(conn: psycopg.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS performance_metrics (
            id SERIAL PRIMARY KEY,
            creative_id TEXT NOT NULL,
            campaign_id TEXT,
            metric_date DATE NOT NULL,
            impressions INTEGER NOT NULL DEFAULT 0,
            clicks INTEGER NOT NULL DEFAULT 0,
            spend_micros BIGINT NOT NULL DEFAULT 0,
            cpm_micros INTEGER,
            cpc_micros INTEGER,
            geography TEXT,
            device_type TEXT,
            placement TEXT,
            seat_id INTEGER,
            reached_queries INTEGER DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_perf_unique_daily "
        "ON performance_metrics(creative_id, metric_date, geography, device_type, placement)"
    )


def resolve_range(args: argparse.Namespace) -> tuple[str, str]:
    if args.start_date and args.end_date:
        return args.start_date, args.end_date

    days = max(1, args.days)
    end_date = date.today()
    start_date = end_date - timedelta(days=days - 1)
    return start_date.isoformat(), end_date.isoformat()


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill performance_metrics from rtb_daily")
    parser.add_argument("--start-date", help="YYYY-MM-DD")
    parser.add_argument("--end-date", help="YYYY-MM-DD")
    parser.add_argument("--days", type=int, default=60, help="Lookback window if no explicit dates")
    parser.add_argument("--buyer-id", help="Optional buyer_account_id filter")
    args = parser.parse_args()

    start_date, end_date = resolve_range(args)

    where = ["metric_date::date BETWEEN %s AND %s", "COALESCE(creative_id, '') <> ''"]
    params: list[object] = [start_date, end_date]
    if args.buyer_id:
        where.append("buyer_account_id = %s")
        params.append(args.buyer_id)

    with get_conn() as conn:
        ensure_performance_metrics_table(conn)

        sql = f"""
            INSERT INTO performance_metrics (
                creative_id, campaign_id, metric_date,
                impressions, clicks, spend_micros,
                geography, device_type, placement, reached_queries,
                updated_at
            )
            SELECT
                creative_id,
                MAX(NULLIF(billing_id, '')) AS campaign_id,
                metric_date::date AS metric_date,
                COALESCE(SUM(impressions), 0) AS impressions,
                COALESCE(SUM(clicks), 0) AS clicks,
                COALESCE(SUM(spend_micros), 0) AS spend_micros,
                COALESCE(NULLIF(country, ''), '') AS geography,
                COALESCE(NULLIF(platform, ''), '') AS device_type,
                COALESCE(NULLIF(environment, ''), '') AS placement,
                COALESCE(SUM(reached_queries), 0) AS reached_queries,
                NOW() AS updated_at
            FROM rtb_daily
            WHERE {' AND '.join(where)}
            GROUP BY creative_id, metric_date::date,
                     COALESCE(NULLIF(country, ''), ''),
                     COALESCE(NULLIF(platform, ''), ''),
                     COALESCE(NULLIF(environment, ''), '')
            ON CONFLICT (creative_id, metric_date, geography, device_type, placement)
            DO UPDATE SET
                impressions = EXCLUDED.impressions,
                clicks = EXCLUDED.clicks,
                spend_micros = EXCLUDED.spend_micros,
                reached_queries = EXCLUDED.reached_queries,
                campaign_id = COALESCE(EXCLUDED.campaign_id, performance_metrics.campaign_id),
                updated_at = NOW()
        """

        cur = conn.execute(sql, tuple(params))
        conn.commit()
        print(
            {
                "status": "ok",
                "start_date": start_date,
                "end_date": end_date,
                "buyer_id": args.buyer_id,
                "rows_upserted": cur.rowcount,
            }
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
