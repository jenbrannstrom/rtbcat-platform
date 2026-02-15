"""Postgres repository for precompute health checks (SQL only)."""

from __future__ import annotations

import re
from typing import Any

from storage.postgres_database import pg_query, pg_query_one


_SAFE_TABLE_NAME = re.compile(r"^[a-z0-9_]+$")


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

    async def get_latest_metric_dates(
        self,
        table_names: list[str],
    ) -> dict[str, str | None]:
        """Return max(metric_date) per table for provided table names."""
        if not table_names:
            return {}

        sanitized = [name for name in table_names if _SAFE_TABLE_NAME.match(name)]
        if len(sanitized) != len(table_names):
            raise ValueError("Unsafe table name provided for freshness lookup.")

        existing_rows = await pg_query(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = ANY(%s)
            """,
            (sanitized,),
        )
        existing = {str(row.get("table_name") or "") for row in existing_rows}

        latest_map: dict[str, str | None] = {}
        for table_name in sanitized:
            if table_name not in existing:
                latest_map[table_name] = None
                continue
            row = await pg_query_one(
                f"SELECT MAX(metric_date::date) AS max_metric_date FROM {table_name}"
            )
            value = (row or {}).get("max_metric_date")
            if hasattr(value, "isoformat"):
                latest_map[table_name] = value.isoformat()
            elif value is not None:
                latest_map[table_name] = str(value)
            else:
                latest_map[table_name] = None
        return latest_map
