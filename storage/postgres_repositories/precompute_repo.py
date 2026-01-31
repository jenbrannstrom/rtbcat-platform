"""Postgres repository for precompute health checks (SQL only)."""

from __future__ import annotations

from typing import Any

from storage.postgres_database import pg_query


class PrecomputeRepository:
    """SQL-only repository for precompute refresh logs."""

    async def get_cache_refresh_times(self) -> list[dict[str, Any]]:
        """Get the most recent refresh time for each cache."""
        return await pg_query(
            """
            SELECT cache_name, MAX(refreshed_at) AS refreshed_at
            FROM precompute_refresh_log
            GROUP BY cache_name
            """
        )
