"""Service layer for analytics common/spend operations."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from storage.postgres_repositories.analytics_repo import AnalyticsRepository

logger = logging.getLogger(__name__)


@dataclass
class PrecomputeStatus:
    """Status of a precompute table."""

    table: str
    exists: bool
    has_rows: bool
    row_count: int


@dataclass
class SpendStats:
    """Spend statistics for a period."""

    period_days: int
    total_impressions: int
    total_spend_usd: float
    avg_cpm_usd: Optional[float]
    has_spend_data: bool
    precompute_status: dict[str, dict]
    message: Optional[str] = None


class AnalyticsService:
    """Orchestrates analytics queries for common/spend endpoints."""

    # Canonical <-> legacy compatibility map for staged naming rollout.
    PRECOMPUTE_TABLE_ALIASES: dict[str, str] = {
        "seat_daily": "home_seat_daily",
        "seat_geo_daily": "home_geo_daily",
        "seat_publisher_daily": "home_publisher_daily",
        "seat_size_daily": "home_size_daily",
        "pretarg_daily": "home_config_daily",
        "pretarg_size_daily": "config_size_daily",
        "pretarg_geo_daily": "config_geo_daily",
        "pretarg_publisher_daily": "config_publisher_daily",
        "pretarg_creative_daily": "config_creative_daily",
        "home_seat_daily": "seat_daily",
        "home_geo_daily": "seat_geo_daily",
        "home_publisher_daily": "seat_publisher_daily",
        "home_size_daily": "seat_size_daily",
        "home_config_daily": "pretarg_daily",
        "config_size_daily": "pretarg_size_daily",
        "config_geo_daily": "pretarg_geo_daily",
        "config_publisher_daily": "pretarg_publisher_daily",
        "config_creative_daily": "pretarg_creative_daily",
    }

    def __init__(self, repo: AnalyticsRepository | None = None) -> None:
        self._repo = repo or AnalyticsRepository()

    # =========================================================================
    # Precompute Status
    # =========================================================================

    async def get_precompute_status(
        self,
        table_name: str,
        days: int,
        filters: Optional[list[str]] = None,
        params: Optional[list] = None,
    ) -> PrecomputeStatus:
        """Check if a precompute table exists and has rows for the requested range.

        Args:
            table_name: Name of the precompute table.
            days: Number of days to check.
            filters: Additional WHERE clause filters (use %s placeholders).
            params: Parameters for the filters.

        Returns:
            PrecomputeStatus with table existence and row count.
        """
        source_table_name = table_name
        if not await self._repo.table_exists(source_table_name):
            fallback_name = self.PRECOMPUTE_TABLE_ALIASES.get(table_name)
            if fallback_name and await self._repo.table_exists(fallback_name):
                logger.info(
                    "Precompute status using fallback table %s for requested %s",
                    fallback_name,
                    table_name,
                )
                source_table_name = fallback_name
            else:
                return PrecomputeStatus(
                    table=table_name,
                    exists=False,
                    has_rows=False,
                    row_count=0,
                )

        row_count = await self._repo.get_precompute_row_count(
            source_table_name, days, filters, params
        )
        return PrecomputeStatus(
            table=table_name,
            exists=True,
            has_rows=row_count > 0,
            row_count=row_count,
        )

    # =========================================================================
    # Billing ID Resolution
    # =========================================================================

    async def get_current_bidder_id(self) -> Optional[str]:
        """Get the current bidder_id from the most recently synced pretargeting config."""
        try:
            return await self._repo.get_current_bidder_id()
        except Exception:
            return None

    async def get_valid_billing_ids(self) -> list[str]:
        """Get list of billing_ids for the current account.

        Returns only billing_ids associated with the currently active account
        to prevent cross-account data mixing.
        """
        try:
            current_bidder = await self._repo.get_current_bidder_id()

            if current_bidder:
                return await self._repo.get_billing_ids_for_bidder(current_bidder)
            else:
                # Fallback: return all billing_ids if no bidder_id found
                return await self._repo.get_all_billing_ids()
        except Exception:
            return []

    async def get_valid_billing_ids_for_buyer(
        self, buyer_id: Optional[str] = None
    ) -> list[str]:
        """Get list of billing_ids for a specific buyer seat.

        Args:
            buyer_id: The buyer seat ID to filter by. If None, returns all billing_ids.

        Returns:
            List of billing_id strings for the specified buyer.
        """
        try:
            if buyer_id:
                bidder_id = await self._repo.get_bidder_id_for_buyer(buyer_id)
                if bidder_id:
                    return await self._repo.get_billing_ids_for_bidder(bidder_id)

            # Fallback: return all billing_ids
            return await self._repo.get_all_billing_ids()
        except Exception as e:
            logger.error(f"Failed to get billing IDs for buyer {buyer_id}: {e}")
            return []

    # =========================================================================
    # Spend Stats
    # =========================================================================

    async def get_spend_stats(
        self,
        days: int,
        billing_id: Optional[str] = None,
        buyer_id: Optional[str] = None,
    ) -> SpendStats:
        """Get overall spend statistics for the selected period.

        Args:
            days: Number of days to analyze.
            billing_id: Optional specific billing account ID to filter by.
            buyer_id: Optional buyer seat ID to scope queries.

        Returns:
            SpendStats with totals and CPM calculation.
        """
        # Check precompute status first
        filters = []
        params = []
        if buyer_id:
            filters.append("buyer_account_id = %s")
            params.append(buyer_id)
        if billing_id:
            filters.append("billing_id = %s")
            params.append(billing_id)
        precompute_status = await self.get_precompute_status(
            "rtb_app_daily", days, filters or None, params or None
        )

        if not precompute_status.has_rows:
            return SpendStats(
                period_days=days,
                total_impressions=0,
                total_spend_usd=0,
                avg_cpm_usd=None,
                has_spend_data=False,
                message="No precompute available for requested date range.",
                precompute_status={
                    "rtb_app_daily": {
                        "table": precompute_status.table,
                        "exists": precompute_status.exists,
                        "has_rows": precompute_status.has_rows,
                        "row_count": precompute_status.row_count,
                    }
                },
            )

        # Fetch spend stats based on filters
        if billing_id:
            row = await self._repo.get_spend_stats_by_billing_id(days, billing_id, buyer_id)
        elif buyer_id:
            row = await self._repo.get_spend_stats_by_buyer(days, buyer_id)
        else:
            valid_billing_ids = await self.get_valid_billing_ids()
            if valid_billing_ids:
                row = await self._repo.get_spend_stats_by_billing_ids(
                    days, valid_billing_ids
                )
            else:
                row = await self._repo.get_spend_stats_all(days)

        total_impressions = row.get("total_impressions", 0) or 0
        total_spend_micros = row.get("total_spend_micros", 0) or 0
        total_spend_usd = total_spend_micros / 1_000_000

        # Calculate CPM: (spend / impressions) * 1000
        avg_cpm = None
        if total_impressions > 0 and total_spend_micros > 0:
            avg_cpm = (total_spend_usd / total_impressions) * 1000

        return SpendStats(
            period_days=days,
            total_impressions=total_impressions,
            total_spend_usd=round(total_spend_usd, 2),
            avg_cpm_usd=round(avg_cpm, 2) if avg_cpm else None,
            has_spend_data=total_spend_micros > 0,
            precompute_status={
                "rtb_app_daily": {
                    "table": precompute_status.table,
                    "exists": precompute_status.exists,
                    "has_rows": precompute_status.has_rows,
                    "row_count": precompute_status.row_count,
                }
            },
        )
