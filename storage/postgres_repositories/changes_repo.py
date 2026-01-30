"""Postgres repository for pretargeting changes (SQL only)."""

from __future__ import annotations

from typing import Any

from storage.postgres_database import pg_execute, pg_insert_returning_id, pg_query


class ChangesRepository:
    """SQL-only repository for pending changes."""

    async def create_change(
        self,
        config_id: int,
        billing_id: str,
        action_type: str,
        payload: dict[str, Any],
        created_by: str,
    ) -> int:
        return await pg_insert_returning_id(
            """
            INSERT INTO pretargeting_changes
            (config_id, billing_id, action_type, payload, status, created_by)
            VALUES (%s, %s, %s, %s, 'PENDING', %s)
            RETURNING id
            """,
            (config_id, billing_id, action_type, payload, created_by),
        )

    async def list_changes(
        self, billing_id: str, limit: int = 100, offset: int = 0
    ) -> list[dict[str, Any]]:
        return await pg_query(
            """
            SELECT *
            FROM pretargeting_changes
            WHERE billing_id = %s
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            (billing_id, limit, offset),
        )

    async def get_change(self, change_id: int) -> dict[str, Any] | None:
        rows = await pg_query(
            "SELECT * FROM pretargeting_changes WHERE id = %s",
            (change_id,),
        )
        return rows[0] if rows else None

    async def update_change_status(self, change_id: int, status: str) -> int:
        return await pg_execute(
            """
            UPDATE pretargeting_changes
            SET status = %s, updated_at = NOW()
            WHERE id = %s
            """,
            (status, change_id),
        )

    async def delete_change(self, change_id: int) -> int:
        return await pg_execute(
            "DELETE FROM pretargeting_changes WHERE id = %s",
            (change_id,),
        )
