"""Postgres repository for home analytics precompute queries (SQL only)."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from storage.postgres_database import pg_query, pg_query_one


class HomeAnalyticsRepository:
    """SQL-only repository for home analytics."""

    @staticmethod
    def _window_bounds(days: int) -> tuple[str, str]:
        """Return inclusive ISO start/end dates for an exact N-day window."""
        safe_days = max(days, 1)
        end_date = date.today()
        start_date = end_date - timedelta(days=safe_days - 1)
        return start_date.isoformat(), end_date.isoformat()

    @classmethod
    def get_window_bounds(cls, days: int) -> tuple[str, str]:
        """Public accessor for request window bounds."""
        return cls._window_bounds(days)

    async def get_funnel_row(self, days: int, buyer_id: str | None) -> dict[str, Any] | None:
        start_date, end_date = self._window_bounds(days)
        params: list[Any] = [start_date, end_date]
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
            FROM seat_daily
            WHERE metric_date BETWEEN %s AND %s{buyer_filter}
            """,
            tuple(params),
        )

    async def get_publisher_rows(self, days: int, buyer_id: str | None, limit: int) -> list[dict[str, Any]]:
        start_date, end_date = self._window_bounds(days)
        params: list[Any] = [start_date, end_date]
        buyer_filter = ""
        if buyer_id:
            buyer_filter = " AND buyer_account_id = %s"
            params.append(buyer_id)
        params.append(limit)
        return await pg_query(
            f"""
            WITH grouped AS (
                SELECT
                    publisher_id,
                    MAX(publisher_name) AS publisher_name,
                    SUM(reached_queries) AS reached,
                    SUM(impressions) AS impressions,
                    SUM(bids) AS total_bids,
                    SUM(auctions_won) AS auctions_won,
                    SUM(successful_responses) AS successful_responses,
                    SUM(bid_requests) AS bid_requests
                FROM seat_publisher_daily
                WHERE metric_date BETWEEN %s AND %s{buyer_filter}
                GROUP BY publisher_id
            )
            SELECT
                publisher_id,
                publisher_name,
                reached,
                impressions,
                total_bids,
                auctions_won,
                successful_responses,
                bid_requests,
                COUNT(*) OVER ()::int AS total_publishers
            FROM grouped
            ORDER BY reached DESC
            LIMIT %s
            """,
            tuple(params),
        )

    async def get_geo_rows(self, days: int, buyer_id: str | None, limit: int) -> list[dict[str, Any]]:
        start_date, end_date = self._window_bounds(days)
        params: list[Any] = [start_date, end_date]
        buyer_filter = ""
        if buyer_id:
            buyer_filter = " AND buyer_account_id = %s"
            params.append(buyer_id)
        params.append(limit)
        return await pg_query(
            f"""
            WITH grouped AS (
                SELECT
                    country,
                    SUM(reached_queries) AS reached,
                    SUM(impressions) AS impressions,
                    SUM(bids) AS total_bids,
                    SUM(auctions_won) AS auctions_won,
                    SUM(successful_responses) AS successful_responses,
                    SUM(bid_requests) AS bid_requests
                FROM seat_geo_daily
                WHERE metric_date BETWEEN %s AND %s{buyer_filter}
                GROUP BY country
            )
            SELECT
                country,
                reached,
                impressions,
                total_bids,
                auctions_won,
                successful_responses,
                bid_requests,
                COUNT(*) OVER ()::int AS total_countries
            FROM grouped
            ORDER BY reached DESC
            LIMIT %s
            """,
            tuple(params),
        )

    async def get_publisher_count(self, days: int, buyer_id: str | None) -> int:
        start_date, end_date = self._window_bounds(days)
        params: list[Any] = [start_date, end_date]
        buyer_filter = ""
        if buyer_id:
            buyer_filter = " AND buyer_account_id = %s"
            params.append(buyer_id)
        row = await pg_query_one(
            f"""
            SELECT COUNT(DISTINCT publisher_id) as cnt
            FROM seat_publisher_daily
            WHERE metric_date BETWEEN %s AND %s{buyer_filter}
            """,
            tuple(params),
        )
        return row["cnt"] if row else 0

    async def get_country_count(self, days: int, buyer_id: str | None) -> int:
        start_date, end_date = self._window_bounds(days)
        params: list[Any] = [start_date, end_date]
        buyer_filter = ""
        if buyer_id:
            buyer_filter = " AND buyer_account_id = %s"
            params.append(buyer_id)
        row = await pg_query_one(
            f"""
            SELECT COUNT(DISTINCT country) as cnt
            FROM seat_geo_daily
            WHERE metric_date BETWEEN %s AND %s{buyer_filter}
            """,
            tuple(params),
        )
        return row["cnt"] if row else 0

    async def get_config_rows(self, days: int, buyer_id: str | None) -> list[dict[str, Any]]:
        start_date, end_date = self._window_bounds(days)
        params: list[Any] = [start_date, end_date]
        buyer_filter = ""
        if buyer_id:
            buyer_filter = " AND buyer_account_id = %s"
            params.append(buyer_id)
        return await pg_query(
            f"""
            WITH grouped AS (
                SELECT
                    billing_id,
                    SUM(reached_queries) AS total_reached,
                    SUM(impressions) AS total_impressions,
                    SUM(bids_in_auction) AS total_bids_in_auction,
                    SUM(auctions_won) AS total_auctions_won
                FROM pretarg_daily
                WHERE metric_date BETWEEN %s AND %s{buyer_filter}
                  AND billing_id IS NOT NULL
                  AND BTRIM(billing_id) <> ''
                GROUP BY billing_id
            )
            SELECT
                billing_id,
                total_reached,
                total_impressions,
                total_bids_in_auction,
                total_auctions_won,
                SUM(total_reached) OVER () AS overall_total_reached,
                SUM(total_impressions) OVER () AS overall_total_impressions
            FROM grouped
            ORDER BY total_reached DESC
            LIMIT 20
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

    async def get_home_seat_coverage(self, days: int, buyer_id: str | None) -> dict[str, Any]:
        """Get actual seat_daily data coverage in requested window."""
        start_date, end_date = self._window_bounds(days)
        params: list[Any] = [start_date, end_date]
        buyer_filter = ""
        if buyer_id:
            buyer_filter = " AND buyer_account_id = %s"
            params.append(buyer_id)
        row = await pg_query_one(
            f"""
            SELECT
                MIN(metric_date)::text AS min_date,
                MAX(metric_date)::text AS max_date,
                COUNT(DISTINCT metric_date)::int AS days_with_data,
                COUNT(*)::bigint AS row_count
            FROM seat_daily
            WHERE metric_date BETWEEN %s AND %s{buyer_filter}
            """,
            tuple(params),
        )
        return dict(row or {})

    async def get_bidstream_summary(self, days: int, buyer_id: str | None) -> dict[str, Any]:
        """Get RTB bidstream funnel aggregates for AB-parity style metrics."""
        start_date, end_date = self._window_bounds(days)
        params: list[Any] = [start_date, end_date]
        buyer_filter = ""
        if buyer_id:
            buyer_filter = " AND buyer_account_id = %s"
            params.append(buyer_id)
        row = await pg_query_one(
            f"""
            SELECT
                COALESCE(SUM(bids), 0)::bigint AS total_bids,
                COALESCE(SUM(bids_in_auction), 0)::bigint AS total_bids_in_auction,
                COALESCE(SUM(auctions_won), 0)::bigint AS total_auctions_won,
                COALESCE(SUM(reached_queries), 0)::bigint AS total_reached_queries,
                COALESCE(SUM(impressions), 0)::bigint AS total_impressions,
                COUNT(*)::bigint AS row_count
            FROM rtb_bidstream
            WHERE metric_date BETWEEN %s AND %s{buyer_filter}
            """,
            tuple(params),
        )
        return dict(row or {})

    async def get_bidstream_coverage(self, days: int, buyer_id: str | None) -> dict[str, Any]:
        """Get actual rtb_bidstream data coverage in requested window."""
        start_date, end_date = self._window_bounds(days)
        params: list[Any] = [start_date, end_date]
        buyer_filter = ""
        if buyer_id:
            buyer_filter = " AND buyer_account_id = %s"
            params.append(buyer_id)
        row = await pg_query_one(
            f"""
            SELECT
                MIN(metric_date)::text AS min_date,
                MAX(metric_date)::text AS max_date,
                COUNT(DISTINCT metric_date)::int AS days_with_data,
                COUNT(*)::bigint AS row_count
            FROM rtb_bidstream
            WHERE metric_date BETWEEN %s AND %s{buyer_filter}
            """,
            tuple(params),
        )
        return dict(row or {})
