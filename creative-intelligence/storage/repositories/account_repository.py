"""Account repository for service accounts and buyer seats.

This module provides database operations for service accounts (multi-account support)
and buyer seats (multi-seat account support).
"""

from __future__ import annotations

import asyncio
import sqlite3
from pathlib import Path
from typing import Optional, Any

from .base import BaseRepository
from ..models import ServiceAccount, BuyerSeat


class AccountRepository(BaseRepository[ServiceAccount]):
    """Repository for service accounts and buyer seats.

    Manages multi-account support (service accounts) and multi-seat
    support (buyer seats) for RTB integration.
    """

    def __init__(self, db_path: str | Path) -> None:
        """Initialize repository with database path.

        Args:
            db_path: Path to SQLite database file.
        """
        super().__init__(db_path)

    # ==================== Service Account Methods ====================

    async def save_service_account(self, account: ServiceAccount) -> None:
        """Insert or update a service account.

        Args:
            account: The ServiceAccount to save.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    """
                    INSERT OR REPLACE INTO service_accounts (
                        id, client_email, project_id, display_name,
                        credentials_path, is_active, created_at, last_used
                    ) VALUES (?, ?, ?, ?, ?, ?, COALESCE(
                        (SELECT created_at FROM service_accounts WHERE id = ?),
                        CURRENT_TIMESTAMP
                    ), ?)
                    """,
                    (
                        account.id,
                        account.client_email,
                        account.project_id,
                        account.display_name,
                        account.credentials_path,
                        1 if account.is_active else 0,
                        account.id,
                        account.last_used,
                    ),
                ),
            )
            await loop.run_in_executor(None, conn.commit)

    async def get_service_accounts(
        self,
        active_only: bool = False,
    ) -> list[ServiceAccount]:
        """Get all service accounts.

        Args:
            active_only: If True, only return active accounts.

        Returns:
            List of ServiceAccount objects.
        """
        conditions = []
        if active_only:
            conditions.append("is_active = 1")

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    f"""
                    SELECT id, client_email, project_id, display_name,
                           credentials_path, is_active, created_at, last_used
                    FROM service_accounts
                    WHERE {where_clause}
                    ORDER BY display_name, client_email
                    """,
                )
                return cursor.fetchall()

            rows = await loop.run_in_executor(None, _query)

        return [
            ServiceAccount(
                id=row[0],
                client_email=row[1],
                project_id=row[2],
                display_name=row[3],
                credentials_path=row[4],
                is_active=bool(row[5]),
                created_at=row[6],
                last_used=row[7],
            )
            for row in rows
        ]

    async def get_service_account(self, account_id: str) -> Optional[ServiceAccount]:
        """Get a specific service account.

        Args:
            account_id: The service account ID (UUID).

        Returns:
            ServiceAccount object or None if not found.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    """
                    SELECT id, client_email, project_id, display_name,
                           credentials_path, is_active, created_at, last_used
                    FROM service_accounts
                    WHERE id = ?
                    """,
                    (account_id,),
                )
                return cursor.fetchone()

            row = await loop.run_in_executor(None, _query)

            if row:
                return ServiceAccount(
                    id=row[0],
                    client_email=row[1],
                    project_id=row[2],
                    display_name=row[3],
                    credentials_path=row[4],
                    is_active=bool(row[5]),
                    created_at=row[6],
                    last_used=row[7],
                )
            return None

    async def get_service_account_by_email(self, client_email: str) -> Optional[ServiceAccount]:
        """Get a service account by its client email.

        Args:
            client_email: The service account email address.

        Returns:
            ServiceAccount object or None if not found.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    """
                    SELECT id, client_email, project_id, display_name,
                           credentials_path, is_active, created_at, last_used
                    FROM service_accounts
                    WHERE client_email = ?
                    """,
                    (client_email,),
                )
                return cursor.fetchone()

            row = await loop.run_in_executor(None, _query)

            if row:
                return ServiceAccount(
                    id=row[0],
                    client_email=row[1],
                    project_id=row[2],
                    display_name=row[3],
                    credentials_path=row[4],
                    is_active=bool(row[5]),
                    created_at=row[6],
                    last_used=row[7],
                )
            return None

    async def delete_service_account(self, account_id: str) -> bool:
        """Delete a service account.

        Note: This also sets service_account_id to NULL for any buyer_seats
        that referenced this account (due to ON DELETE SET NULL).

        Args:
            account_id: The service account ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _delete():
                cursor = conn.execute(
                    "DELETE FROM service_accounts WHERE id = ?",
                    (account_id,),
                )
                conn.commit()
                return cursor.rowcount > 0

            return await loop.run_in_executor(None, _delete)

    async def update_service_account_last_used(self, account_id: str) -> None:
        """Update last_used timestamp for a service account.

        Args:
            account_id: The service account ID.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    """
                    UPDATE service_accounts
                    SET last_used = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (account_id,),
                ),
            )
            await loop.run_in_executor(None, conn.commit)

    # ==================== Buyer Seat Methods ====================

    async def save_buyer_seat(self, seat: BuyerSeat) -> None:
        """Insert or update a buyer seat.

        Args:
            seat: The BuyerSeat to save.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    """
                    INSERT OR REPLACE INTO buyer_seats (
                        buyer_id, bidder_id, service_account_id, display_name, active,
                        creative_count, last_synced, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, COALESCE(
                        (SELECT created_at FROM buyer_seats WHERE buyer_id = ?),
                        CURRENT_TIMESTAMP
                    ))
                    """,
                    (
                        seat.buyer_id,
                        seat.bidder_id,
                        seat.service_account_id,
                        seat.display_name,
                        1 if seat.active else 0,
                        seat.creative_count,
                        seat.last_synced,
                        seat.buyer_id,
                    ),
                ),
            )
            await loop.run_in_executor(None, conn.commit)

    async def get_buyer_seats(
        self,
        bidder_id: Optional[str] = None,
        active_only: bool = False,
    ) -> list[BuyerSeat]:
        """Get all buyer seats, optionally filtered by bidder_id.

        Args:
            bidder_id: Optional filter by bidder account.
            active_only: If True, only return active seats.

        Returns:
            List of BuyerSeat objects.
        """
        conditions = []
        params: list[Any] = []

        if bidder_id:
            conditions.append("bs.bidder_id = ?")
            params.append(bidder_id)
        if active_only:
            conditions.append("bs.active = 1")

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                # Use LEFT JOIN to get dynamic creative count from creatives.account_id
                cursor = conn.execute(
                    f"""
                    SELECT bs.buyer_id, bs.bidder_id, bs.service_account_id, bs.display_name, bs.active,
                           COALESCE(c.cnt, 0) as creative_count,
                           bs.last_synced, bs.created_at
                    FROM buyer_seats bs
                    LEFT JOIN (
                        SELECT account_id, COUNT(*) as cnt
                        FROM creatives
                        GROUP BY account_id
                    ) c ON c.account_id = bs.buyer_id
                    WHERE {where_clause}
                    ORDER BY bs.display_name, bs.buyer_id
                    """,
                    params,
                )
                return cursor.fetchall()

            rows = await loop.run_in_executor(None, _query)

        return [
            BuyerSeat(
                buyer_id=row[0],
                bidder_id=row[1],
                service_account_id=row[2],
                display_name=row[3],
                active=bool(row[4]),
                creative_count=row[5] or 0,
                last_synced=row[6],
                created_at=row[7],
            )
            for row in rows
        ]

    async def get_buyer_seat(self, buyer_id: str) -> Optional[BuyerSeat]:
        """Get a specific buyer seat.

        Args:
            buyer_id: The buyer ID.

        Returns:
            BuyerSeat object or None if not found.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(
                    """
                    SELECT buyer_id, bidder_id, service_account_id, display_name, active,
                           creative_count, last_synced, created_at
                    FROM buyer_seats
                    WHERE buyer_id = ?
                    """,
                    (buyer_id,),
                )
                return cursor.fetchone()

            row = await loop.run_in_executor(None, _query)

            if row:
                return BuyerSeat(
                    buyer_id=row[0],
                    bidder_id=row[1],
                    service_account_id=row[2],
                    display_name=row[3],
                    active=bool(row[4]),
                    creative_count=row[5] or 0,
                    last_synced=row[6],
                    created_at=row[7],
                )
            return None

    async def update_seat_creative_count(self, buyer_id: str) -> int:
        """Update the creative_count for a buyer seat by counting creatives.

        Args:
            buyer_id: The buyer ID to update.

        Returns:
            The updated creative count.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _count_and_update():
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM creatives WHERE buyer_id = ?",
                    (buyer_id,),
                )
                count = cursor.fetchone()[0]

                conn.execute(
                    """
                    UPDATE buyer_seats
                    SET creative_count = ?
                    WHERE buyer_id = ?
                    """,
                    (count, buyer_id),
                )
                conn.commit()
                return count

            count = await loop.run_in_executor(None, _count_and_update)
            return count

    async def update_seat_sync_time(self, buyer_id: str) -> None:
        """Update last_synced timestamp for a buyer seat.

        Args:
            buyer_id: The buyer ID to update.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    """
                    UPDATE buyer_seats
                    SET last_synced = CURRENT_TIMESTAMP
                    WHERE buyer_id = ?
                    """,
                    (buyer_id,),
                ),
            )
            await loop.run_in_executor(None, conn.commit)

    async def populate_buyer_seats_from_creatives(self) -> int:
        """Populate buyer_seats table from existing creatives.

        Creates buyer_seat records for each unique account_id found in creatives
        that doesn't already exist in buyer_seats.

        Returns:
            Number of buyer seats created.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _populate():
                # Get unique account_ids from creatives that aren't already in buyer_seats
                cursor = conn.execute("""
                    SELECT DISTINCT c.account_id, c.advertiser_name
                    FROM creatives c
                    WHERE c.account_id IS NOT NULL
                    AND c.account_id NOT IN (SELECT buyer_id FROM buyer_seats)
                """)
                accounts = cursor.fetchall()

                created = 0
                for account_id, advertiser_name in accounts:
                    # Use advertiser_name as display_name if available
                    display_name = advertiser_name or f"Account {account_id}"
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO buyer_seats
                        (buyer_id, bidder_id, display_name, active, creative_count, created_at)
                        VALUES (?, ?, ?, 1, 0, CURRENT_TIMESTAMP)
                        """,
                        (account_id, account_id, display_name),
                    )
                    created += 1

                conn.commit()
                return created

            return await loop.run_in_executor(None, _populate)

    async def update_buyer_seat_display_name(
        self, buyer_id: str, display_name: str
    ) -> bool:
        """Update the display name for a buyer seat.

        Args:
            buyer_id: The buyer ID to update.
            display_name: The new display name.

        Returns:
            True if updated, False if not found.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()

            def _update():
                cursor = conn.execute(
                    """
                    UPDATE buyer_seats
                    SET display_name = ?
                    WHERE buyer_id = ?
                    """,
                    (display_name, buyer_id),
                )
                conn.commit()
                return cursor.rowcount > 0

            return await loop.run_in_executor(None, _update)

    async def link_buyer_seat_to_service_account(
        self,
        buyer_id: str,
        service_account_id: str,
    ) -> None:
        """Link a buyer seat to a service account.

        Args:
            buyer_id: The buyer seat ID.
            service_account_id: The service account ID to link.
        """
        async with self._connection() as conn:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: conn.execute(
                    """
                    UPDATE buyer_seats
                    SET service_account_id = ?
                    WHERE buyer_id = ?
                    """,
                    (service_account_id, buyer_id),
                ),
            )
            await loop.run_in_executor(None, conn.commit)
