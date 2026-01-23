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

    async def get_buyer_seats(self, bidder_id: Optional[str] = None) -> list[BuyerSeat]:
        """Get all buyer seats, optionally filtered by bidder."""
        if bidder_id:
            rows = await pg_query(
                "SELECT * FROM buyer_seats WHERE bidder_id = %s ORDER BY display_name",
                (bidder_id,)
            )
        else:
            rows = await pg_query("SELECT * FROM buyer_seats ORDER BY display_name")
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
        # TODO: Implement upsert
        logger.warning("PostgresStore.save_buyer_seat() is a stub")

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

    # =========================================================================
    # SERVICE ACCOUNT OPERATIONS
    # =========================================================================

    async def get_service_accounts(self) -> list[ServiceAccount]:
        """Get all service accounts."""
        rows = await pg_query("SELECT * FROM service_accounts ORDER BY display_name")
        return [ServiceAccount(**row) for row in rows]

    async def get_service_account(self, account_id: str) -> Optional[ServiceAccount]:
        """Get a service account by ID."""
        row = await pg_query_one(
            "SELECT * FROM service_accounts WHERE id = %s",
            (account_id,)
        )
        return ServiceAccount(**row) if row else None

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
