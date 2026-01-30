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
                "SELECT * FROM pretargeting_configs WHERE bidder_id = %s ORDER BY billing_id",
                (bidder_id,),
            )
        return await pg_query(
            "SELECT * FROM pretargeting_configs ORDER BY billing_id"
        )

    async def get_config_by_billing_id(self, billing_id: str) -> dict[str, Any] | None:
        return await pg_query_one(
            "SELECT * FROM pretargeting_configs WHERE billing_id = %s",
            (billing_id,),
        )

    async def save_config(self, config: dict[str, Any]) -> None:
        await pg_execute(
            """
            INSERT INTO pretargeting_configs
            (config_id, billing_id, name, user_name, state, bidder_id,
             query_targeting, geo_targeting, language_targeting, technology_targeting,
             inventory_targeting, creative_size_targeting, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, NOW(), NOW())
            ON CONFLICT (config_id) DO UPDATE SET
                name = EXCLUDED.name,
                user_name = EXCLUDED.user_name,
                state = EXCLUDED.state,
                bidder_id = EXCLUDED.bidder_id,
                query_targeting = EXCLUDED.query_targeting,
                geo_targeting = EXCLUDED.geo_targeting,
                language_targeting = EXCLUDED.language_targeting,
                technology_targeting = EXCLUDED.technology_targeting,
                inventory_targeting = EXCLUDED.inventory_targeting,
                creative_size_targeting = EXCLUDED.creative_size_targeting,
                updated_at = NOW()
            """,
            (
                config.get("config_id"),
                config.get("billing_id"),
                config.get("name"),
                config.get("user_name"),
                config.get("state"),
                config.get("bidder_id"),
                config.get("query_targeting"),
                config.get("geo_targeting"),
                config.get("language_targeting"),
                config.get("technology_targeting"),
                config.get("inventory_targeting"),
                config.get("creative_size_targeting"),
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

    async def list_history(self, billing_id: str, limit: int = 100) -> list[dict[str, Any]]:
        return await pg_query(
            """
            SELECT ph.* FROM pretargeting_history ph
            LEFT JOIN pretargeting_configs pc ON ph.config_id = pc.config_id
            WHERE pc.billing_id = %s
            ORDER BY ph.created_at DESC
            LIMIT %s
            """,
            (billing_id, limit),
        )

    async def add_history(
        self,
        config_id: int,
        user_id: str,
        action: str,
        summary: str,
        details: dict[str, Any],
    ) -> int:
        return await pg_insert_returning_id(
            """
            INSERT INTO pretargeting_history
            (config_id, user_id, action, summary, details)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (config_id, user_id, action, summary, details),
        )

    async def list_publishers(self, billing_id: str, mode: str | None = None) -> list[dict[str, Any]]:
        if mode:
            return await pg_query(
                """
                SELECT * FROM pretargeting_publishers
                WHERE billing_id = %s AND mode = %s
                ORDER BY publisher_id
                """,
                (billing_id, mode),
            )
        return await pg_query(
            """
            SELECT * FROM pretargeting_publishers
            WHERE billing_id = %s
            ORDER BY publisher_id
            """,
            (billing_id,),
        )

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
