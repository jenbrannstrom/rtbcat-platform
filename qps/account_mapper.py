"""Account Mapper - Maps billing_id to bidder_id for multi-account support.

This module provides utilities for mapping billing IDs (pretargeting config IDs)
to their parent bidder IDs (account IDs).

The mapping is stored in the pretargeting_configs table which is populated
when the user syncs their Google Authorized Buyers account.
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional
from functools import lru_cache

logger = logging.getLogger(__name__)

# Default database path
DB_PATH = Path.home() / ".catscan" / "catscan.db"


class AccountMapper:
    """Maps billing_ids to bidder_ids using pretargeting_configs table."""

    def __init__(self, db_path: str | Path = DB_PATH):
        self.db_path = str(db_path)
        self._cache: dict[str, Optional[str]] = {}
        self._load_mappings()

    def _load_mappings(self) -> None:
        """Load all billing_id -> bidder_id mappings into cache."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT billing_id, bidder_id
                FROM pretargeting_configs
                WHERE billing_id IS NOT NULL AND bidder_id IS NOT NULL
            """)
            for row in cursor.fetchall():
                self._cache[row[0]] = row[1]
            conn.close()
            logger.debug(f"Loaded {len(self._cache)} billing_id -> bidder_id mappings")
        except Exception as e:
            logger.warning(f"Failed to load account mappings: {e}")

    def get_bidder_id(self, billing_id: str) -> Optional[str]:
        """Get bidder_id for a billing_id.

        Args:
            billing_id: The pretargeting config billing ID

        Returns:
            The parent bidder_id (account ID), or None if not found
        """
        if not billing_id:
            return None

        # Check cache first
        if billing_id in self._cache:
            return self._cache[billing_id]

        # Try database lookup (cache miss or new billing_id)
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT bidder_id FROM pretargeting_configs
                WHERE billing_id = ?
            """, (billing_id,))
            row = cursor.fetchone()
            conn.close()

            bidder_id = row[0] if row else None
            self._cache[billing_id] = bidder_id
            return bidder_id
        except Exception as e:
            logger.warning(f"Failed to lookup bidder_id for billing_id {billing_id}: {e}")
            return None

    def get_bidder_id_for_billing_ids(self, billing_ids: list[str]) -> Optional[str]:
        """Get common bidder_id for a list of billing_ids.

        If all billing_ids map to the same bidder_id, return it.
        If they map to different bidders, return None (ambiguous).
        If no mapping found for any, return None.

        Args:
            billing_ids: List of billing IDs to check

        Returns:
            The common bidder_id, or None if ambiguous/not found
        """
        if not billing_ids:
            return None

        bidder_ids = set()
        for billing_id in billing_ids:
            bidder_id = self.get_bidder_id(billing_id)
            if bidder_id:
                bidder_ids.add(bidder_id)

        # Return the bidder_id if all map to the same one
        if len(bidder_ids) == 1:
            return bidder_ids.pop()

        # Ambiguous or not found
        return None

    def get_all_billing_ids_for_bidder(self, bidder_id: str) -> list[str]:
        """Get all billing_ids that belong to a bidder.

        Args:
            bidder_id: The bidder/account ID

        Returns:
            List of billing_ids belonging to this bidder
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT billing_id FROM pretargeting_configs
                WHERE bidder_id = ? AND billing_id IS NOT NULL
            """, (bidder_id,))
            billing_ids = [row[0] for row in cursor.fetchall()]
            conn.close()
            return billing_ids
        except Exception as e:
            logger.warning(f"Failed to get billing_ids for bidder {bidder_id}: {e}")
            return []

    def get_all_bidder_ids(self) -> list[str]:
        """Get all unique bidder_ids (accounts) in the system.

        Returns:
            List of unique bidder_ids
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT bidder_id FROM pretargeting_configs
                WHERE bidder_id IS NOT NULL
                ORDER BY bidder_id
            """)
            bidder_ids = [row[0] for row in cursor.fetchall()]
            conn.close()
            return bidder_ids
        except Exception as e:
            logger.warning(f"Failed to get bidder_ids: {e}")
            return []

    def refresh_cache(self) -> None:
        """Refresh the billing_id -> bidder_id cache from database."""
        self._cache.clear()
        self._load_mappings()


# Module-level singleton for convenience
_mapper: Optional[AccountMapper] = None


def get_account_mapper(db_path: str | Path = DB_PATH) -> AccountMapper:
    """Get or create the singleton AccountMapper instance.

    Args:
        db_path: Database path (only used on first call)

    Returns:
        AccountMapper instance
    """
    global _mapper
    if _mapper is None:
        _mapper = AccountMapper(db_path)
    return _mapper


def get_bidder_id_for_billing_id(billing_id: str, db_path: str | Path = DB_PATH) -> Optional[str]:
    """Convenience function to get bidder_id for a billing_id.

    Args:
        billing_id: The billing ID to look up
        db_path: Database path

    Returns:
        The bidder_id, or None if not found
    """
    return get_account_mapper(db_path).get_bidder_id(billing_id)
