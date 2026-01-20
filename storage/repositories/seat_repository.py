"""
Seat Repository for managing buyer account/billing seat data.

Handles seat extraction from CSV imports and provides lookup functionality.
"""

import sqlite3
from typing import Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Seat:
    """Seat record for database storage."""
    id: Optional[int] = None
    billing_id: str = ""
    account_name: Optional[str] = None
    account_id: Optional[str] = None
    created_at: Optional[datetime] = None


class SeatRepository:
    """
    Repository for seat management with caching.

    Seats represent buyer accounts/billing entities extracted from CSV imports.
    Each import identifies the seat from the first row's billing columns.
    """

    def __init__(self, db_connection: sqlite3.Connection):
        """
        Initialize repository with database connection.

        Args:
            db_connection: SQLite database connection
        """
        self.db = db_connection
        self.db.row_factory = sqlite3.Row

        # In-memory cache for seat lookups
        self._cache: dict[str, int] = {}
        self._load_cache()

    def _load_cache(self) -> None:
        """Load existing seats into memory cache."""
        cursor = self.db.cursor()
        cursor.execute("SELECT id, billing_id FROM seats")
        for row in cursor.fetchall():
            self._cache[row['billing_id']] = row['id']

    def get_or_create_seat(
        self,
        billing_id: str,
        account_name: Optional[str] = None,
        account_id: Optional[str] = None,
    ) -> int:
        """
        Find existing seat or create new one.

        Args:
            billing_id: External billing account identifier (required, unique)
            account_name: Human-readable account name
            account_id: External account ID

        Returns:
            Internal seat_id (integer)
        """
        if not billing_id:
            raise ValueError("billing_id is required")

        # Check cache first
        if billing_id in self._cache:
            return self._cache[billing_id]

        cursor = self.db.cursor()

        # Try to find existing
        cursor.execute(
            "SELECT id FROM seats WHERE billing_id = ?",
            (billing_id,)
        )
        row = cursor.fetchone()

        if row:
            seat_id = row['id']
            self._cache[billing_id] = seat_id
            return seat_id

        # Create new seat
        cursor.execute("""
            INSERT INTO seats (billing_id, account_name, account_id, created_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        """, (billing_id, account_name, account_id))

        seat_id = cursor.lastrowid
        self._cache[billing_id] = seat_id
        self.db.commit()

        return seat_id

    def get_seat(self, seat_id: int) -> Optional[Seat]:
        """
        Get a seat by ID.

        Args:
            seat_id: Internal seat ID

        Returns:
            Seat object or None if not found
        """
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT * FROM seats WHERE id = ?",
            (seat_id,)
        )
        row = cursor.fetchone()

        if row:
            return Seat(
                id=row['id'],
                billing_id=row['billing_id'],
                account_name=row['account_name'],
                account_id=row['account_id'],
                created_at=row['created_at'],
            )
        return None

    def get_seat_by_billing_id(self, billing_id: str) -> Optional[Seat]:
        """
        Get a seat by billing ID.

        Args:
            billing_id: External billing account identifier

        Returns:
            Seat object or None if not found
        """
        cursor = self.db.cursor()
        cursor.execute(
            "SELECT * FROM seats WHERE billing_id = ?",
            (billing_id,)
        )
        row = cursor.fetchone()

        if row:
            return Seat(
                id=row['id'],
                billing_id=row['billing_id'],
                account_name=row['account_name'],
                account_id=row['account_id'],
                created_at=row['created_at'],
            )
        return None

    def list_seats(self) -> list[Seat]:
        """
        List all seats.

        Returns:
            List of Seat objects
        """
        cursor = self.db.cursor()
        cursor.execute("SELECT * FROM seats ORDER BY account_name, billing_id")

        return [
            Seat(
                id=row['id'],
                billing_id=row['billing_id'],
                account_name=row['account_name'],
                account_id=row['account_id'],
                created_at=row['created_at'],
            )
            for row in cursor.fetchall()
        ]

    def update_seat(
        self,
        seat_id: int,
        account_name: Optional[str] = None,
        account_id: Optional[str] = None,
    ) -> bool:
        """
        Update seat details.

        Args:
            seat_id: Internal seat ID
            account_name: New account name (or None to keep existing)
            account_id: New account ID (or None to keep existing)

        Returns:
            True if updated, False if not found
        """
        updates = []
        params = []

        if account_name is not None:
            updates.append("account_name = ?")
            params.append(account_name)

        if account_id is not None:
            updates.append("account_id = ?")
            params.append(account_id)

        if not updates:
            return False

        params.append(seat_id)

        cursor = self.db.cursor()
        cursor.execute(
            f"UPDATE seats SET {', '.join(updates)} WHERE id = ?",
            params
        )
        self.db.commit()

        return cursor.rowcount > 0

    def clear_cache(self) -> None:
        """Clear the in-memory cache."""
        self._cache.clear()
