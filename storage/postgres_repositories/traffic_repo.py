"""Postgres repository for traffic import (SQL only)."""

from __future__ import annotations

from storage.postgres_database import pg_execute


class TrafficRepository:
    """SQL-only repository for traffic data."""

    async def upsert_traffic_row(
        self,
        canonical_size: str,
        raw_size: str,
        request_count: int,
        date: str,
        buyer_id: str | None,
    ) -> None:
        await pg_execute(
            """
            INSERT INTO rtb_traffic
                (canonical_size, raw_size, request_count, date, buyer_id)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (buyer_id, canonical_size, raw_size, date)
            DO UPDATE SET request_count = EXCLUDED.request_count
            """,
            (canonical_size, raw_size, request_count, date, buyer_id),
        )
