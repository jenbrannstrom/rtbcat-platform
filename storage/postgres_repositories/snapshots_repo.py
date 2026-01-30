"""Postgres repository for snapshots (SQL only)."""

from __future__ import annotations

from typing import Any

from storage.postgres_database import pg_execute, pg_query, pg_insert_returning_id


class SnapshotsRepository:
    """SQL-only repository for snapshot CRUD."""

    async def create_snapshot(
        self,
        user_id: str,
        config_id: int,
        billing_id: str,
        snapshot_data: dict[str, Any],
    ) -> int:
        snapshot_id = await pg_insert_returning_id(
            """
            INSERT INTO pretargeting_snapshots
            (config_id, billing_id, snapshot_data, created_by)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (config_id, billing_id, snapshot_data, user_id),
        )
        await pg_execute(
            """
            UPDATE pretargeting_configs
            SET last_snapshot_id = %s, updated_at = NOW()
            WHERE id = %s
            """,
            (snapshot_id, config_id),
        )
        return snapshot_id

    async def list_snapshots(
        self,
        billing_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        return await pg_query(
            """
            SELECT s.id, s.config_id, s.billing_id, s.snapshot_data, s.created_by,
                   s.created_at, c.name as config_name
            FROM pretargeting_snapshots s
            LEFT JOIN pretargeting_configs c ON s.config_id = c.id
            WHERE s.billing_id = %s
            ORDER BY s.created_at DESC
            LIMIT %s OFFSET %s
            """,
            (billing_id, limit, offset),
        )

    async def get_snapshot_by_id(self, snapshot_id: int) -> dict[str, Any] | None:
        rows = await pg_query(
            "SELECT * FROM pretargeting_snapshots WHERE id = %s",
            (snapshot_id,),
        )
        return rows[0] if rows else None
