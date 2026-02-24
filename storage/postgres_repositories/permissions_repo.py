"""Postgres repository for user permissions (SQL only)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from storage.postgres_database import pg_query, pg_query_one, pg_execute


class PermissionsRepository:
    """SQL-only repository for user service account permissions."""

    async def grant_permission(
        self,
        permission_id: str,
        user_id: str,
        service_account_id: str,
        permission_level: str = "read",
        granted_by: Optional[str] = None,
    ) -> dict[str, Any]:
        """Grant a user access to a service account."""
        now = datetime.utcnow().isoformat()

        await pg_execute(
            """
            INSERT INTO user_service_account_permissions
            (id, user_id, service_account_id, permission_level, granted_by, granted_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, service_account_id)
            DO UPDATE SET
                permission_level = EXCLUDED.permission_level,
                granted_by = EXCLUDED.granted_by,
                granted_at = EXCLUDED.granted_at
            """,
            (permission_id, user_id, service_account_id, permission_level, granted_by, now),
        )

        return {
            "id": permission_id,
            "user_id": user_id,
            "service_account_id": service_account_id,
            "permission_level": permission_level,
            "granted_by": granted_by,
            "granted_at": now,
        }

    async def revoke_permission(
        self,
        user_id: str,
        service_account_id: str,
    ) -> bool:
        """Revoke a user's access to a service account. Returns True if revoked."""
        rowcount = await pg_execute(
            """
            DELETE FROM user_service_account_permissions
            WHERE user_id = %s AND service_account_id = %s
            """,
            (user_id, service_account_id),
        )
        return rowcount > 0

    async def get_user_permissions(self, user_id: str) -> list[dict[str, Any]]:
        """Get all permissions for a user."""
        return await pg_query(
            """
            SELECT id, user_id, service_account_id, permission_level, granted_by, granted_at
            FROM user_service_account_permissions
            WHERE user_id = %s
            """,
            (user_id,),
        )

    async def get_user_service_account_ids(
        self,
        user_id: str,
        min_permission_level: str = "read",
    ) -> list[str]:
        """Get service account IDs the user can access with at least the given permission level."""
        # Permission levels in order
        levels = ["read", "write", "admin"]
        min_index = levels.index(min_permission_level) if min_permission_level in levels else 0

        rows = await pg_query(
            """
            SELECT service_account_id, permission_level
            FROM user_service_account_permissions
            WHERE user_id = %s
            """,
            (user_id,),
        )

        # Filter by permission level
        result = []
        for row in rows:
            sa_id = row["service_account_id"]
            level = row["permission_level"]
            level_index = levels.index(level) if level in levels else -1
            if level_index >= min_index:
                result.append(sa_id)

        return result

    async def check_user_permission(
        self,
        user_id: str,
        service_account_id: str,
        required_level: str = "read",
    ) -> bool:
        """Check if a user has the required permission for a service account."""
        levels = ["read", "write", "admin"]
        required_index = levels.index(required_level) if required_level in levels else 0

        row = await pg_query_one(
            """
            SELECT permission_level
            FROM user_service_account_permissions
            WHERE user_id = %s AND service_account_id = %s
            """,
            (user_id, service_account_id),
        )

        if row:
            user_level = row["permission_level"]
            user_index = levels.index(user_level) if user_level in levels else -1
            return user_index >= required_index
        return False

    # ==================== Explicit Buyer Seat Permissions ====================

    async def grant_buyer_seat_permission(
        self,
        permission_id: str,
        user_id: str,
        buyer_id: str,
        access_level: str = "read",
        granted_by: Optional[str] = None,
    ) -> dict[str, Any]:
        """Grant a user explicit access to a buyer seat."""
        now = datetime.utcnow().isoformat()

        await pg_execute(
            """
            INSERT INTO user_buyer_seat_permissions
            (id, user_id, buyer_id, access_level, granted_by, granted_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, buyer_id)
            DO UPDATE SET
                access_level = EXCLUDED.access_level,
                granted_by = EXCLUDED.granted_by,
                granted_at = EXCLUDED.granted_at
            """,
            (permission_id, user_id, buyer_id, access_level, granted_by, now),
        )

        row = await pg_query_one(
            """
            SELECT ubsp.id, ubsp.user_id, ubsp.buyer_id, ubsp.access_level,
                   ubsp.granted_by, ubsp.granted_at,
                   bs.display_name as buyer_display_name,
                   bs.bidder_id,
                   bs.active
            FROM user_buyer_seat_permissions ubsp
            LEFT JOIN buyer_seats bs ON bs.buyer_id = ubsp.buyer_id
            WHERE ubsp.user_id = %s AND ubsp.buyer_id = %s
            """,
            (user_id, buyer_id),
        )
        if row is None:
            raise RuntimeError("Failed to load buyer seat permission after upsert")
        return row

    async def revoke_buyer_seat_permission(
        self,
        user_id: str,
        buyer_id: str,
    ) -> bool:
        """Revoke a user's explicit access to a buyer seat."""
        rowcount = await pg_execute(
            """
            DELETE FROM user_buyer_seat_permissions
            WHERE user_id = %s AND buyer_id = %s
            """,
            (user_id, buyer_id),
        )
        return rowcount > 0

    async def get_user_buyer_seat_permissions(self, user_id: str) -> list[dict[str, Any]]:
        """Get all explicit buyer seat permissions for a user."""
        return await pg_query(
            """
            SELECT ubsp.id, ubsp.user_id, ubsp.buyer_id, ubsp.access_level,
                   ubsp.granted_by, ubsp.granted_at,
                   bs.display_name as buyer_display_name,
                   bs.bidder_id,
                   bs.active
            FROM user_buyer_seat_permissions ubsp
            LEFT JOIN buyer_seats bs ON bs.buyer_id = ubsp.buyer_id
            WHERE ubsp.user_id = %s
            ORDER BY COALESCE(bs.display_name, ubsp.buyer_id), ubsp.buyer_id
            """,
            (user_id,),
        )

    async def get_user_buyer_seat_ids(
        self,
        user_id: str,
        min_access_level: str = "read",
    ) -> list[str]:
        """Get explicit buyer IDs a user can access with at least the given level."""
        levels = ["read", "admin"]
        min_index = levels.index(min_access_level) if min_access_level in levels else 0

        rows = await pg_query(
            """
            SELECT ubsp.buyer_id, ubsp.access_level
            FROM user_buyer_seat_permissions ubsp
            JOIN buyer_seats bs ON bs.buyer_id = ubsp.buyer_id
            WHERE ubsp.user_id = %s
              AND COALESCE(bs.active, true) = true
            """,
            (user_id,),
        )

        result: list[str] = []
        for row in rows:
            level = row["access_level"]
            level_index = levels.index(level) if level in levels else -1
            if level_index >= min_index:
                result.append(row["buyer_id"])
        return result
