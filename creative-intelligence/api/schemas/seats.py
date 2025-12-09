"""Buyer seat schema models."""

from typing import Optional
from pydantic import BaseModel


class BuyerSeatResponse(BaseModel):
    """Response model for buyer seat data."""
    buyer_id: str
    bidder_id: str
    display_name: Optional[str] = None
    active: bool = True
    creative_count: int = 0
    last_synced: Optional[str] = None
    created_at: Optional[str] = None


class DiscoverSeatsRequest(BaseModel):
    """Request model for discovering buyer seats."""
    bidder_id: str


class DiscoverSeatsResponse(BaseModel):
    """Response model for seat discovery."""
    status: str
    bidder_id: str
    seats_discovered: int
    seats: list[BuyerSeatResponse]


class SyncSeatResponse(BaseModel):
    """Response model for seat sync operation."""
    status: str
    buyer_id: str
    creatives_synced: int
    message: str
