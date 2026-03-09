"""Postgres repository for pretargeting snapshots (SQL only)."""

from __future__ import annotations

from typing import Any

from psycopg.types.json import Jsonb

from storage.postgres_database import pg_query, pg_query_one
from utils.list_payloads import parse_list_payload


class SnapshotsRepository:
    """SQL-only repository for snapshot CRUD."""

    @staticmethod
    def _jsonb_list_param(value: Any) -> Jsonb:
        return Jsonb(parse_list_payload(value))

    async def create_snapshot(
        self,
        billing_id: str,
        snapshot_name: str | None,
        snapshot_type: str,
        config_data: dict[str, Any],
        performance_data: dict[str, Any],
        publisher_targeting_mode: str | None,
        publisher_targeting_values: list[str] | None,
        notes: str | None,
    ) -> int:
        row = await pg_query_one(
            """
            INSERT INTO pretargeting_snapshots
            (billing_id, snapshot_name, snapshot_type,
             included_formats, included_platforms, included_sizes,
             included_geos, excluded_geos, state,
             publisher_targeting_mode, publisher_targeting_values,
             total_impressions, total_clicks, total_spend_usd,
             total_reached_queries, days_tracked,
             avg_daily_impressions, avg_daily_spend_usd, ctr_pct, cpm_usd,
             notes, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            RETURNING id
            """,
            (
                billing_id,
                snapshot_name,
                snapshot_type,
                self._jsonb_list_param(config_data.get("included_formats")),
                self._jsonb_list_param(config_data.get("included_platforms")),
                self._jsonb_list_param(config_data.get("included_sizes")),
                self._jsonb_list_param(config_data.get("included_geos")),
                self._jsonb_list_param(config_data.get("excluded_geos")),
                config_data.get("state"),
                publisher_targeting_mode,
                self._jsonb_list_param(publisher_targeting_values),
                performance_data.get("total_impressions", 0),
                performance_data.get("total_clicks", 0),
                performance_data.get("total_spend_usd", 0),
                performance_data.get("total_reached_queries", 0),
                performance_data.get("days_tracked", 0),
                performance_data.get("avg_daily_impressions"),
                performance_data.get("avg_daily_spend_usd"),
                performance_data.get("ctr_pct"),
                performance_data.get("cpm_usd"),
                notes,
            ),
        )
        return row["id"] if row else 0

    async def get_snapshot(self, snapshot_id: int) -> dict[str, Any] | None:
        row = await pg_query_one(
            "SELECT * FROM pretargeting_snapshots WHERE id = %s",
            (snapshot_id,),
        )
        return dict(row) if row else None

    async def list_snapshots(
        self,
        billing_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if billing_id:
            rows = await pg_query(
                """
                SELECT * FROM pretargeting_snapshots
                WHERE billing_id = %s
                ORDER BY created_at DESC LIMIT %s
                """,
                (billing_id, limit),
            )
        else:
            rows = await pg_query(
                "SELECT * FROM pretargeting_snapshots ORDER BY created_at DESC LIMIT %s",
                (limit,),
            )
        return [dict(row) for row in rows]
