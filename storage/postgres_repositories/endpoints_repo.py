"""Postgres repository for RTB endpoints (SQL only)."""

from __future__ import annotations

from typing import Any, Optional

from storage.postgres_database import pg_execute, pg_execute_many, pg_query, pg_query_one


class EndpointsRepository:
    """SQL-only repository for RTB endpoints."""

    async def upsert_endpoints(self, bidder_id: str, endpoints: list[dict[str, Any]]) -> int:
        if not endpoints:
            # No endpoints from API - delete all for this bidder
            await pg_execute(
                "DELETE FROM rtb_endpoints WHERE bidder_id = %s",
                (bidder_id,),
            )
            return 0

        # Get endpoint IDs from API response
        api_endpoint_ids = [str(ep["endpointId"]) for ep in endpoints]

        # Delete endpoints that no longer exist in API
        await pg_execute(
            """
            DELETE FROM rtb_endpoints
            WHERE bidder_id = %s AND endpoint_id != ALL(%s)
            """,
            (bidder_id, api_endpoint_ids),
        )

        data = [
            (
                bidder_id,
                ep["endpointId"],
                ep.get("url"),
                ep.get("maximumQps"),
                ep.get("tradingLocation"),
                ep.get("bidProtocol"),
            )
            for ep in endpoints
        ]

        await pg_execute_many(
            """
            INSERT INTO rtb_endpoints
            (bidder_id, endpoint_id, url, maximum_qps, trading_location, bid_protocol, synced_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (bidder_id, endpoint_id) DO UPDATE SET
                url = EXCLUDED.url,
                maximum_qps = EXCLUDED.maximum_qps,
                trading_location = EXCLUDED.trading_location,
                bid_protocol = EXCLUDED.bid_protocol,
                synced_at = NOW()
            """,
            data,
        )
        return len(endpoints)

    async def list_endpoints(self, bidder_id: str | None = None) -> list[dict[str, Any]]:
        if bidder_id:
            return await pg_query(
                "SELECT * FROM rtb_endpoints WHERE bidder_id = %s ORDER BY trading_location, endpoint_id",
                (bidder_id,),
            )
        return await pg_query(
            "SELECT * FROM rtb_endpoints ORDER BY trading_location, endpoint_id"
        )

    async def get_current_qps(self, bidder_id: str | None = None) -> float:
        try:
            if bidder_id:
                rows = await pg_query(
                    "SELECT SUM(current_qps) AS current_qps FROM rtb_endpoints_current WHERE bidder_id = %s",
                    (bidder_id,),
                )
            else:
                rows = await pg_query(
                    "SELECT SUM(current_qps) AS current_qps FROM rtb_endpoints_current"
                )
        except Exception:
            return 0.0
        if not rows:
            return 0.0
        value = rows[0].get("current_qps")
        return float(value) if value is not None else 0.0

    async def refresh_endpoints_current(
        self,
        lookback_days: int = 7,
        bidder_id: Optional[str] = None,
    ) -> int:
        """Derive observed QPS from bidstream data and populate rtb_endpoints_current.

        For each configured endpoint in rtb_endpoints, computes observed QPS by:
        1. Summing reached_queries from home_seat_daily over lookback_days
        2. Converting to average QPS (total / window_seconds)
        3. Distributing across endpoints proportionally by maximum_qps

        Returns the number of rows upserted.
        """
        bidder_filter = ""
        params: list[Any] = [lookback_days]
        if bidder_id:
            bidder_filter = "AND e.bidder_id = %s"
            params.append(bidder_id)

        return await pg_execute(
            f"""
            INSERT INTO rtb_endpoints_current (bidder_id, endpoint_id, current_qps, observed_at)
            SELECT
                e.bidder_id,
                e.endpoint_id,
                CASE
                    WHEN totals.total_max_qps > 0 AND traffic.observed_qps IS NOT NULL
                    THEN (COALESCE(e.maximum_qps, 0)::real / totals.total_max_qps) * traffic.observed_qps
                    ELSE 0
                END,
                CURRENT_TIMESTAMP
            FROM rtb_endpoints e
            JOIN (
                SELECT bidder_id, NULLIF(SUM(COALESCE(maximum_qps, 0)), 0)::real AS total_max_qps
                FROM rtb_endpoints
                GROUP BY bidder_id
            ) totals ON totals.bidder_id = e.bidder_id
            LEFT JOIN (
                SELECT
                    COALESCE(bs.bidder_id, hsd.buyer_account_id) AS bidder_id,
                    SUM(hsd.reached_queries)::real
                        / GREATEST(COUNT(DISTINCT hsd.metric_date), 1)
                        / 86400 AS observed_qps
                FROM home_seat_daily hsd
                LEFT JOIN buyer_seats bs ON bs.buyer_id = hsd.buyer_account_id
                WHERE hsd.metric_date >= CURRENT_DATE - make_interval(days => %s)
                GROUP BY COALESCE(bs.bidder_id, hsd.buyer_account_id)
            ) traffic ON traffic.bidder_id = e.bidder_id
            WHERE TRUE {bidder_filter}
            ON CONFLICT (bidder_id, endpoint_id) DO UPDATE SET
                current_qps = EXCLUDED.current_qps,
                observed_at = CURRENT_TIMESTAMP
            """,
            tuple(params),
        )
