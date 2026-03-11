"""Postgres repository for pretargeting changes (SQL only)."""

from __future__ import annotations

from typing import Any

from storage.postgres_database import pg_execute, pg_insert_returning_id, pg_query


class ChangesRepository:
    """SQL-only repository for pending changes."""

    async def create_pending_change(
        self,
        billing_id: str,
        config_id: str,
        change_type: str,
        field_name: str,
        value: str,
        reason: str | None,
        estimated_qps_impact: float | None,
        created_by: str | None,
    ) -> int:
        return await pg_insert_returning_id(
            """
            INSERT INTO pretargeting_pending_changes
            (billing_id, config_id, change_type, field_name, value,
             reason, estimated_qps_impact, created_by, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', CURRENT_TIMESTAMP)
            RETURNING id
            """,
            (
                billing_id,
                config_id,
                change_type,
                field_name,
                value,
                reason,
                estimated_qps_impact,
                created_by,
            ),
        )

    async def list_pending_changes(
        self,
        billing_id: str | None = None,
        status: str = "pending",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if billing_id:
            return await pg_query(
                """
                SELECT * FROM pretargeting_pending_changes
                WHERE billing_id = %s AND status = %s
                ORDER BY created_at DESC, id DESC LIMIT %s
                """,
                (billing_id, status, limit),
            )

        return await pg_query(
            """
            SELECT * FROM pretargeting_pending_changes
            WHERE status = %s
            ORDER BY created_at DESC, id DESC LIMIT %s
            """,
            (status, limit),
        )

    async def get_pending_change(self, change_id: int) -> dict[str, Any] | None:
        rows = await pg_query(
            "SELECT * FROM pretargeting_pending_changes WHERE id = %s",
            (change_id,),
        )
        return rows[0] if rows else None

    async def cancel_pending_change(self, change_id: int) -> int:
        return await pg_execute(
            "UPDATE pretargeting_pending_changes SET status = 'cancelled' WHERE id = %s AND status = 'pending'",
            (change_id,),
        )

    async def cancel_pending_changes_for_billing(self, billing_id: str) -> int:
        return await pg_execute(
            """
            UPDATE pretargeting_pending_changes
            SET status = 'cancelled'
            WHERE billing_id = %s AND status = 'pending'
            """,
            (billing_id,),
        )

    async def mark_pending_change_applied(
        self, change_id: int, applied_by: str | None = None
    ) -> int:
        return await pg_execute(
            """
            UPDATE pretargeting_pending_changes
            SET status = 'applied', applied_at = CURRENT_TIMESTAMP, applied_by = %s
            WHERE id = %s AND status = 'pending'
            """,
            (applied_by, change_id),
        )
