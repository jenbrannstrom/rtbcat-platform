"""Postgres repository for buyer seats and service accounts (SQL only)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from storage.postgres_database import pg_query, pg_query_one, pg_execute


class SeatsRepository:
    """SQL-only repository for buyer_seats and service_accounts tables."""

    # =========================================================================
    # Buyer Seats
    # =========================================================================

    async def get_buyer_seats(
        self,
        bidder_id: Optional[str] = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        """Get all buyer seats, optionally filtered."""
        conditions = []
        params = []

        if bidder_id:
            conditions.append("bidder_id = %s")
            params.append(bidder_id)
        if active_only:
            conditions.append("active = true")

        where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

        return await pg_query(
            f"""
            SELECT buyer_id, bidder_id, display_name, active,
                   creative_count, last_synced, created_at, service_account_id
            FROM buyer_seats
            {where_clause}
            ORDER BY display_name, buyer_id
            """,
            tuple(params) if params else None,
        )

    async def get_buyer_seats_by_ids(
        self,
        buyer_ids: list[str],
        bidder_id: Optional[str] = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        """Get buyer seats constrained to an explicit buyer_id allow-list."""
        if not buyer_ids:
            return []

        conditions = ["buyer_id = ANY(%s)"]
        params: list[Any] = [buyer_ids]

        if bidder_id:
            conditions.append("bidder_id = %s")
            params.append(bidder_id)
        if active_only:
            conditions.append("active = true")

        where_clause = "WHERE " + " AND ".join(conditions)

        return await pg_query(
            f"""
            SELECT buyer_id, bidder_id, display_name, active,
                   creative_count, last_synced, created_at, service_account_id
            FROM buyer_seats
            {where_clause}
            ORDER BY display_name, buyer_id
            """,
            tuple(params),
        )

    async def get_buyer_seats_for_service_accounts(
        self,
        service_account_ids: list[str],
        bidder_id: Optional[str] = None,
        active_only: bool = True,
    ) -> list[dict[str, Any]]:
        """Get buyer seats linked to specific service accounts."""
        if not service_account_ids:
            return []

        conditions = ["service_account_id = ANY(%s)"]
        params: list[Any] = [service_account_ids]

        if bidder_id:
            conditions.append("bidder_id = %s")
            params.append(bidder_id)
        if active_only:
            conditions.append("active = true")

        where_clause = "WHERE " + " AND ".join(conditions)

        return await pg_query(
            f"""
            SELECT buyer_id, bidder_id, display_name, active,
                   creative_count, last_synced, created_at, service_account_id
            FROM buyer_seats
            {where_clause}
            ORDER BY display_name, buyer_id
            """,
            tuple(params),
        )

    async def get_buyer_seat(self, buyer_id: str) -> Optional[dict[str, Any]]:
        """Get a single buyer seat by ID."""
        return await pg_query_one(
            """
            SELECT buyer_id, bidder_id, display_name, active,
                   creative_count, last_synced, created_at, service_account_id
            FROM buyer_seats
            WHERE buyer_id = %s
            """,
            (buyer_id,),
        )

    async def save_buyer_seat(
        self,
        buyer_id: str,
        bidder_id: str,
        display_name: Optional[str] = None,
        active: bool = True,
        service_account_id: Optional[str] = None,
    ) -> None:
        """Insert or update a buyer seat."""
        await pg_execute(
            """
            INSERT INTO buyer_seats (buyer_id, bidder_id, display_name, active, service_account_id, created_at)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (buyer_id) DO UPDATE SET
                bidder_id = EXCLUDED.bidder_id,
                display_name = COALESCE(EXCLUDED.display_name, buyer_seats.display_name),
                active = EXCLUDED.active,
                service_account_id = COALESCE(EXCLUDED.service_account_id, buyer_seats.service_account_id)
            """,
            (buyer_id, bidder_id, display_name, active, service_account_id),
        )

    async def update_buyer_seat_display_name(
        self, buyer_id: str, display_name: str
    ) -> bool:
        """Update a buyer seat's display name."""
        await pg_execute(
            "UPDATE buyer_seats SET display_name = %s WHERE buyer_id = %s",
            (display_name, buyer_id),
        )
        return True

    async def update_seat_creative_count(self, buyer_id: str) -> None:
        """Update creative count for a buyer seat."""
        await pg_execute(
            """
            UPDATE buyer_seats
            SET creative_count = (
                SELECT COUNT(*) FROM creatives WHERE buyer_id = %s
            )
            WHERE buyer_id = %s
            """,
            (buyer_id, buyer_id),
        )

    async def update_seat_sync_time(self, buyer_id: str) -> None:
        """Update last_synced timestamp for a buyer seat."""
        await pg_execute(
            "UPDATE buyer_seats SET last_synced = CURRENT_TIMESTAMP WHERE buyer_id = %s",
            (buyer_id,),
        )

    async def link_buyer_seat_to_service_account(
        self, buyer_id: str, service_account_id: str
    ) -> None:
        """Link a buyer seat to a service account."""
        await pg_execute(
            "UPDATE buyer_seats SET service_account_id = %s WHERE buyer_id = %s",
            (service_account_id, buyer_id),
        )

    async def get_distinct_bidder_ids(self) -> list[str]:
        """Get all unique bidder IDs from buyer seats."""
        rows = await pg_query(
            "SELECT DISTINCT bidder_id FROM buyer_seats WHERE active = true ORDER BY bidder_id"
        )
        return [row["bidder_id"] for row in rows]

    async def populate_buyer_seats_from_creatives(self) -> int:
        """Create buyer seats from unique account_ids in creatives."""
        await pg_execute(
            """
            INSERT INTO buyer_seats (buyer_id, bidder_id, active, created_at)
            SELECT DISTINCT buyer_id, account_id, true, CURRENT_TIMESTAMP
            FROM creatives
            WHERE buyer_id IS NOT NULL AND account_id IS NOT NULL
            ON CONFLICT (buyer_id) DO NOTHING
            """
        )
        row = await pg_query_one(
            "SELECT COUNT(*) as cnt FROM buyer_seats"
        )
        return row["cnt"] if row else 0

    # =========================================================================
    # Service Accounts
    # =========================================================================

    async def get_service_accounts(
        self, active_only: bool = True
    ) -> list[dict[str, Any]]:
        """Get all service accounts."""
        if active_only:
            return await pg_query(
                """
                SELECT id, client_email, project_id, display_name,
                       credentials_path, is_active, last_used, created_at
                FROM service_accounts
                WHERE is_active = true
                ORDER BY display_name, id
                """
            )
        return await pg_query(
            """
            SELECT id, client_email, project_id, display_name,
                   credentials_path, is_active, last_used, created_at
            FROM service_accounts
            ORDER BY display_name, id
            """
        )

    async def get_service_account(self, account_id: str) -> Optional[dict[str, Any]]:
        """Get a single service account by ID."""
        return await pg_query_one(
            """
            SELECT id, client_email, project_id, display_name,
                   credentials_path, is_active, last_used, created_at
            FROM service_accounts
            WHERE id = %s
            """,
            (account_id,),
        )

    async def update_service_account_last_used(self, account_id: str) -> None:
        """Update last_used timestamp for a service account."""
        await pg_execute(
            "UPDATE service_accounts SET last_used = CURRENT_TIMESTAMP WHERE id = %s",
            (account_id,),
        )

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

    async def get_buyer_seat_with_bidder(self, buyer_id: str) -> Optional[dict[str, Any]]:
        """Get buyer seat info including bidder_id, display_name, and service_account_id."""
        return await pg_query_one(
            "SELECT bidder_id, display_name, service_account_id FROM buyer_seats WHERE buyer_id = %s",
            (buyer_id,)
        )
