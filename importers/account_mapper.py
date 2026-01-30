"""Account Mapper - Maps billing_id to bidder_id for multi-account support.

This module provides utilities for mapping billing IDs (pretargeting config IDs)
to their parent bidder IDs (account IDs).

The mapping is stored in the pretargeting_configs table which is populated
when the user syncs their Google Authorized Buyers account.
"""

import os
import logging
from typing import Optional

import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)


def _get_connection():
    """Get Postgres connection using POSTGRES_SERVING_DSN."""
    dsn = os.getenv("POSTGRES_SERVING_DSN", "")
    if not dsn:
        raise RuntimeError("POSTGRES_SERVING_DSN environment variable not set")
    return psycopg.connect(dsn, row_factory=dict_row)


class AccountMapper:
    """Maps billing_ids to bidder_ids using pretargeting_configs table."""

    def __init__(self):
        self._cache: dict[str, Optional[str]] = {}
        self._load_mappings()

    def _load_mappings(self) -> None:
        """Load all billing_id -> bidder_id mappings into cache."""
        try:
            conn = _get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT billing_id, bidder_id
                FROM pretargeting_configs
                WHERE billing_id IS NOT NULL AND bidder_id IS NOT NULL
            """)
            for row in cursor.fetchall():
                # Normalize billing_id (strip whitespace) to match CSV import format
                normalized_billing_id = str(row["billing_id"]).strip()
                self._cache[normalized_billing_id] = row["bidder_id"]
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

        # Normalize billing_id to match how it's stored (stripped of whitespace)
        normalized_billing_id = str(billing_id).strip()

        # Check cache first
        if normalized_billing_id in self._cache:
            return self._cache[normalized_billing_id]

        # Try database lookup (cache miss or new billing_id)
        try:
            conn = _get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT bidder_id FROM pretargeting_configs
                WHERE TRIM(billing_id) = %s
            """, (normalized_billing_id,))
            row = cursor.fetchone()
            conn.close()

            bidder_id = row["bidder_id"] if row else None
            self._cache[normalized_billing_id] = bidder_id
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
            conn = _get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT billing_id FROM pretargeting_configs
                WHERE bidder_id = %s AND billing_id IS NOT NULL
            """, (bidder_id,))
            billing_ids = [row["billing_id"] for row in cursor.fetchall()]
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
            conn = _get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT bidder_id FROM pretargeting_configs
                WHERE bidder_id IS NOT NULL
                ORDER BY bidder_id
            """)
            bidder_ids = [row["bidder_id"] for row in cursor.fetchall()]
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


def get_account_mapper() -> AccountMapper:
    """Get or create the singleton AccountMapper instance.

    Returns:
        AccountMapper instance
    """
    global _mapper
    if _mapper is None:
        _mapper = AccountMapper()
    return _mapper


def get_bidder_id_for_billing_id(billing_id: str) -> Optional[str]:
    """Convenience function to get bidder_id for a billing_id.

    Args:
        billing_id: The billing ID to look up

    Returns:
        The bidder_id, or None if not found
    """
    return get_account_mapper().get_bidder_id(billing_id)
