"""Postgres repository for retention management (SQL only)."""

from __future__ import annotations

from typing import Any

from storage.postgres_database import pg_execute, pg_query, pg_query_one


class RetentionRepository:
    """SQL-only repository for retention config and cleanup."""

    async def get_retention_config(self, seat_id: str | None = None) -> dict | None:
        if seat_id:
            row = await pg_query_one(
                "SELECT * FROM retention_config WHERE seat_id = %s",
                (seat_id,),
            )
            if row:
                return dict(row)
        row = await pg_query_one(
            "SELECT * FROM retention_config WHERE seat_id IS NULL"
        )
        return dict(row) if row else None

    async def set_retention_config(
        self,
        raw_retention_days: int,
        summary_retention_days: int,
        auto_aggregate_after_days: int,
        seat_id: str | None = None,
    ) -> None:
        await pg_execute(
            """
            INSERT INTO retention_config
            (seat_id, raw_retention_days, summary_retention_days, auto_aggregate_after_days, updated_at)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (seat_id) DO UPDATE SET
                raw_retention_days = EXCLUDED.raw_retention_days,
                summary_retention_days = EXCLUDED.summary_retention_days,
                auto_aggregate_after_days = EXCLUDED.auto_aggregate_after_days,
                updated_at = CURRENT_TIMESTAMP
            """,
            (seat_id, raw_retention_days, summary_retention_days, auto_aggregate_after_days),
        )

    async def get_raw_stats(self, seat_id: str | None = None) -> dict[str, Any]:
        if seat_id:
            row = await pg_query_one(
                "SELECT COUNT(*) as cnt, MIN(metric_date) as earliest, MAX(metric_date) as latest FROM performance_metrics WHERE seat_id = %s",
                (seat_id,),
            )
        else:
            row = await pg_query_one(
                "SELECT COUNT(*) as cnt, MIN(metric_date) as earliest, MAX(metric_date) as latest FROM performance_metrics"
            )
        return dict(row) if row else {}

    async def get_summary_stats(self, seat_id: str | None = None) -> dict[str, Any]:
        if seat_id:
            row = await pg_query_one(
                "SELECT COUNT(*) as cnt, MIN(summary_date) as earliest, MAX(summary_date) as latest FROM daily_creative_summary WHERE seat_id = %s",
                (seat_id,),
            )
        else:
            row = await pg_query_one(
                "SELECT COUNT(*) as cnt, MIN(summary_date) as earliest, MAX(summary_date) as latest FROM daily_creative_summary"
            )
        return dict(row) if row else {}

    async def get_conversion_event_stats(self, seat_id: str | None = None) -> dict[str, Any]:
        if seat_id:
            row = await pg_query_one(
                "SELECT COUNT(*) as cnt, MIN(event_ts) as earliest, MAX(event_ts) as latest FROM conversion_events WHERE buyer_id = %s",
                (seat_id,),
            )
        else:
            row = await pg_query_one(
                "SELECT COUNT(*) as cnt, MIN(event_ts) as earliest, MAX(event_ts) as latest FROM conversion_events"
            )
        return dict(row) if row else {}

    async def get_conversion_failure_stats(self, seat_id: str | None = None) -> dict[str, Any]:
        if seat_id:
            row = await pg_query_one(
                "SELECT COUNT(*) as cnt, MIN(created_at) as earliest, MAX(created_at) as latest FROM conversion_ingestion_failures WHERE buyer_id = %s",
                (seat_id,),
            )
        else:
            row = await pg_query_one(
                "SELECT COUNT(*) as cnt, MIN(created_at) as earliest, MAX(created_at) as latest FROM conversion_ingestion_failures"
            )
        return dict(row) if row else {}

    async def get_conversion_join_stats(self, seat_id: str | None = None) -> dict[str, Any]:
        if seat_id:
            row = await pg_query_one(
                "SELECT COUNT(*) as cnt, MIN(conversion_event_ts) as earliest, MAX(conversion_event_ts) as latest FROM conversion_attribution_joins WHERE buyer_id = %s",
                (seat_id,),
            )
        else:
            row = await pg_query_one(
                "SELECT COUNT(*) as cnt, MIN(conversion_event_ts) as earliest, MAX(conversion_event_ts) as latest FROM conversion_attribution_joins"
            )
        return dict(row) if row else {}

    async def aggregate_old_data(self, cutoff_date: str, seat_id: str | None = None) -> None:
        seat_filter = "AND seat_id = %s" if seat_id else ""
        params: tuple = (cutoff_date, seat_id) if seat_id else (cutoff_date,)

        await pg_execute(
            f"""
            INSERT INTO daily_creative_summary
            (seat_id, creative_id, summary_date, total_queries, total_impressions, total_clicks, total_spend, win_rate, ctr, cpm)
            SELECT
                seat_id,
                creative_id,
                metric_date,
                SUM(COALESCE(reached_queries, 0)),
                SUM(COALESCE(impressions, 0)),
                SUM(COALESCE(clicks, 0)),
                SUM(COALESCE(spend_micros, 0)) / 1000000.0,
                CASE WHEN SUM(COALESCE(reached_queries, 0)) > 0
                     THEN CAST(SUM(COALESCE(impressions, 0)) AS REAL) / SUM(reached_queries)
                     ELSE 0 END,
                CASE WHEN SUM(COALESCE(impressions, 0)) > 0
                     THEN CAST(SUM(COALESCE(clicks, 0)) AS REAL) / SUM(impressions)
                     ELSE 0 END,
                CASE WHEN SUM(COALESCE(impressions, 0)) > 0
                     THEN (SUM(COALESCE(spend_micros, 0)) / 1000000.0 / SUM(impressions)) * 1000
                     ELSE 0 END
            FROM performance_metrics
            WHERE metric_date < %s {seat_filter}
            GROUP BY seat_id, creative_id, metric_date
            ON CONFLICT (seat_id, creative_id, summary_date) DO UPDATE SET
                total_queries = EXCLUDED.total_queries,
                total_impressions = EXCLUDED.total_impressions,
                total_clicks = EXCLUDED.total_clicks,
                total_spend = EXCLUDED.total_spend
            """,
            params,
        )

    async def delete_raw_before(self, cutoff_date: str, seat_id: str | None = None) -> int:
        seat_filter = "AND seat_id = %s" if seat_id else ""
        params: tuple = (cutoff_date, seat_id) if seat_id else (cutoff_date,)
        return await pg_execute(
            f"DELETE FROM performance_metrics WHERE metric_date < %s {seat_filter}",
            params,
        )

    async def delete_summary_before(self, cutoff_date: str, seat_id: str | None = None) -> int:
        seat_filter = "AND seat_id = %s" if seat_id else ""
        params: tuple = (cutoff_date, seat_id) if seat_id else (cutoff_date,)
        return await pg_execute(
            f"DELETE FROM daily_creative_summary WHERE summary_date < %s {seat_filter}",
            params,
        )

    async def delete_conversion_joins_before(self, cutoff_date: str, seat_id: str | None = None) -> int:
        seat_filter = "AND buyer_id = %s" if seat_id else ""
        params: tuple = (cutoff_date, seat_id) if seat_id else (cutoff_date,)
        return await pg_execute(
            f"DELETE FROM conversion_attribution_joins WHERE conversion_event_ts < %s::date {seat_filter}",
            params,
        )

    async def delete_conversion_events_before(self, cutoff_date: str, seat_id: str | None = None) -> int:
        seat_filter = "AND buyer_id = %s" if seat_id else ""
        params: tuple = (cutoff_date, seat_id) if seat_id else (cutoff_date,)
        return await pg_execute(
            f"DELETE FROM conversion_events WHERE event_ts < %s::date {seat_filter}",
            params,
        )

    async def delete_conversion_failures_before(self, cutoff_date: str, seat_id: str | None = None) -> int:
        seat_filter = "AND buyer_id = %s" if seat_id else ""
        params: tuple = (cutoff_date, seat_id) if seat_id else (cutoff_date,)
        return await pg_execute(
            f"DELETE FROM conversion_ingestion_failures WHERE created_at < %s::date {seat_filter}",
            params,
        )
