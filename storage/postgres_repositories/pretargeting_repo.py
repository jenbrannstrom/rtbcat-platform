"""Postgres repository for pretargeting (SQL only)."""

from __future__ import annotations

from typing import Any

from storage.postgres_database import (
    pg_execute,
    pg_insert_returning_id,
    pg_query,
    pg_query_one,
)


class PretargetingRepository:
    """SQL-only repository for pretargeting configs and publishers."""

    async def list_configs(self, bidder_id: str | None = None) -> list[dict[str, Any]]:
        if bidder_id:
            return await pg_query(
                """
                SELECT * FROM (
                    SELECT
                        pc.*,
                        ROW_NUMBER() OVER (
                            PARTITION BY COALESCE(NULLIF(TRIM(pc.billing_id), ''), pc.config_id)
                            ORDER BY pc.synced_at DESC NULLS LAST, pc.id DESC
                        ) AS rn
                    FROM pretargeting_configs pc
                    WHERE pc.bidder_id = %s
                ) deduped
                WHERE rn = 1
                ORDER BY billing_id
                """,
                (bidder_id,),
            )
        return await pg_query(
            """
            SELECT * FROM (
                SELECT
                    pc.*,
                    ROW_NUMBER() OVER (
                        PARTITION BY COALESCE(NULLIF(TRIM(pc.billing_id), ''), pc.config_id)
                        ORDER BY pc.synced_at DESC NULLS LAST, pc.id DESC
                    ) AS rn
                FROM pretargeting_configs pc
            ) deduped
            WHERE rn = 1
            ORDER BY billing_id
            """
        )

    async def get_config_by_billing_id(self, billing_id: str) -> dict[str, Any] | None:
        return await pg_query_one(
            """
            SELECT *
            FROM pretargeting_configs
            WHERE billing_id = %s
            ORDER BY synced_at DESC NULLS LAST, id DESC
            LIMIT 1
            """,
            (billing_id,),
        )

    async def save_config(self, config: dict[str, Any]) -> None:
        await pg_execute(
            """
            INSERT INTO pretargeting_configs
            (bidder_id, config_id, billing_id, display_name, user_name, state,
             included_formats, included_platforms, included_sizes,
             included_geos, excluded_geos, included_operating_systems,
             raw_config, synced_at)
            VALUES (%s, %s, %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, NOW())
            ON CONFLICT (bidder_id, config_id) DO UPDATE SET
                billing_id = EXCLUDED.billing_id,
                display_name = EXCLUDED.display_name,
                user_name = EXCLUDED.user_name,
                state = EXCLUDED.state,
                included_formats = EXCLUDED.included_formats,
                included_platforms = EXCLUDED.included_platforms,
                included_sizes = EXCLUDED.included_sizes,
                included_geos = EXCLUDED.included_geos,
                excluded_geos = EXCLUDED.excluded_geos,
                included_operating_systems = EXCLUDED.included_operating_systems,
                raw_config = EXCLUDED.raw_config,
                synced_at = NOW()
            """,
            (
                config.get("bidder_id"),
                config.get("config_id"),
                config.get("billing_id"),
                config.get("display_name"),
                config.get("user_name"),
                config.get("state"),
                config.get("included_formats"),
                config.get("included_platforms"),
                config.get("included_sizes"),
                config.get("included_geos"),
                config.get("excluded_geos"),
                config.get("included_operating_systems"),
                config.get("raw_config"),
            ),
        )

    async def update_user_name(self, billing_id: str, user_name: str | None) -> int:
        return await pg_execute(
            "UPDATE pretargeting_configs SET user_name = %s WHERE billing_id = %s",
            (user_name, billing_id),
        )

    async def update_state(self, billing_id: str, state: str) -> int:
        return await pg_execute(
            "UPDATE pretargeting_configs SET state = %s WHERE billing_id = %s",
            (state, billing_id),
        )

    async def list_history(
        self,
        config_id: str | None = None,
        billing_id: str | None = None,
        days: int = 30,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        conditions = ["ph.changed_at >= CURRENT_TIMESTAMP - make_interval(days => %s)"]
        params: list[Any] = [days]

        if config_id:
            conditions.append("ph.config_id = %s")
            params.append(config_id)
        if billing_id:
            conditions.append("pc.billing_id = %s")
            params.append(billing_id)

        params.append(limit)
        where_clause = " AND ".join(conditions)

        rows = await pg_query(
            f"""
            SELECT ph.* FROM pretargeting_history ph
            LEFT JOIN pretargeting_configs pc ON ph.config_id = pc.config_id
            WHERE {where_clause}
            ORDER BY ph.changed_at DESC LIMIT %s
            """,
            tuple(params),
        )
        return [dict(row) for row in rows]

    async def add_history(
        self,
        config_id: str,
        bidder_id: str,
        change_type: str,
        field_changed: str | None,
        old_value: str | None,
        new_value: str | None,
        changed_by: str | None,
        change_source: str,
        raw_config_snapshot: dict[str, Any] | None = None,
    ) -> int:
        return await pg_insert_returning_id(
            """
            INSERT INTO pretargeting_history
            (config_id, bidder_id, change_type, field_changed, old_value, new_value,
             changed_by, change_source, raw_config_snapshot, changed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            RETURNING id
            """,
            (
                config_id,
                bidder_id,
                change_type,
                field_changed,
                old_value,
                new_value,
                changed_by,
                change_source,
                raw_config_snapshot,
            ),
        )

    async def list_publishers(
        self,
        billing_id: str,
        mode: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        conditions = ["billing_id = %s"]
        params: list[Any] = [billing_id]

        if mode:
            conditions.append("mode = %s")
            params.append(mode)
        if status:
            conditions.append("status = %s")
            params.append(status)

        where_clause = " AND ".join(conditions)
        rows = await pg_query(
            f"""
            SELECT * FROM pretargeting_publishers
            WHERE {where_clause}
            ORDER BY publisher_id
            """,
            tuple(params),
        )
        return [dict(row) for row in rows]

    async def add_publisher(
        self,
        billing_id: str,
        publisher_id: str,
        mode: str,
        status: str = "active",
        source: str = "manual",
    ) -> int:
        return await pg_execute(
            """
            INSERT INTO pretargeting_publishers
            (billing_id, publisher_id, mode, status, source)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (billing_id, publisher_id, mode) DO UPDATE SET
                status = EXCLUDED.status,
                source = EXCLUDED.source,
                updated_at = NOW()
            """,
            (billing_id, publisher_id, mode, status, source),
        )

    async def update_publisher_status(
        self,
        billing_id: str,
        publisher_id: str,
        mode: str,
        status: str,
    ) -> int:
        return await pg_execute(
            """
            UPDATE pretargeting_publishers
            SET status = %s, updated_at = NOW()
            WHERE billing_id = %s AND publisher_id = %s AND mode = %s
            """,
            (status, billing_id, publisher_id, mode),
        )

    async def delete_publisher(self, billing_id: str, publisher_id: str, mode: str) -> int:
        return await pg_execute(
            "DELETE FROM pretargeting_publishers WHERE billing_id = %s AND publisher_id = %s AND mode = %s",
            (billing_id, publisher_id, mode),
        )

    async def clear_sync_publishers(self, billing_id: str) -> int:
        return await pg_execute(
            "DELETE FROM pretargeting_publishers WHERE billing_id = %s AND source = 'api_sync'",
            (billing_id,),
        )

    async def check_publisher_in_opposite_mode(
        self, billing_id: str, publisher_id: str, mode: str
    ) -> dict[str, Any] | None:
        return await pg_query_one(
            """
            SELECT mode FROM pretargeting_publishers
            WHERE billing_id = %s AND publisher_id = %s AND mode != %s
            """,
            (billing_id, publisher_id, mode),
        )

    async def list_pending_publisher_changes(self, billing_id: str) -> list[dict[str, Any]]:
        rows = await pg_query(
            """
            SELECT publisher_id, mode, status, source, updated_at
            FROM pretargeting_publishers
            WHERE billing_id = %s AND status IN ('pending_add', 'pending_remove')
            ORDER BY status, mode, publisher_id
            """,
            (billing_id,),
        )
        return [dict(row) for row in rows]

    async def get_publisher_rows(
        self, billing_id: str, publisher_id: str
    ) -> list[dict[str, Any]]:
        rows = await pg_query(
            """
            SELECT * FROM pretargeting_publishers
            WHERE billing_id = %s AND publisher_id = %s
            ORDER BY mode
            """,
            (billing_id, publisher_id),
        )
        return [dict(row) for row in rows]
