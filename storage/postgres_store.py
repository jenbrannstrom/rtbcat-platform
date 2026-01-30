"""PostgreSQL storage backend for Cat-Scan.

This module provides the PostgresStore class which mirrors the SQLiteStore API.
Currently contains stubs - full implementation will be done incrementally.

Usage:
    >>> from storage.postgres_store import PostgresStore
    >>>
    >>> store = PostgresStore()
    >>> await store.initialize()
    >>>
    >>> # API matches SQLiteStore
    >>> await store.save_creatives(creatives)
    >>> html_creatives = await store.list_creatives(format="HTML")

Environment:
    POSTGRES_DSN or DATABASE_URL must be set.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Optional

from .postgres_database import (
    pg_query,
    pg_query_one,
    pg_execute,
    pg_execute_many,
    pg_transaction_async,
    init_postgres_database,
)

# Import models from centralized location
from .models import (
    Creative,
    Campaign,
    Cluster,
    ServiceAccount,
    BuyerSeat,
    PerformanceMetric,
)

# Import user models from user_repository for Tier 1 auth support
from .repositories.user_repository import (
    User,
    UserSession,
    UserPermission,
    AuditLogEntry,
)

if TYPE_CHECKING:
    from collectors.creatives.schemas import CreativeDict

logger = logging.getLogger(__name__)


# Re-export models for backward compatibility
__all__ = [
    "PostgresStore",
    "Creative",
    "Campaign",
    "Cluster",
    "ServiceAccount",
    "BuyerSeat",
    "PerformanceMetric",
    "User",
    "UserSession",
    "UserPermission",
    "AuditLogEntry",
]


class PostgresStore:
    """Async PostgreSQL storage for creative intelligence data.

    Provides CRUD operations for creatives, campaigns, and clusters
    with support for search and filtering.

    This class mirrors the SQLiteStore API for drop-in replacement.
    Many methods are currently stubs marked with TODO.
    """

    def __init__(self) -> None:
        """Initialize the PostgreSQL store.

        Connection parameters are read from POSTGRES_DSN or DATABASE_URL
        environment variables.
        """
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the database schema.

        Runs pending migrations if needed.
        """
        if self._initialized:
            return

        await init_postgres_database()
        self._initialized = True
        logger.info("PostgresStore initialized")

    # =========================================================================
    # CREATIVE OPERATIONS
    # =========================================================================

    async def save_creatives(self, creatives: list["CreativeDict"]) -> int:
        """Save or update multiple creatives.

        TODO: Implement full upsert logic with JSONB fields.
        """
        # TODO: Implement - stub for now
        logger.warning("PostgresStore.save_creatives() is a stub")
        return 0

    async def get_creative(self, creative_id: str) -> Optional[Creative]:
        """Get a creative by ID."""
        row = await pg_query_one(
            "SELECT * FROM creatives WHERE id = %s",
            (creative_id,)
        )
        if row:
            return Creative(**row)
        return None

    async def list_creatives(
        self,
        limit: int = 100,
        offset: int = 0,
        format: Optional[str] = None,
        campaign_id: Optional[str] = None,
        buyer_id: Optional[str] = None,
        approval_status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> list[Creative]:
        """List creatives with optional filters.

        TODO: Implement full filtering logic.
        """
        # TODO: Implement full filtering - basic version for now
        sql = "SELECT * FROM creatives"
        params: list[Any] = []
        conditions = []

        if format:
            conditions.append("format = %s")
            params.append(format)
        if buyer_id:
            conditions.append("buyer_id = %s")
            params.append(buyer_id)
        if approval_status:
            conditions.append("approval_status = %s")
            params.append(approval_status)

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        sql += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        rows = await pg_query(sql, tuple(params))
        return [Creative(**row) for row in rows]

    async def get_creative_count(
        self,
        buyer_id: Optional[str] = None,
        format: Optional[str] = None,
    ) -> int:
        """Get total count of creatives matching filters."""
        sql = "SELECT COUNT(*) as count FROM creatives"
        params: list[Any] = []
        conditions = []

        if buyer_id:
            conditions.append("buyer_id = %s")
            params.append(buyer_id)
        if format:
            conditions.append("format = %s")
            params.append(format)

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        row = await pg_query_one(sql, tuple(params))
        return row["count"] if row else 0

    async def delete_creative(self, creative_id: str) -> bool:
        """Delete a creative by ID."""
        rows = await pg_execute(
            "DELETE FROM creatives WHERE id = %s",
            (creative_id,)
        )
        return rows > 0

    # =========================================================================
    # BUYER SEAT OPERATIONS
    # =========================================================================

    async def get_buyer_seats(
        self,
        bidder_id: Optional[str] = None,
        active_only: bool = False,
    ) -> list[BuyerSeat]:
        """Get all buyer seats, optionally filtered by bidder."""
        conditions = []
        params: list[Any] = []

        if bidder_id:
            conditions.append("bidder_id = %s")
            params.append(bidder_id)
        if active_only:
            conditions.append("active = 1")

        sql = "SELECT * FROM buyer_seats"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY display_name"

        rows = await pg_query(sql, tuple(params) if params else ())
        return [BuyerSeat(**row) for row in rows]

    async def get_buyer_seats_for_service_accounts(
        self,
        service_account_ids: list[str],
        bidder_id: Optional[str] = None,
        active_only: bool = False,
    ) -> list[BuyerSeat]:
        """Get buyer seats for specific service accounts."""
        if not service_account_ids:
            return []

        placeholders = ", ".join(["%s"] * len(service_account_ids))
        conditions = [f"service_account_id IN ({placeholders})"]
        params: list[Any] = list(service_account_ids)

        if bidder_id:
            conditions.append("bidder_id = %s")
            params.append(bidder_id)
        if active_only:
            conditions.append("active = 1")

        sql = "SELECT * FROM buyer_seats WHERE " + " AND ".join(conditions)
        sql += " ORDER BY display_name"

        rows = await pg_query(sql, tuple(params))
        return [BuyerSeat(**row) for row in rows]

    async def get_buyer_seat(self, buyer_id: str) -> Optional[BuyerSeat]:
        """Get a buyer seat by ID."""
        row = await pg_query_one(
            "SELECT * FROM buyer_seats WHERE buyer_id = %s",
            (buyer_id,)
        )
        return BuyerSeat(**row) if row else None

    async def save_buyer_seat(self, seat: BuyerSeat) -> None:
        """Save or update a buyer seat."""
        await pg_execute(
            """
            INSERT INTO buyer_seats (buyer_id, bidder_id, service_account_id, display_name,
                                     active, creative_count, last_synced, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (buyer_id) DO UPDATE SET
                bidder_id = EXCLUDED.bidder_id,
                service_account_id = EXCLUDED.service_account_id,
                display_name = EXCLUDED.display_name,
                active = EXCLUDED.active,
                creative_count = EXCLUDED.creative_count,
                last_synced = EXCLUDED.last_synced
            """,
            (
                seat.buyer_id,
                seat.bidder_id,
                seat.service_account_id,
                seat.display_name,
                1 if seat.active else 0,
                seat.creative_count or 0,
                seat.last_synced,
            ),
        )

    async def get_buyer_ids_for_service_accounts(
        self, service_account_ids: list[str]
    ) -> list[str]:
        """Get buyer IDs associated with service accounts."""
        if not service_account_ids:
            return []
        placeholders = ", ".join(["%s"] * len(service_account_ids))
        rows = await pg_query(
            f"SELECT buyer_id FROM buyer_seats WHERE service_account_id IN ({placeholders})",
            tuple(service_account_ids)
        )
        return [row["buyer_id"] for row in rows]

    async def get_bidder_ids_for_buyer_ids(self, buyer_ids: list[str]) -> list[str]:
        """Get bidder IDs for given buyer IDs."""
        if not buyer_ids:
            return []
        placeholders = ", ".join(["%s"] * len(buyer_ids))
        rows = await pg_query(
            f"SELECT DISTINCT bidder_id FROM buyer_seats WHERE buyer_id IN ({placeholders})",
            tuple(buyer_ids)
        )
        return [row["bidder_id"] for row in rows]

    async def link_buyer_seat_to_service_account(
        self,
        buyer_id: str,
        service_account_id: str,
    ) -> None:
        """Link a buyer seat to a service account."""
        await pg_execute(
            "UPDATE buyer_seats SET service_account_id = %s WHERE buyer_id = %s",
            (service_account_id, buyer_id)
        )

    async def update_buyer_seat_display_name(
        self, buyer_id: str, display_name: str
    ) -> bool:
        """Update the display name for a buyer seat."""
        rows = await pg_execute(
            "UPDATE buyer_seats SET display_name = %s WHERE buyer_id = %s",
            (display_name, buyer_id)
        )
        return rows > 0

    async def update_seat_creative_count(self, buyer_id: str) -> int:
        """Update the creative_count for a buyer seat from creatives table."""
        row = await pg_query_one(
            "SELECT COUNT(*) as count FROM creatives WHERE buyer_id = %s",
            (buyer_id,)
        )
        count = row["count"] if row else 0
        await pg_execute(
            "UPDATE buyer_seats SET creative_count = %s WHERE buyer_id = %s",
            (count, buyer_id)
        )
        return count

    async def update_seat_sync_time(self, buyer_id: str) -> None:
        """Update last_synced timestamp for a buyer seat."""
        await pg_execute(
            "UPDATE buyer_seats SET last_synced = CURRENT_TIMESTAMP WHERE buyer_id = %s",
            (buyer_id,)
        )

    async def populate_buyer_seats_from_creatives(self) -> int:
        """Populate buyer_seats table from existing creatives."""
        # Get distinct buyer_ids from creatives that don't have seats yet
        rows = await pg_query(
            """
            SELECT DISTINCT c.buyer_id, c.account_id as bidder_id
            FROM creatives c
            LEFT JOIN buyer_seats bs ON c.buyer_id = bs.buyer_id
            WHERE bs.buyer_id IS NULL AND c.buyer_id IS NOT NULL
            """
        )

        count = 0
        for row in rows:
            await pg_execute(
                """
                INSERT INTO buyer_seats (buyer_id, bidder_id, active, created_at)
                VALUES (%s, %s, 1, CURRENT_TIMESTAMP)
                ON CONFLICT (buyer_id) DO NOTHING
                """,
                (row["buyer_id"], row["bidder_id"])
            )
            count += 1

        return count

    # =========================================================================
    # SERVICE ACCOUNT OPERATIONS
    # =========================================================================

    async def get_service_accounts(
        self, active_only: bool = False
    ) -> list[ServiceAccount]:
        """Get all service accounts."""
        if active_only:
            rows = await pg_query(
                "SELECT * FROM service_accounts WHERE is_active = 1 ORDER BY display_name"
            )
        else:
            rows = await pg_query("SELECT * FROM service_accounts ORDER BY display_name")
        return [ServiceAccount(**row) for row in rows]

    async def get_service_account(self, account_id: str) -> Optional[ServiceAccount]:
        """Get a service account by ID."""
        row = await pg_query_one(
            "SELECT * FROM service_accounts WHERE id = %s",
            (account_id,)
        )
        return ServiceAccount(**row) if row else None

    async def get_service_account_by_email(
        self, client_email: str
    ) -> Optional[ServiceAccount]:
        """Get a service account by its client email."""
        row = await pg_query_one(
            "SELECT * FROM service_accounts WHERE client_email = %s",
            (client_email,)
        )
        return ServiceAccount(**row) if row else None

    async def save_service_account(self, account: ServiceAccount) -> None:
        """Insert or update a service account."""
        await pg_execute(
            """
            INSERT INTO service_accounts (id, client_email, project_id, display_name,
                                          credentials_path, is_active, created_at, last_used)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s)
            ON CONFLICT (id) DO UPDATE SET
                client_email = EXCLUDED.client_email,
                project_id = EXCLUDED.project_id,
                display_name = EXCLUDED.display_name,
                credentials_path = EXCLUDED.credentials_path,
                is_active = EXCLUDED.is_active,
                last_used = EXCLUDED.last_used
            """,
            (
                account.id,
                account.client_email,
                account.project_id,
                account.display_name,
                account.credentials_path,
                1 if account.is_active else 0,
                account.last_used,
            ),
        )

    async def delete_service_account(self, account_id: str) -> bool:
        """Delete a service account."""
        rows = await pg_execute(
            "DELETE FROM service_accounts WHERE id = %s",
            (account_id,)
        )
        return rows > 0

    async def update_service_account_last_used(self, account_id: str) -> None:
        """Update last_used timestamp for a service account."""
        await pg_execute(
            "UPDATE service_accounts SET last_used = CURRENT_TIMESTAMP WHERE id = %s",
            (account_id,)
        )

    # =========================================================================
    # USER OPERATIONS (Tier 1)
    # =========================================================================

    async def create_user(
        self,
        user_id: str,
        email: str,
        display_name: Optional[str] = None,
        role: str = "user",
        default_language: str = "en",
    ) -> User:
        """Create a new user."""
        now = datetime.utcnow().isoformat()
        await pg_execute(
            """
            INSERT INTO users (id, email, display_name, role, is_active, created_at, default_language)
            VALUES (%s, %s, %s, %s, 1, %s, %s)
            """,
            (user_id, email, display_name, role, now, default_language),
        )
        return User(
            id=user_id,
            email=email,
            display_name=display_name,
            role=role,
            is_active=True,
            created_at=now,
            default_language=default_language,
        )

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get a user by ID."""
        row = await pg_query_one(
            """
            SELECT id, email, display_name, role, is_active, created_at,
                   updated_at, last_login_at, default_language
            FROM users WHERE id = %s
            """,
            (user_id,),
        )
        if row:
            return User(
                id=row["id"],
                email=row["email"],
                display_name=row["display_name"],
                role=row["role"],
                is_active=bool(row["is_active"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                last_login_at=row["last_login_at"],
                default_language=row["default_language"],
            )
        return None

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get a user by email address."""
        row = await pg_query_one(
            """
            SELECT id, email, display_name, role, is_active, created_at,
                   updated_at, last_login_at, default_language
            FROM users WHERE email = %s
            """,
            (email,),
        )
        if row:
            return User(
                id=row["id"],
                email=row["email"],
                display_name=row["display_name"],
                role=row["role"],
                is_active=bool(row["is_active"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                last_login_at=row["last_login_at"],
                default_language=row["default_language"],
            )
        return None

    async def get_users(
        self,
        active_only: bool = False,
        role: Optional[str] = None,
    ) -> list[User]:
        """Get all users, optionally filtered."""
        conditions = []
        params: list[Any] = []

        if active_only:
            conditions.append("is_active = 1")
        if role:
            conditions.append("role = %s")
            params.append(role)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"""
            SELECT id, email, display_name, role, is_active, created_at,
                   updated_at, last_login_at, default_language
            FROM users WHERE {where_clause} ORDER BY created_at DESC
        """
        rows = await pg_query(sql, tuple(params) if params else ())
        return [
            User(
                id=row["id"],
                email=row["email"],
                display_name=row["display_name"],
                role=row["role"],
                is_active=bool(row["is_active"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                last_login_at=row["last_login_at"],
                default_language=row["default_language"],
            )
            for row in rows
        ]

    async def update_user(
        self,
        user_id: str,
        display_name: Optional[str] = None,
        role: Optional[str] = None,
        is_active: Optional[bool] = None,
        default_language: Optional[str] = None,
    ) -> bool:
        """Update a user's fields."""
        updates = []
        params: list[Any] = []

        if display_name is not None:
            updates.append("display_name = %s")
            params.append(display_name)
        if role is not None:
            updates.append("role = %s")
            params.append(role)
        if is_active is not None:
            updates.append("is_active = %s")
            params.append(1 if is_active else 0)
        if default_language is not None:
            updates.append("default_language = %s")
            params.append(default_language)

        if not updates:
            return False

        updates.append("updated_at = %s")
        params.append(datetime.utcnow().isoformat())
        params.append(user_id)

        sql = f"UPDATE users SET {', '.join(updates)} WHERE id = %s"
        rows = await pg_execute(sql, tuple(params))
        return rows > 0

    async def update_last_login(self, user_id: str) -> None:
        """Update user's last login timestamp."""
        await pg_execute(
            "UPDATE users SET last_login_at = %s WHERE id = %s",
            (datetime.utcnow().isoformat(), user_id),
        )

    async def count_users(self) -> int:
        """Count total number of users."""
        row = await pg_query_one("SELECT COUNT(*) as count FROM users")
        return row["count"] if row else 0

    # =========================================================================
    # SESSION OPERATIONS (Tier 1)
    # =========================================================================

    async def create_session(
        self,
        session_id: str,
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        duration_days: int = 30,
    ) -> UserSession:
        """Create a new session for a user."""
        now = datetime.utcnow()
        expires_at = now + timedelta(days=duration_days)

        await pg_execute(
            """
            INSERT INTO user_sessions (id, user_id, created_at, expires_at, ip_address, user_agent)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                session_id,
                user_id,
                now.isoformat(),
                expires_at.isoformat(),
                ip_address,
                user_agent,
            ),
        )
        return UserSession(
            id=session_id,
            user_id=user_id,
            created_at=now.isoformat(),
            expires_at=expires_at.isoformat(),
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def get_session(self, session_id: str) -> Optional[UserSession]:
        """Get a session by ID."""
        row = await pg_query_one(
            """
            SELECT id, user_id, created_at, expires_at, ip_address, user_agent
            FROM user_sessions WHERE id = %s
            """,
            (session_id,),
        )
        if row:
            return UserSession(
                id=row["id"],
                user_id=row["user_id"],
                created_at=str(row["created_at"]) if row["created_at"] else "",
                expires_at=str(row["expires_at"]) if row["expires_at"] else "",
                ip_address=row["ip_address"],
                user_agent=row["user_agent"],
            )
        return None

    async def validate_session(self, session_id: str) -> Optional[User]:
        """Validate a session and return the associated user."""
        now = datetime.utcnow().isoformat()
        row = await pg_query_one(
            """
            SELECT u.id, u.email, u.display_name, u.role, u.is_active,
                   u.created_at, u.updated_at, u.last_login_at, u.default_language
            FROM user_sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.id = %s AND s.expires_at > %s AND u.is_active = 1
            """,
            (session_id, now),
        )
        if row:
            return User(
                id=row["id"],
                email=row["email"],
                display_name=row["display_name"],
                role=row["role"],
                is_active=bool(row["is_active"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                last_login_at=row["last_login_at"],
                default_language=row["default_language"],
            )
        return None

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session (logout)."""
        rows = await pg_execute(
            "DELETE FROM user_sessions WHERE id = %s",
            (session_id,),
        )
        return rows > 0

    async def delete_user_sessions(self, user_id: str) -> int:
        """Delete all sessions for a user."""
        return await pg_execute(
            "DELETE FROM user_sessions WHERE user_id = %s",
            (user_id,),
        )

    async def cleanup_expired_sessions(self) -> int:
        """Delete all expired sessions."""
        now = datetime.utcnow().isoformat()
        return await pg_execute(
            "DELETE FROM user_sessions WHERE expires_at < %s",
            (now,),
        )

    # =========================================================================
    # PERMISSION OPERATIONS (Tier 1)
    # =========================================================================

    async def grant_permission(
        self,
        permission_id: str,
        user_id: str,
        service_account_id: str,
        permission_level: str = "read",
        granted_by: Optional[str] = None,
    ) -> UserPermission:
        """Grant a user access to a service account."""
        now = datetime.utcnow().isoformat()
        await pg_execute(
            """
            INSERT INTO user_service_account_permissions
            (id, user_id, service_account_id, permission_level, granted_by, granted_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, service_account_id) DO UPDATE SET
                permission_level = EXCLUDED.permission_level,
                granted_by = EXCLUDED.granted_by,
                granted_at = EXCLUDED.granted_at
            """,
            (permission_id, user_id, service_account_id, permission_level, granted_by, now),
        )
        return UserPermission(
            id=permission_id,
            user_id=user_id,
            service_account_id=service_account_id,
            permission_level=permission_level,
            granted_by=granted_by,
            granted_at=now,
        )

    async def revoke_permission(
        self,
        user_id: str,
        service_account_id: str,
    ) -> bool:
        """Revoke a user's access to a service account."""
        rows = await pg_execute(
            """
            DELETE FROM user_service_account_permissions
            WHERE user_id = %s AND service_account_id = %s
            """,
            (user_id, service_account_id),
        )
        return rows > 0

    async def get_user_permissions(self, user_id: str) -> list[UserPermission]:
        """Get all permissions for a user."""
        rows = await pg_query(
            """
            SELECT id, user_id, service_account_id, permission_level, granted_by, granted_at
            FROM user_service_account_permissions WHERE user_id = %s
            """,
            (user_id,),
        )
        return [
            UserPermission(
                id=row["id"],
                user_id=row["user_id"],
                service_account_id=row["service_account_id"],
                permission_level=row["permission_level"],
                granted_by=row["granted_by"],
                granted_at=str(row["granted_at"]) if row["granted_at"] else None,
            )
            for row in rows
        ]

    async def get_user_service_account_ids(
        self,
        user_id: str,
        min_permission_level: str = "read",
    ) -> list[str]:
        """Get service account IDs the user can access."""
        levels = ["read", "write", "admin"]
        min_index = levels.index(min_permission_level) if min_permission_level in levels else 0

        rows = await pg_query(
            """
            SELECT service_account_id, permission_level
            FROM user_service_account_permissions WHERE user_id = %s
            """,
            (user_id,),
        )
        result = []
        for row in rows:
            level = row["permission_level"]
            level_index = levels.index(level) if level in levels else -1
            if level_index >= min_index:
                result.append(row["service_account_id"])
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

    # =========================================================================
    # SYSTEM SETTINGS OPERATIONS (Tier 1)
    # =========================================================================

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
            ON CONFLICT (key) DO UPDATE SET
                value = EXCLUDED.value,
                updated_at = EXCLUDED.updated_at,
                updated_by = EXCLUDED.updated_by
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

    # =========================================================================
    # AUDIT LOG OPERATIONS (Tier 1)
    # =========================================================================

    async def log_audit(
        self,
        audit_id: str,
        action: str,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLogEntry:
        """Create an audit log entry."""
        now = datetime.utcnow().isoformat()
        await pg_execute(
            """
            INSERT INTO audit_log (id, user_id, action, resource_type, resource_id, details, ip_address, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (audit_id, user_id, action, resource_type, resource_id, details, ip_address, now),
        )
        return AuditLogEntry(
            id=audit_id,
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            created_at=now,
        )

    async def get_audit_logs(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        since_days: Optional[int] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLogEntry]:
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

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.extend([limit, offset])

        sql = f"""
            SELECT id, user_id, action, resource_type, resource_id, details, ip_address, created_at
            FROM audit_log WHERE {where_clause}
            ORDER BY created_at DESC LIMIT %s OFFSET %s
        """
        rows = await pg_query(sql, tuple(params))
        return [
            AuditLogEntry(
                id=row["id"],
                user_id=row["user_id"],
                action=row["action"],
                resource_type=row["resource_type"],
                resource_id=row["resource_id"],
                details=row["details"],
                ip_address=row["ip_address"],
                created_at=str(row["created_at"]) if row["created_at"] else None,
            )
            for row in rows
        ]

    async def cleanup_old_audit_logs(self, retention_days: int) -> int:
        """Delete audit logs older than retention period."""
        if retention_days <= 0:
            return 0
        cutoff = (datetime.utcnow() - timedelta(days=retention_days)).isoformat()
        return await pg_execute(
            "DELETE FROM audit_log WHERE created_at < %s",
            (cutoff,),
        )

    # =========================================================================
    # CAMPAIGN OPERATIONS
    # =========================================================================

    async def get_campaigns(self, limit: int = 100) -> list[Campaign]:
        """Get all campaigns."""
        rows = await pg_query(
            "SELECT * FROM campaigns ORDER BY created_at DESC LIMIT %s",
            (limit,)
        )
        return [Campaign(**row) for row in rows]

    async def get_campaign(self, campaign_id: str) -> Optional[Campaign]:
        """Get a campaign by ID."""
        row = await pg_query_one(
            "SELECT * FROM campaigns WHERE id = %s",
            (campaign_id,)
        )
        return Campaign(**row) if row else None

    # =========================================================================
    # STATISTICS
    # =========================================================================

    async def get_stats(self) -> dict[str, Any]:
        """Get database statistics."""
        stats = {}

        # Creative counts
        row = await pg_query_one("SELECT COUNT(*) as count FROM creatives")
        stats["total_creatives"] = row["count"] if row else 0

        # Format breakdown
        rows = await pg_query(
            "SELECT format, COUNT(*) as count FROM creatives GROUP BY format"
        )
        stats["by_format"] = {row["format"]: row["count"] for row in rows}

        # Buyer seat count
        row = await pg_query_one("SELECT COUNT(*) as count FROM buyer_seats")
        stats["total_buyer_seats"] = row["count"] if row else 0

        return stats

    # =========================================================================
    # STUB METHODS - TODO: Implement these
    # =========================================================================

    async def save_campaign(self, campaign: Campaign) -> None:
        """Save or update a campaign. TODO: Implement."""
        logger.warning("PostgresStore.save_campaign() is a stub")

    async def save_cluster(self, cluster: Cluster) -> None:
        """Save or update a cluster. TODO: Implement."""
        logger.warning("PostgresStore.save_cluster() is a stub")

    async def get_clusters(self) -> list[Cluster]:
        """Get all clusters. TODO: Implement."""
        logger.warning("PostgresStore.get_clusters() is a stub")
        return []

    async def save_performance_metrics(self, metrics: list[PerformanceMetric]) -> int:
        """Save performance metrics. TODO: Implement."""
        logger.warning("PostgresStore.save_performance_metrics() is a stub")
        return 0

    async def get_performance_metrics(
        self,
        creative_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[PerformanceMetric]:
        """Get performance metrics. TODO: Implement."""
        logger.warning("PostgresStore.get_performance_metrics() is a stub")
        return []

    # =========================================================================
    # RTB TRAFFIC - STUB
    # =========================================================================

    async def save_rtb_traffic(self, traffic_data: list[dict]) -> int:
        """Save RTB traffic data. TODO: Implement."""
        logger.warning("PostgresStore.save_rtb_traffic() is a stub")
        return 0

    async def get_rtb_traffic(
        self,
        buyer_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> list[dict]:
        """Get RTB traffic data. TODO: Implement."""
        logger.warning("PostgresStore.get_rtb_traffic() is a stub")
        return []

    # =========================================================================
    # PRETARGETING - STUB
    # =========================================================================

    async def get_pretargeting_configs(
        self, bidder_id: Optional[str] = None
    ) -> list[dict]:
        """Get pretargeting configs. TODO: Implement."""
        logger.warning("PostgresStore.get_pretargeting_configs() is a stub")
        return []

    async def save_pretargeting_config(self, config: dict) -> None:
        """Save pretargeting config. TODO: Implement."""
        logger.warning("PostgresStore.save_pretargeting_config() is a stub")

    # =========================================================================
    # IMPORT HISTORY - STUB
    # =========================================================================

    async def save_import_history(self, history: dict) -> int:
        """Save import history record. TODO: Implement."""
        logger.warning("PostgresStore.save_import_history() is a stub")
        return 0

    async def get_import_history(self, limit: int = 100) -> list[dict]:
        """Get import history. TODO: Implement."""
        logger.warning("PostgresStore.get_import_history() is a stub")
        return []

    # =========================================================================
    # THUMBNAIL STATUS - STUB
    # =========================================================================

    async def get_thumbnail_status(self, creative_id: str) -> Optional[dict]:
        """Get thumbnail status for a creative. TODO: Implement."""
        logger.warning("PostgresStore.get_thumbnail_status() is a stub")
        return None

    async def save_thumbnail_status(
        self, creative_id: str, status: str, error_reason: Optional[str] = None
    ) -> None:
        """Save thumbnail generation status. TODO: Implement."""
        logger.warning("PostgresStore.save_thumbnail_status() is a stub")
