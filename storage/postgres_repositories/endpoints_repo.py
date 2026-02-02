"""Postgres repository for RTB endpoints (SQL only)."""

from __future__ import annotations

from typing import Any

from storage.postgres_database import pg_execute, pg_execute_many, pg_query


class EndpointsRepository:
    """SQL-only repository for RTB endpoints."""

    async def upsert_endpoints(self, bidder_id: str, endpoints: list[dict[str, Any]]) -> int:
        if not endpoints:
            return 0

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
