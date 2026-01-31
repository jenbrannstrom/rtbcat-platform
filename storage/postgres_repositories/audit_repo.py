"""Postgres repository for audit logs and system settings (SQL only)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

from storage.postgres_database import pg_query, pg_query_one, pg_execute


class AuditRepository:
    """SQL-only repository for audit logging and system settings."""

    # ==================== Audit Log Methods ====================

    async def log_audit(
        self,
        audit_id: str,
        action: str,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> dict[str, Any]:
        """Create an audit log entry."""
        now = datetime.utcnow().isoformat()

        await pg_execute(
            """
            INSERT INTO audit_log (id, user_id, action, resource_type, resource_id, details, ip_address, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (audit_id, user_id, action, resource_type, resource_id, details, ip_address, now),
        )

        return {
            "id": audit_id,
            "action": action,
            "user_id": user_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "details": details,
            "ip_address": ip_address,
            "created_at": now,
        }

    async def get_audit_logs(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        since_days: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Get audit log entries with optional filters."""
        conditions = []
        params: list[Any] = []

        if user_id:
            conditions.append("user_id = %s")
            params.append(user_id)
        if action:
            conditions.append("action = %s")
            params.append(action)
        if resource_type:
            conditions.append("resource_type = %s")
            params.append(resource_type)
        if since_days:
            since = (datetime.utcnow() - timedelta(days=since_days)).isoformat()
            conditions.append("created_at > %s")
            params.append(since)

        where_clause = " AND ".join(conditions) if conditions else "TRUE"
        params.extend([limit, offset])

        return await pg_query(
            f"""
            SELECT id, user_id, action, resource_type, resource_id, details, ip_address, created_at
            FROM audit_log
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            tuple(params),
        )

    async def cleanup_old_audit_logs(self, retention_days: int) -> int:
        """Delete audit logs older than retention period. Returns count deleted."""
        if retention_days <= 0:
            return 0

        cutoff = (datetime.utcnow() - timedelta(days=retention_days)).isoformat()
        return await pg_execute(
            "DELETE FROM audit_log WHERE created_at < %s",
            (cutoff,),
        )

    # ==================== Settings Methods ====================

    async def get_setting(self, key: str) -> Optional[str]:
        """Get a system setting value."""
        row = await pg_query_one(
            "SELECT value FROM system_settings WHERE key = %s",
            (key,),
        )
        return row["value"] if row else None

    async def set_setting(
        self,
        key: str,
        value: str,
        updated_by: Optional[str] = None,
    ) -> None:
        """Set a system setting value."""
        now = datetime.utcnow().isoformat()
        await pg_execute(
            """
            INSERT INTO system_settings (key, value, updated_at, updated_by)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (key)
            DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at, updated_by = EXCLUDED.updated_by
            """,
            (key, value, now, updated_by),
        )

    async def get_all_settings(self) -> dict[str, str]:
        """Get all system settings."""
        rows = await pg_query("SELECT key, value FROM system_settings")
        return {row["key"]: row["value"] for row in rows}

    async def is_multi_user_enabled(self) -> bool:
        """Check if multi-user mode is enabled."""
        value = await self.get_setting("multi_user_enabled")
        return value == "1" if value else True
