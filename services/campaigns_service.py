"""Business logic for campaign management and clustering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from storage.postgres_repositories.campaign_repo import CampaignRepository


@dataclass
class AICampaign:
    """AI-generated campaign record."""

    id: str
    name: str
    seat_id: Optional[int] = None
    description: Optional[str] = None
    ai_generated: bool = True
    ai_confidence: Optional[float] = None
    clustering_method: Optional[str] = None
    status: str = "active"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    creative_count: int = 0


class CampaignsService:
    """Service layer for campaign management."""

    def __init__(self, repo: CampaignRepository | None = None) -> None:
        self._repo = repo or CampaignRepository()

    # ==================== Campaign CRUD ====================

    async def create_campaign(
        self,
        name: str,
        seat_id: Optional[int] = None,
        description: Optional[str] = None,
        ai_generated: bool = True,
        ai_confidence: Optional[float] = None,
        clustering_method: Optional[str] = None,
    ) -> str:
        """Create a new campaign. Returns campaign ID."""
        return await self._repo.create_campaign(
            name=name,
            seat_id=seat_id,
            description=description,
            ai_generated=ai_generated,
            ai_confidence=ai_confidence,
            clustering_method=clustering_method,
        )

    async def get_campaign(self, campaign_id: str) -> Optional[AICampaign]:
        """Get a campaign by ID."""
        row = await self._repo.get_campaign(campaign_id)
        return self._row_to_campaign(row) if row else None

    async def list_campaigns(
        self,
        seat_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AICampaign]:
        """List campaigns with optional filtering."""
        rows = await self._repo.list_campaigns(
            seat_id=seat_id, status=status, limit=limit, offset=offset
        )
        return [self._row_to_campaign(r) for r in rows]

    async def update_campaign(
        self,
        campaign_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        status: Optional[str] = None,
    ) -> bool:
        """Update a campaign."""
        return await self._repo.update_campaign(
            campaign_id=campaign_id, name=name, description=description, status=status
        )

    async def delete_campaign(self, campaign_id: str) -> bool:
        """Delete a campaign and its assignments."""
        return await self._repo.delete_campaign(campaign_id)

    # ==================== Creative Assignment ====================

    async def assign_creative(
        self,
        creative_id: str,
        campaign_id: str,
        assigned_by: str = "ai",
        manually_assigned: bool = False,
    ) -> bool:
        """Assign a creative to a campaign."""
        return await self._repo.assign_creative_to_campaign(
            creative_id=creative_id,
            campaign_id=campaign_id,
            assigned_by=assigned_by,
            manually_assigned=manually_assigned,
        )

    async def assign_creatives_batch(
        self,
        creative_ids: list[str],
        campaign_id: str,
        assigned_by: str = "ai",
        manually_assigned: bool = False,
    ) -> int:
        """Batch assign creatives to a campaign."""
        return await self._repo.assign_creatives_batch(
            creative_ids=creative_ids,
            campaign_id=campaign_id,
            assigned_by=assigned_by,
            manually_assigned=manually_assigned,
        )

    async def remove_creative(self, creative_id: str) -> bool:
        """Remove a creative from its campaign."""
        return await self._repo.remove_creative_from_campaign(creative_id)

    async def get_campaign_creatives(self, campaign_id: str) -> list[str]:
        """Get all creative IDs in a campaign."""
        return await self._repo.get_campaign_creatives(campaign_id)

    # ==================== Performance ====================

    async def get_campaign_performance(self, campaign_id: str, days: int = 7) -> dict[str, Any]:
        """Get aggregated performance for a campaign."""
        return await self._repo.get_campaign_performance(campaign_id, days)

    async def get_campaign_country_breakdown(
        self, campaign_id: str, days: int = 7
    ) -> dict[str, dict[str, Any]]:
        """Get country breakdown for a campaign."""
        return await self._repo.get_campaign_country_breakdown(campaign_id, days)

    async def get_campaign_daily_trend(self, campaign_id: str, days: int = 30) -> list[dict[str, Any]]:
        """Get daily performance trend for a campaign."""
        return await self._repo.get_campaign_daily_trend(campaign_id, days)

    async def update_campaign_summary(self, campaign_id: str, date: str) -> None:
        """Recalculate campaign daily summary."""
        await self._repo.update_campaign_summary(campaign_id, date)

    async def refresh_all_summaries(self, seat_id: Optional[int] = None) -> dict[str, int]:
        """Refresh summaries for all campaigns. Returns {campaigns, dates} counts."""
        campaigns = await self.list_campaigns(seat_id=seat_id)
        dates = await self._repo.get_distinct_metric_dates(limit=30)

        for campaign in campaigns:
            for date in dates:
                await self._repo.update_campaign_summary(campaign.id, date)

        return {"campaigns": len(campaigns), "dates": len(dates)}

    # ==================== Waste Metrics ====================

    async def count_disapproved_creatives(self, creative_ids: list[str]) -> int:
        """Count disapproved creatives in a list."""
        return await self._repo.count_disapproved_in_list(creative_ids)

    # ==================== Unclustered Creatives ====================

    async def get_unclustered_creatives(
        self, buyer_id: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Get unclustered creatives with app/URL info for clustering."""
        return await self._repo.get_unclustered_creatives(buyer_id)

    async def get_unclustered_creative_ids(
        self, buyer_id: Optional[str] = None
    ) -> list[str]:
        """Get IDs of unclustered creatives."""
        return await self._repo.get_unclustered_creative_ids(buyer_id)

    async def get_creative_countries(
        self, creative_ids: list[str], days: int = 30
    ) -> dict[str, str]:
        """Get primary country (by spend) for each creative."""
        return await self._repo.get_creative_countries(creative_ids, days)

    # ==================== Helpers ====================

    @staticmethod
    def _row_to_campaign(row: dict[str, Any]) -> AICampaign:
        """Convert database row to AICampaign dataclass."""
        return AICampaign(
            id=row["id"],
            name=row["name"],
            seat_id=row.get("seat_id"),
            description=row.get("description"),
            ai_generated=bool(row.get("ai_generated", True)),
            ai_confidence=row.get("ai_confidence"),
            clustering_method=row.get("clustering_method"),
            status=row.get("status") or "active",
            created_at=str(row["created_at"]) if row.get("created_at") else None,
            updated_at=str(row["updated_at"]) if row.get("updated_at") else None,
            creative_count=row.get("computed_count", row.get("creative_count", 0)) or 0,
        )
