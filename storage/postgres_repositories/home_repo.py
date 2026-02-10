"""Postgres repository for home analytics precompute queries (SQL only)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from storage.postgres_database import pg_query, pg_query_one


class HomeAnalyticsRepository:
    """SQL-only repository for home analytics."""

    @staticmethod
    def _cutoff_date(days: int) -> str:
        """Return ISO date cutoff matching prior CURRENT_DATE + '-N days' behavior."""
        return (date.today() - timedelta(days=days)).isoformat()

    async def get_funnel_row(self, days: int, buyer_id: str | None) -> dict[str, Any] | None:
        params: list[Any] = [self._cutoff_date(days)]
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
            WHERE metric_date >= %s{buyer_filter}
            """,
            tuple(params),
        )

    async def get_publisher_rows(self, days: int, buyer_id: str | None, limit: int) -> list[dict[str, Any]]:
        params: list[Any] = [self._cutoff_date(days)]
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
            WHERE metric_date >= %s{buyer_filter}
            GROUP BY publisher_id
            ORDER BY reached DESC
            LIMIT %s
            """,
            tuple(params),
        )

    async def get_geo_rows(self, days: int, buyer_id: str | None, limit: int) -> list[dict[str, Any]]:
        params: list[Any] = [self._cutoff_date(days)]
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
            WHERE metric_date >= %s{buyer_filter}
            GROUP BY country
            ORDER BY reached DESC
            LIMIT %s
            """,
            tuple(params),
        )

    async def get_publisher_count(self, days: int, buyer_id: str | None) -> int:
        params: list[Any] = [self._cutoff_date(days)]
        buyer_filter = ""
        if buyer_id:
            buyer_filter = " AND buyer_account_id = %s"
            params.append(buyer_id)
        row = await pg_query_one(
            f"""
            SELECT COUNT(DISTINCT publisher_id) as cnt
            FROM home_publisher_daily
            WHERE metric_date >= %s{buyer_filter}
            """,
            tuple(params),
        )
        return row["cnt"] if row else 0

    async def get_country_count(self, days: int, buyer_id: str | None) -> int:
        params: list[Any] = [self._cutoff_date(days)]
        buyer_filter = ""
        if buyer_id:
            buyer_filter = " AND buyer_account_id = %s"
            params.append(buyer_id)
        row = await pg_query_one(
            f"""
            SELECT COUNT(DISTINCT country) as cnt
            FROM home_geo_daily
            WHERE metric_date >= %s{buyer_filter}
            """,
            tuple(params),
        )
        return row["cnt"] if row else 0

    async def get_config_rows(self, days: int, buyer_id: str | None) -> list[dict[str, Any]]:
        params: list[Any] = [self._cutoff_date(days)]
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
            WHERE metric_date >= %s{buyer_filter}
            GROUP BY billing_id
            ORDER BY total_reached DESC
            """,
            tuple(params),
        )

    async def get_bidder_id_for_buyer(self, buyer_id: str) -> str | None:
        row = await pg_query_one(
            """
            SELECT bidder_id
            FROM buyer_seats
            WHERE buyer_id = %s
            LIMIT 1
            """,
            (buyer_id,),
        )
        return (row or {}).get("bidder_id")

    async def get_endpoints_for_bidder(self, bidder_id: str | None) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if bidder_id:
            where = "WHERE bidder_id = %s"
            params.append(bidder_id)
        return await pg_query(
            f"""
            SELECT
                bidder_id,
                endpoint_id,
                url,
                trading_location,
                COALESCE(maximum_qps, 0) AS maximum_qps
            FROM rtb_endpoints
            {where}
            ORDER BY trading_location, endpoint_id
            """,
            tuple(params),
        )

    async def get_observed_endpoint_rows(self, bidder_id: str | None) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if bidder_id:
            where = "WHERE c.bidder_id = %s"
            params.append(bidder_id)
        return await pg_query(
            f"""
            SELECT
                c.bidder_id,
                c.endpoint_id,
                COALESCE(c.current_qps, 0) AS current_qps,
                c.observed_at,
                e.trading_location,
                e.url
            FROM rtb_endpoints_current c
            LEFT JOIN rtb_endpoints e
              ON e.bidder_id = c.bidder_id AND e.endpoint_id = c.endpoint_id
            {where}
            ORDER BY c.current_qps DESC, c.endpoint_id
            """,
            tuple(params),
        )
