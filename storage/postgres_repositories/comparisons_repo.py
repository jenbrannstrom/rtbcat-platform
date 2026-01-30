"""Postgres repository for snapshot comparisons (SQL only)."""

from __future__ import annotations

from typing import Any

from storage.postgres_database import pg_query, pg_query_one


class ComparisonsRepository:
    """SQL-only repository for snapshot comparisons."""

    async def create_comparison(
        self,
        billing_id: str,
        comparison_name: str | None,
        before_snapshot_id: int,
        before_start_date: str | None,
        before_end_date: str | None,
    ) -> int:
        row = await pg_query_one(
            """
            INSERT INTO snapshot_comparisons
            (billing_id, comparison_name, before_snapshot_id, before_start_date, before_end_date, status)
            VALUES (%s, %s, %s, %s, %s, 'in_progress')
            RETURNING id
            """,
            (billing_id, comparison_name, before_snapshot_id, before_start_date, before_end_date),
        )
        return row["id"] if row else 0

    async def get_comparison(self, comparison_id: int) -> dict[str, Any] | None:
        row = await pg_query_one(
            "SELECT * FROM snapshot_comparisons WHERE id = %s",
            (comparison_id,),
        )
        return dict(row) if row else None

    async def list_comparisons(
        self,
        billing_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        conditions = []
        params: list[Any] = []

        if billing_id:
            conditions.append("billing_id = %s")
            params.append(billing_id)
        if status:
            conditions.append("status = %s")
            params.append(status)

        params.append(limit)
        where_clause = " AND ".join(conditions) if conditions else "1=1"

        rows = await pg_query(
            f"""
            SELECT * FROM snapshot_comparisons
            WHERE {where_clause}
            ORDER BY created_at DESC LIMIT %s
            """,
            tuple(params),
        )
        return [dict(row) for row in rows]
