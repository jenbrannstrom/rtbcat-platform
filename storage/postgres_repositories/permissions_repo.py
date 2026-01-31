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
