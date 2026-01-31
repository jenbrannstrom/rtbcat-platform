"""Postgres repository for home analytics precompute queries (SQL only)."""

from __future__ import annotations

from typing import Any

from storage.postgres_database import pg_query, pg_query_one


class HomeAnalyticsRepository:
    """SQL-only repository for home analytics."""

    async def get_funnel_row(self, days: int, buyer_id: str | None) -> dict[str, Any] | None:
        params: list[Any] = [f"-{days} days"]
        buyer_filter = ""
        if buyer_id:
            buyer_filter = " AND buyer_account_id = %s"
            params.append(buyer_id)
        return await pg_query_one(
            f"""
            SELECT
                SUM(reached_queries) as total_reached,
                SUM(impressions) as total_impressions,
                SUM(bids) as total_bids,
                SUM(successful_responses) as total_successful_responses,
                SUM(bid_requests) as total_bid_requests
            FROM home_seat_daily
            WHERE metric_date::date >= (CURRENT_DATE + %s::interval){buyer_filter}
            """,
            tuple(params),
        )

    async def get_publisher_rows(self, days: int, buyer_id: str | None, limit: int) -> list[dict[str, Any]]:
        params: list[Any] = [f"-{days} days"]
        buyer_filter = ""
        if buyer_id:
            buyer_filter = " AND buyer_account_id = %s"
            params.append(buyer_id)
        params.append(limit)
        return await pg_query(
            f"""
            SELECT
                publisher_id,
                MAX(publisher_name) as publisher_name,
                SUM(reached_queries) as reached,
                SUM(impressions) as impressions,
                SUM(bids) as total_bids,
                SUM(auctions_won) as auctions_won,
                SUM(successful_responses) as successful_responses,
                SUM(bid_requests) as bid_requests
            FROM home_publisher_daily
            WHERE metric_date::date >= (CURRENT_DATE + %s::interval){buyer_filter}
            GROUP BY publisher_id
            ORDER BY reached DESC
            LIMIT %s
            """,
            tuple(params),
        )

    async def get_geo_rows(self, days: int, buyer_id: str | None, limit: int) -> list[dict[str, Any]]:
        params: list[Any] = [f"-{days} days"]
        buyer_filter = ""
        if buyer_id:
            buyer_filter = " AND buyer_account_id = %s"
            params.append(buyer_id)
        params.append(limit)
        return await pg_query(
            f"""
            SELECT
                country,
                SUM(reached_queries) as reached,
                SUM(impressions) as impressions,
                SUM(bids) as total_bids,
                SUM(auctions_won) as auctions_won,
                SUM(successful_responses) as successful_responses,
                SUM(bid_requests) as bid_requests
            FROM home_geo_daily
            WHERE metric_date::date >= (CURRENT_DATE + %s::interval){buyer_filter}
            GROUP BY country
            ORDER BY reached DESC
            LIMIT %s
            """,
            tuple(params),
        )

    async def get_publisher_count(self, days: int, buyer_id: str | None) -> int:
        params: list[Any] = [f"-{days} days"]
        buyer_filter = ""
        if buyer_id:
            buyer_filter = " AND buyer_account_id = %s"
            params.append(buyer_id)
        row = await pg_query_one(
            f"""
            SELECT COUNT(DISTINCT publisher_id) as cnt
            FROM home_publisher_daily
            WHERE metric_date::date >= (CURRENT_DATE + %s::interval){buyer_filter}
            """,
            tuple(params),
        )
        return row["cnt"] if row else 0

    async def get_country_count(self, days: int, buyer_id: str | None) -> int:
        params: list[Any] = [f"-{days} days"]
        buyer_filter = ""
        if buyer_id:
            buyer_filter = " AND buyer_account_id = %s"
            params.append(buyer_id)
        row = await pg_query_one(
            f"""
            SELECT COUNT(DISTINCT country) as cnt
            FROM home_geo_daily
            WHERE metric_date::date >= (CURRENT_DATE + %s::interval){buyer_filter}
            """,
            tuple(params),
        )
        return row["cnt"] if row else 0

    async def get_config_rows(self, days: int, buyer_id: str | None) -> list[dict[str, Any]]:
        params: list[Any] = [f"-{days} days"]
        buyer_filter = ""
        if buyer_id:
            buyer_filter = " AND buyer_account_id = %s"
            params.append(buyer_id)
        return await pg_query(
            f"""
            SELECT
                billing_id,
                SUM(reached_queries) as total_reached,
                SUM(impressions) as total_impressions,
                SUM(bids_in_auction) as total_bids_in_auction,
                SUM(auctions_won) as total_auctions_won
            FROM home_config_daily
            WHERE metric_date::date >= (CURRENT_DATE + %s::interval){buyer_filter}
            GROUP BY billing_id
            ORDER BY total_reached DESC
            """,
            tuple(params),
        )
