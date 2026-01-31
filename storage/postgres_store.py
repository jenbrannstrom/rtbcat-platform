"""PostgreSQL storage backend for Cat-Scan.

This module provides the PostgresStore class as the primary storage API.
Full implementation is being completed incrementally.

Usage:
    >>> from storage.postgres_store import PostgresStore
    >>>
    >>> store = PostgresStore()
    >>> await store.initialize()
    >>>
    >>> # API matches prior SQLiteStore surface
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
    RTBEndpoint,
)

# Import user models from auth_service (Postgres-only)
from services.auth_service import (
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

    This class preserves the prior storage surface for compatibility.
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
        """Save or update multiple creatives using batch upsert."""
        import json
        from .repositories.creative_repository import compute_canonical_size, get_size_category

        if not creatives:
            return 0

        # Prepare data tuples for batch insert
        data = []
        for c in creatives:
            # Handle both dict and Creative object
            if hasattr(c, "id"):
                # Creative object
                width = c.width
                height = c.height
                canonical = c.canonical_size
                category = c.size_category
                if canonical is None and width is not None and height is not None:
                    canonical = compute_canonical_size(width, height)
                    category = get_size_category(canonical)

                data.append((
                    c.id, c.name, c.format, c.account_id, c.buyer_id, c.approval_status,
                    width, height, canonical, category,
                    c.final_url, c.display_url,
                    c.utm_source, c.utm_medium, c.utm_campaign,
                    c.utm_content, c.utm_term, c.advertiser_name,
                    c.campaign_id, c.cluster_id,
                    json.dumps(c.raw_data) if c.raw_data else None,
                    c.app_id, c.app_name, c.app_store,
                    json.dumps(c.disapproval_reasons) if c.disapproval_reasons else None,
                    json.dumps(c.serving_restrictions) if c.serving_restrictions else None,
                ))
            else:
                # Dict (CreativeDict)
                width = c.get("width")
                height = c.get("height")
                canonical = c.get("canonical_size")
                category = c.get("size_category")
                if canonical is None and width is not None and height is not None:
                    canonical = compute_canonical_size(width, height)
                    category = get_size_category(canonical)

                data.append((
                    c.get("id"), c.get("name"), c.get("format"),
                    c.get("account_id"), c.get("buyer_id"), c.get("approval_status"),
                    width, height, canonical, category,
                    c.get("final_url"), c.get("display_url"),
                    c.get("utm_source"), c.get("utm_medium"), c.get("utm_campaign"),
                    c.get("utm_content"), c.get("utm_term"), c.get("advertiser_name"),
                    c.get("campaign_id"), c.get("cluster_id"),
                    json.dumps(c.get("raw_data")) if c.get("raw_data") else None,
                    c.get("app_id"), c.get("app_name"), c.get("app_store"),
                    json.dumps(c.get("disapproval_reasons")) if c.get("disapproval_reasons") else None,
                    json.dumps(c.get("serving_restrictions")) if c.get("serving_restrictions") else None,
                ))

        # Batch upsert using pg_execute_many
        await pg_execute_many(
            """
            INSERT INTO creatives (
                id, name, format, account_id, buyer_id, approval_status,
                width, height, canonical_size, size_category,
                final_url, display_url,
                utm_source, utm_medium, utm_campaign,
                utm_content, utm_term, advertiser_name,
                campaign_id, cluster_id, raw_data,
                app_id, app_name, app_store,
                disapproval_reasons, serving_restrictions,
                updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                format = EXCLUDED.format,
                account_id = EXCLUDED.account_id,
                buyer_id = EXCLUDED.buyer_id,
                approval_status = EXCLUDED.approval_status,
                width = EXCLUDED.width,
                height = EXCLUDED.height,
                canonical_size = EXCLUDED.canonical_size,
                size_category = EXCLUDED.size_category,
                final_url = EXCLUDED.final_url,
                display_url = EXCLUDED.display_url,
                utm_source = EXCLUDED.utm_source,
                utm_medium = EXCLUDED.utm_medium,
                utm_campaign = EXCLUDED.utm_campaign,
                utm_content = EXCLUDED.utm_content,
                utm_term = EXCLUDED.utm_term,
                advertiser_name = EXCLUDED.advertiser_name,
                campaign_id = EXCLUDED.campaign_id,
                cluster_id = EXCLUDED.cluster_id,
                raw_data = EXCLUDED.raw_data,
                app_id = EXCLUDED.app_id,
                app_name = EXCLUDED.app_name,
                app_store = EXCLUDED.app_store,
                disapproval_reasons = EXCLUDED.disapproval_reasons,
                serving_restrictions = EXCLUDED.serving_restrictions,
                updated_at = CURRENT_TIMESTAMP
            """,
            data
        )

        return len(creatives)

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

    async def get_available_sizes(self) -> list[dict]:
        """Get all unique canonical sizes with counts."""
        rows = await pg_query(
            """
            SELECT canonical_size, size_category, COUNT(*) as count
            FROM creatives
            WHERE canonical_size IS NOT NULL
            GROUP BY canonical_size, size_category
            ORDER BY count DESC
            """
        )
        return [
            {
                "canonical_size": row["canonical_size"],
                "size_category": row["size_category"],
                "count": row["count"],
            }
            for row in rows
        ]

    async def update_creative_cluster(
        self, creative_id: str, cluster_id: Optional[str]
    ) -> bool:
        """Update the cluster assignment for a creative."""
        rows = await pg_execute(
            "UPDATE creatives SET cluster_id = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (cluster_id, creative_id)
        )
        return rows > 0

    async def update_creative_campaign(
        self, creative_id: str, campaign_id: Optional[str]
    ) -> bool:
        """Update the campaign assignment for a creative."""
        rows = await pg_execute(
            "UPDATE creatives SET campaign_id = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (campaign_id, creative_id)
        )
        return rows > 0

    async def get_thumbnail_statuses(self, creative_ids: list[str]) -> dict[str, dict]:
        """Get thumbnail statuses for multiple creatives."""
        if not creative_ids:
            return {}
        placeholders = ", ".join(["%s"] * len(creative_ids))
        rows = await pg_query(
            f"""
            SELECT creative_id, status, error_reason, updated_at
            FROM creative_thumbnails
            WHERE creative_id IN ({placeholders})
            """,
            tuple(creative_ids)
        )
        return {
            row["creative_id"]: {
                "status": row["status"],
                "error_reason": row["error_reason"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        }

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

    async def get_distinct_bidder_ids(self) -> list[str]:
        """Get all distinct bidder IDs from buyer_seats table."""
        rows = await pg_query("SELECT DISTINCT bidder_id FROM buyer_seats")
        return [row["bidder_id"] for row in rows if row["bidder_id"]]

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
    # PRETARGETING CONFIGS (Tier 2)
    # =========================================================================

    async def get_pretargeting_configs(
        self, bidder_id: Optional[str] = None
    ) -> list[dict]:
        """Get pretargeting configs, optionally filtered by bidder."""
        if bidder_id:
            rows = await pg_query(
                "SELECT * FROM pretargeting_configs WHERE bidder_id = %s ORDER BY billing_id",
                (bidder_id,)
            )
        else:
            rows = await pg_query(
                "SELECT * FROM pretargeting_configs ORDER BY billing_id"
            )
        return [dict(row) for row in rows]

    async def get_pretargeting_config_by_billing_id(
        self, billing_id: str
    ) -> Optional[dict]:
        """Get a single pretargeting config by billing_id."""
        row = await pg_query_one(
            "SELECT * FROM pretargeting_configs WHERE billing_id = %s",
            (billing_id,)
        )
        return dict(row) if row else None

    async def save_pretargeting_config(self, config: dict) -> None:
        """Save or update a pretargeting config."""
        await pg_execute(
            """
            INSERT INTO pretargeting_configs
            (bidder_id, config_id, billing_id, display_name, user_name, state,
             included_formats, included_platforms, included_sizes,
             included_geos, excluded_geos, included_publishers, excluded_publishers,
             publisher_targeting_mode, raw_config, synced_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (bidder_id, config_id) DO UPDATE SET
                billing_id = EXCLUDED.billing_id,
                display_name = EXCLUDED.display_name,
                state = EXCLUDED.state,
                included_formats = EXCLUDED.included_formats,
                included_platforms = EXCLUDED.included_platforms,
                included_sizes = EXCLUDED.included_sizes,
                included_geos = EXCLUDED.included_geos,
                excluded_geos = EXCLUDED.excluded_geos,
                included_publishers = EXCLUDED.included_publishers,
                excluded_publishers = EXCLUDED.excluded_publishers,
                publisher_targeting_mode = EXCLUDED.publisher_targeting_mode,
                raw_config = EXCLUDED.raw_config,
                synced_at = CURRENT_TIMESTAMP
            """,
            (
                config.get("bidder_id"),
                config.get("config_id"),
                config.get("billing_id"),
                config.get("display_name"),
                config.get("user_name"),
                config.get("state", "ACTIVE"),
                config.get("included_formats"),
                config.get("included_platforms"),
                config.get("included_sizes"),
                config.get("included_geos"),
                config.get("excluded_geos"),
                config.get("included_publishers"),
                config.get("excluded_publishers"),
                config.get("publisher_targeting_mode"),
                config.get("raw_config"),
            ),
        )

    async def update_pretargeting_user_name(
        self, billing_id: str, user_name: str
    ) -> bool:
        """Update user-defined name for a pretargeting config."""
        rows = await pg_execute(
            "UPDATE pretargeting_configs SET user_name = %s WHERE billing_id = %s",
            (user_name, billing_id)
        )
        return rows > 0

    async def update_pretargeting_state(
        self, billing_id: str, state: str
    ) -> bool:
        """Update the state (ACTIVE/SUSPENDED) for a pretargeting config."""
        rows = await pg_execute(
            "UPDATE pretargeting_configs SET state = %s WHERE billing_id = %s",
            (state, billing_id)
        )
        return rows > 0

    # =========================================================================
    # PRETARGETING HISTORY (Tier 2)
    # =========================================================================

    async def get_pretargeting_history(
        self,
        config_id: Optional[str] = None,
        billing_id: Optional[str] = None,
        days: int = 30,
        limit: int = 500,
    ) -> list[dict]:
        """Get pretargeting change history."""
        conditions = [f"ph.changed_at >= CURRENT_TIMESTAMP - INTERVAL '{days} days'"]
        params: list[Any] = []

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
            tuple(params)
        )
        return [dict(row) for row in rows]

    async def add_pretargeting_history(
        self,
        config_id: str,
        bidder_id: str,
        change_type: str,
        field_changed: Optional[str] = None,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        changed_by: Optional[str] = None,
        change_source: str = "user",
    ) -> int:
        """Add a pretargeting history entry. Returns the new ID."""
        row = await pg_query_one(
            """
            INSERT INTO pretargeting_history
            (config_id, bidder_id, change_type, field_changed, old_value, new_value,
             changed_by, change_source, changed_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            RETURNING id
            """,
            (config_id, bidder_id, change_type, field_changed, old_value, new_value,
             changed_by, change_source)
        )
        return row["id"] if row else 0

    # =========================================================================
    # PRETARGETING PENDING CHANGES (Tier 2)
    # =========================================================================

    async def get_pending_changes(
        self,
        billing_id: Optional[str] = None,
        status: str = "pending",
        limit: int = 100,
    ) -> list[dict]:
        """Get pending pretargeting changes."""
        conditions = ["status = %s"]
        params: list[Any] = [status]

        if billing_id:
            conditions.append("billing_id = %s")
            params.append(billing_id)

        params.append(limit)
        where_clause = " AND ".join(conditions)

        rows = await pg_query(
            f"""
            SELECT * FROM pretargeting_pending_changes
            WHERE {where_clause}
            ORDER BY created_at DESC LIMIT %s
            """,
            tuple(params)
        )
        return [dict(row) for row in rows]

    async def create_pending_change(
        self,
        billing_id: str,
        config_id: str,
        change_type: str,
        field_name: str,
        value: str,
        reason: Optional[str] = None,
        estimated_qps_impact: Optional[float] = None,
        created_by: Optional[str] = None,
    ) -> int:
        """Create a pending change. Returns the new ID."""
        row = await pg_query_one(
            """
            INSERT INTO pretargeting_pending_changes
            (billing_id, config_id, change_type, field_name, value,
             reason, estimated_qps_impact, created_by, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', CURRENT_TIMESTAMP)
            RETURNING id
            """,
            (billing_id, config_id, change_type, field_name, value,
             reason, estimated_qps_impact, created_by)
        )
        return row["id"] if row else 0

    async def get_pending_change(self, change_id: int) -> Optional[dict]:
        """Get a single pending change by ID."""
        row = await pg_query_one(
            "SELECT * FROM pretargeting_pending_changes WHERE id = %s",
            (change_id,)
        )
        return dict(row) if row else None

    async def cancel_pending_change(self, change_id: int) -> bool:
        """Mark a pending change as cancelled."""
        rows = await pg_execute(
            "UPDATE pretargeting_pending_changes SET status = 'cancelled' WHERE id = %s AND status = 'pending'",
            (change_id,)
        )
        return rows > 0

    async def mark_pending_change_applied(self, change_id: int, applied_by: Optional[str] = None) -> bool:
        """Mark a pending change as applied."""
        rows = await pg_execute(
            """
            UPDATE pretargeting_pending_changes
            SET status = 'applied', applied_at = CURRENT_TIMESTAMP, applied_by = %s
            WHERE id = %s AND status = 'pending'
            """,
            (applied_by, change_id)
        )
        return rows > 0

    async def get_performance_aggregates(
        self, billing_id: str
    ) -> dict:
        """Get aggregated performance metrics for a billing_id.

        Tries rtb_daily first (new schema), falls back to performance_metrics.

        Returns:
            Dict with days_tracked, total_impressions, total_clicks, total_spend_usd.
        """
        # Try rtb_daily first (new schema)
        perf = await pg_query_one(
            """
            SELECT
                COUNT(DISTINCT metric_date) as days_tracked,
                COALESCE(SUM(impressions), 0) as total_impressions,
                COALESCE(SUM(clicks), 0) as total_clicks,
                COALESCE(SUM(spend_micros), 0) / 1000000.0 as total_spend_usd
            FROM rtb_daily
            WHERE billing_id = %s
            """,
            (billing_id,)
        )

        if perf and perf["days_tracked"] > 0:
            return {
                "days_tracked": perf["days_tracked"],
                "total_impressions": perf["total_impressions"],
                "total_clicks": perf["total_clicks"],
                "total_spend_usd": perf["total_spend_usd"],
            }

        # Fallback to performance_metrics (old schema)
        perf = await pg_query_one(
            """
            SELECT
                COUNT(DISTINCT metric_date) as days_tracked,
                COALESCE(SUM(impressions), 0) as total_impressions,
                COALESCE(SUM(clicks), 0) as total_clicks,
                COALESCE(SUM(spend_micros), 0) / 1000000.0 as total_spend_usd
            FROM performance_metrics
            WHERE billing_id = %s
            """,
            (billing_id,)
        )

        return {
            "days_tracked": perf["days_tracked"] if perf else 0,
            "total_impressions": perf["total_impressions"] if perf else 0,
            "total_clicks": perf["total_clicks"] if perf else 0,
            "total_spend_usd": perf["total_spend_usd"] if perf else 0,
        }

    # =========================================================================
    # PRETARGETING SNAPSHOTS (Tier 2)
    # =========================================================================

    async def create_snapshot(
        self,
        billing_id: str,
        snapshot_name: Optional[str] = None,
        snapshot_type: str = "manual",
        config_data: Optional[dict] = None,
        performance_data: Optional[dict] = None,
        publisher_targeting_mode: Optional[str] = None,
        publisher_targeting_values: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> int:
        """Create a pretargeting snapshot. Returns the new ID."""
        cfg = config_data or {}
        perf = performance_data or {}

        row = await pg_query_one(
            """
            INSERT INTO pretargeting_snapshots
            (billing_id, snapshot_name, snapshot_type,
             included_formats, included_platforms, included_sizes,
             included_geos, excluded_geos, state,
             publisher_targeting_mode, publisher_targeting_values,
             total_impressions, total_clicks, total_spend_usd,
             total_reached_queries, days_tracked,
             avg_daily_impressions, avg_daily_spend_usd, ctr_pct, cpm_usd,
             notes, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            RETURNING id
            """,
            (
                billing_id,
                snapshot_name,
                snapshot_type,
                cfg.get("included_formats"),
                cfg.get("included_platforms"),
                cfg.get("included_sizes"),
                cfg.get("included_geos"),
                cfg.get("excluded_geos"),
                cfg.get("state"),
                publisher_targeting_mode,
                publisher_targeting_values,
                perf.get("total_impressions", 0),
                perf.get("total_clicks", 0),
                perf.get("total_spend_usd", 0),
                perf.get("total_reached_queries", 0),
                perf.get("days_tracked", 0),
                perf.get("avg_daily_impressions"),
                perf.get("avg_daily_spend_usd"),
                perf.get("ctr_pct"),
                perf.get("cpm_usd"),
                notes,
            )
        )
        return row["id"] if row else 0

    async def get_snapshot(self, snapshot_id: int) -> Optional[dict]:
        """Get a snapshot by ID."""
        row = await pg_query_one(
            "SELECT * FROM pretargeting_snapshots WHERE id = %s",
            (snapshot_id,)
        )
        return dict(row) if row else None

    async def list_snapshots(
        self,
        billing_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """List pretargeting snapshots."""
        if billing_id:
            rows = await pg_query(
                """
                SELECT * FROM pretargeting_snapshots
                WHERE billing_id = %s
                ORDER BY created_at DESC LIMIT %s
                """,
                (billing_id, limit)
            )
        else:
            rows = await pg_query(
                "SELECT * FROM pretargeting_snapshots ORDER BY created_at DESC LIMIT %s",
                (limit,)
            )
        return [dict(row) for row in rows]

    # =========================================================================
    # PRETARGETING CHANGE LOG (Tier 2)
    # =========================================================================

    async def add_change_log(
        self,
        billing_id: str,
        change_type: str,
        field_changed: str,
        old_value: Optional[str] = None,
        new_value: Optional[str] = None,
        auto_snapshot_id: Optional[int] = None,
    ) -> int:
        """Add a change log entry. Returns the new ID."""
        row = await pg_query_one(
            """
            INSERT INTO pretargeting_change_log
            (billing_id, change_type, field_changed, old_value, new_value,
             auto_snapshot_id, detected_at)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            RETURNING id
            """,
            (billing_id, change_type, field_changed, old_value, new_value, auto_snapshot_id)
        )
        return row["id"] if row else 0

    async def get_change_log(
        self,
        billing_id: Optional[str] = None,
        days: int = 30,
        limit: int = 100,
    ) -> list[dict]:
        """Get pretargeting change log."""
        conditions = [f"detected_at >= CURRENT_TIMESTAMP - INTERVAL '{days} days'"]
        params: list[Any] = []

        if billing_id:
            conditions.append("billing_id = %s")
            params.append(billing_id)

        params.append(limit)
        where_clause = " AND ".join(conditions)

        rows = await pg_query(
            f"""
            SELECT * FROM pretargeting_change_log
            WHERE {where_clause}
            ORDER BY detected_at DESC LIMIT %s
            """,
            tuple(params)
        )
        return [dict(row) for row in rows]

    # =========================================================================
    # PRETARGETING PUBLISHERS (Tier 2)
    # =========================================================================

    async def get_pretargeting_publishers(
        self,
        billing_id: str,
        mode: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[dict]:
        """Get publishers for a pretargeting config."""
        conditions = ["billing_id = %s"]
        params: list[Any] = [billing_id]

        if mode:
            conditions.append("mode = %s")
            params.append(mode.upper())
        if status:
            conditions.append("status = %s")
            params.append(status)

        where_clause = " AND ".join(conditions)
        rows = await pg_query(
            f"""
            SELECT publisher_id, mode, status, source, created_at, updated_at
            FROM pretargeting_publishers
            WHERE {where_clause}
            ORDER BY mode, publisher_id
            """,
            tuple(params)
        )
        return [dict(row) for row in rows]

    async def add_pretargeting_publisher(
        self,
        billing_id: str,
        publisher_id: str,
        mode: str,
        status: str = "pending_add",
        source: str = "user",
    ) -> None:
        """Add a publisher to pretargeting list."""
        await pg_execute(
            """
            INSERT INTO pretargeting_publishers (billing_id, publisher_id, mode, status, source)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (billing_id, publisher_id, mode) DO UPDATE SET
                status = EXCLUDED.status,
                source = EXCLUDED.source,
                updated_at = CURRENT_TIMESTAMP
            """,
            (billing_id, publisher_id, mode.upper(), status, source)
        )

    async def update_publisher_status(
        self,
        billing_id: str,
        publisher_id: str,
        mode: str,
        status: str,
    ) -> bool:
        """Update a publisher's status."""
        rows = await pg_execute(
            """
            UPDATE pretargeting_publishers
            SET status = %s, updated_at = CURRENT_TIMESTAMP
            WHERE billing_id = %s AND publisher_id = %s AND mode = %s
            """,
            (status, billing_id, publisher_id, mode.upper())
        )
        return rows > 0

    async def delete_pretargeting_publisher(
        self,
        billing_id: str,
        publisher_id: str,
        mode: str,
    ) -> bool:
        """Delete a publisher from pretargeting list."""
        rows = await pg_execute(
            "DELETE FROM pretargeting_publishers WHERE billing_id = %s AND publisher_id = %s AND mode = %s",
            (billing_id, publisher_id, mode.upper())
        )
        return rows > 0

    async def get_pending_publisher_changes(self, billing_id: str) -> list[dict]:
        """Get publishers with pending changes."""
        rows = await pg_query(
            """
            SELECT publisher_id, mode, status, source, updated_at
            FROM pretargeting_publishers
            WHERE billing_id = %s AND status IN ('pending_add', 'pending_remove')
            ORDER BY status, mode, publisher_id
            """,
            (billing_id,)
        )
        return [dict(row) for row in rows]

    async def clear_api_sync_publishers(self, billing_id: str) -> int:
        """Clear all api_sync publishers for a billing_id before re-syncing."""
        return await pg_execute(
            "DELETE FROM pretargeting_publishers WHERE billing_id = %s AND source = 'api_sync'",
            (billing_id,)
        )

    async def check_publisher_in_opposite_mode(
        self,
        billing_id: str,
        publisher_id: str,
        mode: str,
    ) -> Optional[dict]:
        """Check if publisher exists in the opposite mode."""
        row = await pg_query_one(
            "SELECT mode FROM pretargeting_publishers WHERE billing_id = %s AND publisher_id = %s AND mode != %s",
            (billing_id, publisher_id, mode.upper())
        )
        return dict(row) if row else None

    # =========================================================================
    # SNAPSHOT COMPARISONS (Tier 2)
    # =========================================================================

    async def create_comparison(
        self,
        billing_id: str,
        comparison_name: Optional[str],
        before_snapshot_id: int,
        before_start_date: Optional[str] = None,
        before_end_date: Optional[str] = None,
    ) -> int:
        """Create a snapshot comparison. Returns the new ID."""
        row = await pg_query_one(
            """
            INSERT INTO snapshot_comparisons
            (billing_id, comparison_name, before_snapshot_id, before_start_date, before_end_date, status)
            VALUES (%s, %s, %s, %s, %s, 'in_progress')
            RETURNING id
            """,
            (billing_id, comparison_name, before_snapshot_id, before_start_date, before_end_date)
        )
        return row["id"] if row else 0

    async def get_comparison(self, comparison_id: int) -> Optional[dict]:
        """Get a comparison by ID."""
        row = await pg_query_one(
            "SELECT * FROM snapshot_comparisons WHERE id = %s",
            (comparison_id,)
        )
        return dict(row) if row else None

    async def list_comparisons(
        self,
        billing_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """List snapshot comparisons."""
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
            tuple(params)
        )
        return [dict(row) for row in rows]

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
    # THUMBNAIL STATUS (Tier 3)
    # =========================================================================

    async def get_thumbnail_status(self, creative_id: str) -> Optional[dict]:
        """Get thumbnail status for a single creative."""
        row = await pg_query_one(
            """
            SELECT creative_id, status, error_reason, updated_at
            FROM creative_thumbnails WHERE creative_id = %s
            """,
            (creative_id,)
        )
        if row:
            return {
                "status": row["status"],
                "error_reason": row["error_reason"],
                "updated_at": row["updated_at"],
            }
        return None

    async def save_thumbnail_status(
        self, creative_id: str, status: str, error_reason: Optional[str] = None
    ) -> None:
        """Save thumbnail generation status."""
        await pg_execute(
            """
            INSERT INTO creative_thumbnails (creative_id, status, error_reason, updated_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (creative_id) DO UPDATE SET
                status = EXCLUDED.status,
                error_reason = EXCLUDED.error_reason,
                updated_at = CURRENT_TIMESTAMP
            """,
            (creative_id, status, error_reason)
        )

    # =========================================================================
    # RTB ENDPOINTS
    # =========================================================================

    async def get_bidder_id_for_service_account(
        self, service_account_id: str
    ) -> Optional[str]:
        """Get bidder_id for a service account from buyer_seats."""
        row = await pg_query_one(
            "SELECT bidder_id FROM buyer_seats WHERE service_account_id = %s LIMIT 1",
            (service_account_id,)
        )
        return row["bidder_id"] if row else None

    async def get_first_bidder_id(self) -> Optional[str]:
        """Get the first available bidder_id (for single-account scenarios)."""
        row = await pg_query_one("SELECT bidder_id FROM buyer_seats LIMIT 1")
        return row["bidder_id"] if row else None

    async def get_buyer_seat_with_bidder(
        self, buyer_id: str
    ) -> Optional[dict]:
        """Get buyer seat info including bidder_id and display_name."""
        row = await pg_query_one(
            "SELECT bidder_id, display_name FROM buyer_seats WHERE buyer_id = %s",
            (buyer_id,)
        )
        return dict(row) if row else None

    async def sync_rtb_endpoints(
        self, bidder_id: str, endpoints: list[dict]
    ) -> int:
        """Sync RTB endpoints from API response.

        Upserts endpoints for a bidder account.

        Args:
            bidder_id: The bidder account ID.
            endpoints: List of endpoint dicts from API.

        Returns:
            Number of endpoints synced.
        """
        if not endpoints:
            return 0

        data = [
            (
                bidder_id,
                ep["endpointId"],
                ep.get("url"),
                ep.get("maximumQps"),
                ep.get("tradingLocation"),
                ep.get("bidProtocol"),
            )
            for ep in endpoints
        ]

        await pg_execute_many(
            """
            INSERT INTO rtb_endpoints
            (bidder_id, endpoint_id, url, maximum_qps, trading_location, bid_protocol, synced_at)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (bidder_id, endpoint_id) DO UPDATE SET
                url = EXCLUDED.url,
                maximum_qps = EXCLUDED.maximum_qps,
                trading_location = EXCLUDED.trading_location,
                bid_protocol = EXCLUDED.bid_protocol,
                synced_at = CURRENT_TIMESTAMP
            """,
            data
        )
        return len(endpoints)

    async def get_rtb_endpoints(
        self, bidder_id: Optional[str] = None
    ) -> list[dict]:
        """Get RTB endpoints, optionally filtered by bidder.

        Returns:
            List of endpoint dicts with endpoint info and sync timestamp.
        """
        if bidder_id:
            rows = await pg_query(
                """
                SELECT * FROM rtb_endpoints
                WHERE bidder_id = %s
                ORDER BY trading_location, endpoint_id
                """,
                (bidder_id,)
            )
        else:
            rows = await pg_query(
                "SELECT * FROM rtb_endpoints ORDER BY trading_location, endpoint_id"
            )
        return [dict(row) for row in rows]

    async def get_rtb_endpoints_current_qps(
        self, bidder_id: Optional[str] = None
    ) -> Optional[int]:
        """Get aggregated current QPS from rtb_endpoints_current table.

        Returns:
            Total current QPS, or None if no data.
        """
        if bidder_id:
            row = await pg_query_one(
                "SELECT SUM(current_qps) as current_qps FROM rtb_endpoints_current WHERE bidder_id = %s",
                (bidder_id,)
            )
        else:
            row = await pg_query_one(
                "SELECT SUM(current_qps) as current_qps FROM rtb_endpoints_current"
            )
        return row["current_qps"] if row else None

    # =========================================================================
    # Retention Management
    # =========================================================================

    async def get_retention_config(self, seat_id: Optional[str] = None) -> dict:
        """Get retention configuration."""
        if seat_id:
            row = await pg_query_one(
                "SELECT * FROM retention_config WHERE seat_id = %s",
                (seat_id,)
            )
            if row:
                return dict(row)

        # Check for global config (seat_id = NULL)
        row = await pg_query_one(
            "SELECT * FROM retention_config WHERE seat_id IS NULL"
        )
        if row:
            return dict(row)

        # Return defaults
        return {
            'raw_retention_days': 90,
            'summary_retention_days': 365,
            'auto_aggregate_after_days': 30,
        }

    async def set_retention_config(
        self,
        raw_retention_days: int,
        summary_retention_days: int,
        auto_aggregate_after_days: int = 30,
        seat_id: Optional[str] = None,
    ) -> None:
        """Set retention configuration."""
        await pg_execute(
            """
            INSERT INTO retention_config (seat_id, raw_retention_days, summary_retention_days, auto_aggregate_after_days, updated_at)
            VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (seat_id) DO UPDATE SET
                raw_retention_days = EXCLUDED.raw_retention_days,
                summary_retention_days = EXCLUDED.summary_retention_days,
                auto_aggregate_after_days = EXCLUDED.auto_aggregate_after_days,
                updated_at = CURRENT_TIMESTAMP
            """,
            (seat_id, raw_retention_days, summary_retention_days, auto_aggregate_after_days)
        )

    async def get_storage_stats(self, seat_id: Optional[str] = None) -> dict:
        """Get storage statistics for retention management."""
        stats = {}

        # Raw data stats from performance_metrics
        if seat_id:
            raw_row = await pg_query_one(
                "SELECT COUNT(*) as cnt, MIN(metric_date) as earliest, MAX(metric_date) as latest FROM performance_metrics WHERE seat_id = %s",
                (seat_id,)
            )
        else:
            raw_row = await pg_query_one(
                "SELECT COUNT(*) as cnt, MIN(metric_date) as earliest, MAX(metric_date) as latest FROM performance_metrics"
            )

        if raw_row:
            stats['raw_rows'] = raw_row['cnt'] or 0
            stats['raw_earliest_date'] = str(raw_row['earliest']) if raw_row['earliest'] else None
            stats['raw_latest_date'] = str(raw_row['latest']) if raw_row['latest'] else None
        else:
            stats['raw_rows'] = 0
            stats['raw_earliest_date'] = None
            stats['raw_latest_date'] = None

        # Summary stats
        if seat_id:
            summary_row = await pg_query_one(
                "SELECT COUNT(*) as cnt, MIN(summary_date) as earliest, MAX(summary_date) as latest FROM daily_creative_summary WHERE seat_id = %s",
                (seat_id,)
            )
        else:
            summary_row = await pg_query_one(
                "SELECT COUNT(*) as cnt, MIN(summary_date) as earliest, MAX(summary_date) as latest FROM daily_creative_summary"
            )

        if summary_row:
            stats['summary_rows'] = summary_row['cnt'] or 0
            stats['summary_earliest_date'] = str(summary_row['earliest']) if summary_row['earliest'] else None
            stats['summary_latest_date'] = str(summary_row['latest']) if summary_row['latest'] else None
        else:
            stats['summary_rows'] = 0
            stats['summary_earliest_date'] = None
            stats['summary_latest_date'] = None

        return stats

    async def run_retention_job(self, seat_id: Optional[str] = None) -> dict:
        """Run retention job to aggregate and clean old data."""
        from datetime import datetime, timedelta

        config = await self.get_retention_config(seat_id)
        stats = {
            'aggregated_rows': 0,
            'deleted_raw_rows': 0,
            'deleted_summary_rows': 0,
        }

        # Step 1: Aggregate old data into daily summaries
        aggregate_cutoff = (datetime.now() - timedelta(days=config['auto_aggregate_after_days'])).strftime('%Y-%m-%d')

        # Aggregate from performance_metrics to daily_creative_summary
        seat_filter = "AND seat_id = %s" if seat_id else ""
        params: tuple = (aggregate_cutoff, seat_id) if seat_id else (aggregate_cutoff,)

        await pg_execute(
            f"""
            INSERT INTO daily_creative_summary (seat_id, creative_id, summary_date, total_queries, total_impressions, total_clicks, total_spend, win_rate, ctr, cpm)
            SELECT
                seat_id,
                creative_id,
                metric_date,
                SUM(COALESCE(reached_queries, 0)),
                SUM(COALESCE(impressions, 0)),
                SUM(COALESCE(clicks, 0)),
                SUM(COALESCE(spend_micros, 0)) / 1000000.0,
                CASE WHEN SUM(COALESCE(reached_queries, 0)) > 0
                     THEN CAST(SUM(COALESCE(impressions, 0)) AS REAL) / SUM(reached_queries)
                     ELSE 0 END,
                CASE WHEN SUM(COALESCE(impressions, 0)) > 0
                     THEN CAST(SUM(COALESCE(clicks, 0)) AS REAL) / SUM(impressions)
                     ELSE 0 END,
                CASE WHEN SUM(COALESCE(impressions, 0)) > 0
                     THEN (SUM(COALESCE(spend_micros, 0)) / 1000000.0 / SUM(impressions)) * 1000
                     ELSE 0 END
            FROM performance_metrics
            WHERE metric_date < %s {seat_filter}
            GROUP BY seat_id, creative_id, metric_date
            ON CONFLICT (seat_id, creative_id, summary_date) DO UPDATE SET
                total_queries = EXCLUDED.total_queries,
                total_impressions = EXCLUDED.total_impressions,
                total_clicks = EXCLUDED.total_clicks,
                total_spend = EXCLUDED.total_spend
            """,
            params
        )

        # Step 2: Delete old raw data
        delete_cutoff = (datetime.now() - timedelta(days=config['raw_retention_days'])).strftime('%Y-%m-%d')
        delete_params: tuple = (delete_cutoff, seat_id) if seat_id else (delete_cutoff,)

        stats['deleted_raw_rows'] = await pg_execute(
            f"DELETE FROM performance_metrics WHERE metric_date < %s {seat_filter}",
            delete_params
        )

        # Step 3: Delete old summaries if configured
        if config['summary_retention_days'] > 0:
            summary_cutoff = (datetime.now() - timedelta(days=config['summary_retention_days'])).strftime('%Y-%m-%d')
            summary_params: tuple = (summary_cutoff, seat_id) if seat_id else (summary_cutoff,)

            stats['deleted_summary_rows'] = await pg_execute(
                f"DELETE FROM daily_creative_summary WHERE summary_date < %s {seat_filter}",
                summary_params
            )

        return stats
