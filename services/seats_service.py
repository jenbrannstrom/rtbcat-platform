"""Seats Service - Business logic for buyer seats and service accounts.

Handles seat management, credential resolution, and sync orchestration.
SQL operations delegated to SeatsRepository.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Any

from storage.postgres_repositories.seats_repo import SeatsRepository

logger = logging.getLogger(__name__)


def is_gcp_mode() -> bool:
    """Check if running in GCP mode with ADC (OAuth2 Proxy enabled)."""
    return os.environ.get("OAUTH2_PROXY_ENABLED", "").lower() in ("1", "true", "yes")


@dataclass
class BuyerSeat:
    """Buyer seat data object."""
    buyer_id: str
    bidder_id: str
    display_name: Optional[str] = None
    active: bool = True
    creative_count: int = 0
    last_synced: Optional[datetime] = None
    created_at: Optional[datetime] = None
    service_account_id: Optional[str] = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "BuyerSeat":
        """Create from database row."""
        return cls(
            buyer_id=row["buyer_id"],
            bidder_id=row["bidder_id"],
            display_name=row.get("display_name"),
            active=row.get("active", True),
            creative_count=row.get("creative_count", 0),
            last_synced=row.get("last_synced"),
            created_at=row.get("created_at"),
            service_account_id=row.get("service_account_id"),
        )

    def to_response_dict(self) -> dict[str, Any]:
        """Convert to response-ready dict with formatted datetime fields."""
        return {
            "buyer_id": self.buyer_id,
            "bidder_id": self.bidder_id,
            "display_name": self.display_name,
            "active": self.active,
            "creative_count": self.creative_count,
            "last_synced": _format_datetime(self.last_synced),
            "created_at": _format_datetime(self.created_at),
        }


def _format_datetime(dt: Optional[datetime | str]) -> Optional[str]:
    """Format datetime to ISO string for response."""
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    return dt.isoformat()


@dataclass
class ServiceAccount:
    """Service account data object."""
    id: str
    client_email: str
    project_id: str
    display_name: Optional[str] = None
    credentials_path: Optional[str] = None
    is_active: bool = True
    last_used: Optional[datetime] = None
    created_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "ServiceAccount":
        """Create from database row."""
        return cls(
            id=row["id"],
            client_email=row["client_email"],
            project_id=row["project_id"],
            display_name=row.get("display_name"),
            credentials_path=row.get("credentials_path"),
            is_active=row.get("is_active", True),
            last_used=row.get("last_used"),
            created_at=row.get("created_at"),
        )


class SeatsService:
    """Service for buyer seat and service account management."""

    def __init__(self, repo: Optional[SeatsRepository] = None):
        self.repo = repo or SeatsRepository()

    # =========================================================================
    # Buyer Seats
    # =========================================================================

    async def get_buyer_seats(
        self,
        bidder_id: Optional[str] = None,
        active_only: bool = True,
    ) -> list[BuyerSeat]:
        """Get all buyer seats."""
        rows = await self.repo.get_buyer_seats(bidder_id, active_only)
        return [BuyerSeat.from_row(row) for row in rows]

    async def get_buyer_seats_for_service_accounts(
        self,
        service_account_ids: list[str],
        bidder_id: Optional[str] = None,
        active_only: bool = True,
    ) -> list[BuyerSeat]:
        """Get buyer seats linked to specific service accounts."""
        rows = await self.repo.get_buyer_seats_for_service_accounts(
            service_account_ids, bidder_id, active_only
        )
        return [BuyerSeat.from_row(row) for row in rows]

    async def get_buyer_seat(self, buyer_id: str) -> Optional[BuyerSeat]:
        """Get a single buyer seat."""
        row = await self.repo.get_buyer_seat(buyer_id)
        return BuyerSeat.from_row(row) if row else None

    async def save_buyer_seat(self, seat: BuyerSeat) -> None:
        """Save a buyer seat."""
        await self.repo.save_buyer_seat(
            buyer_id=seat.buyer_id,
            bidder_id=seat.bidder_id,
            display_name=seat.display_name,
            active=seat.active,
            service_account_id=seat.service_account_id,
        )

    async def update_display_name(self, buyer_id: str, display_name: str) -> bool:
        """Update a buyer seat's display name."""
        return await self.repo.update_buyer_seat_display_name(buyer_id, display_name)

    async def update_seat_after_sync(self, buyer_id: str) -> None:
        """Update seat metadata after a sync operation."""
        await self.repo.update_seat_creative_count(buyer_id)
        await self.repo.update_seat_sync_time(buyer_id)

    async def link_to_service_account(
        self, buyer_id: str, service_account_id: str
    ) -> None:
        """Link a buyer seat to a service account."""
        await self.repo.link_buyer_seat_to_service_account(buyer_id, service_account_id)

    async def get_distinct_bidder_ids(self) -> list[str]:
        """Get all unique bidder IDs."""
        return await self.repo.get_distinct_bidder_ids()

    async def populate_from_creatives(self) -> int:
        """Populate buyer seats from existing creatives."""
        return await self.repo.populate_buyer_seats_from_creatives()

    # =========================================================================
    # Service Accounts
    # =========================================================================

    async def get_service_accounts(
        self, active_only: bool = True
    ) -> list[ServiceAccount]:
        """Get all service accounts."""
        rows = await self.repo.get_service_accounts(active_only)
        return [ServiceAccount.from_row(row) for row in rows]

    async def get_service_account(self, account_id: str) -> Optional[ServiceAccount]:
        """Get a single service account."""
        row = await self.repo.get_service_account(account_id)
        return ServiceAccount.from_row(row) if row else None

    async def update_service_account_last_used(self, account_id: str) -> None:
        """Update last_used timestamp for a service account."""
        await self.repo.update_service_account_last_used(account_id)

    async def get_bidder_id_for_service_account(
        self, service_account_id: str
    ) -> Optional[str]:
        """Get bidder_id for a service account from buyer_seats."""
        return await self.repo.get_bidder_id_for_service_account(service_account_id)

    async def get_first_bidder_id(self) -> Optional[str]:
        """Get the first available bidder_id (for single-account scenarios)."""
        return await self.repo.get_first_bidder_id()

    async def get_buyer_seat_with_bidder(self, buyer_id: str) -> Optional[dict]:
        """Get buyer seat info including bidder_id and display_name."""
        return await self.repo.get_buyer_seat_with_bidder(buyer_id)

    # =========================================================================
    # Credential Resolution
    # =========================================================================

    async def get_credentials_for_seat(
        self, seat: BuyerSeat
    ) -> Optional[str]:
        """Get credentials path for a buyer seat.

        Tries credentials in order:
        1. Seat's linked service account
        2. First available active service account
        3. Returns None (caller should check legacy/ADC)

        Returns:
            Path to service account JSON file, or None.
        """
        # Try seat's linked service account
        if seat.service_account_id:
            account = await self.get_service_account(seat.service_account_id)
            if account and account.credentials_path:
                await self.update_service_account_last_used(seat.service_account_id)
                return account.credentials_path

        # Try first available service account
        accounts = await self.get_service_accounts(active_only=True)
        if accounts:
            account = accounts[0]
            # Link for future use
            await self.link_to_service_account(seat.buyer_id, account.id)
            await self.update_service_account_last_used(account.id)
            return account.credentials_path

        return None

    async def get_credentials_with_fallback(
        self,
        seat: BuyerSeat,
        config: Any,
    ) -> Optional[str]:
        """Get credentials path with full fallback chain.

        Tries credentials in order:
        1. Multi-account credentials (via service_account_id)
        2. First available service account
        3. Legacy ConfigManager credentials
        4. ADC (GCP mode) - returns None to trigger Application Default Credentials

        Args:
            seat: The buyer seat to get credentials for.
            config: ConfigManager instance for legacy fallback.

        Returns:
            Path to service account JSON file, or None for ADC mode.

        Raises:
            ValueError: If no valid credentials found and not in GCP mode.
        """
        # Try multi-account via SeatsService
        creds_path = await self.get_credentials_for_seat(seat)
        if creds_path:
            return creds_path

        # Fall back to legacy ConfigManager
        if config.is_configured():
            try:
                return str(config.get_service_account_path())
            except Exception:
                pass

        # GCP mode: use Application Default Credentials
        if is_gcp_mode():
            logger.info("Using ADC (Application Default Credentials) for GCP mode")
            return None

        raise ValueError(
            "No service account credentials configured. Add a service account in Setup."
        )
