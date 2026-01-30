"""Campaign Aggregation Service for Phase 11.1.

Provides timeframe-aware campaign metrics and waste detection.
Business logic only - calls repo for data access.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from storage.postgres_repositories.campaign_repo import CampaignRepository


@dataclass
class CampaignMetrics:
    """Aggregated metrics for a campaign within a timeframe."""
    total_spend_micros: int = 0
    total_impressions: int = 0
    total_clicks: int = 0
    total_reached_queries: int = 0
    avg_cpm: Optional[float] = None
    avg_ctr: Optional[float] = None
    waste_score: Optional[float] = None


@dataclass
class CampaignWarnings:
    """Warning counts for a campaign."""
    broken_video_count: int = 0
    zero_engagement_count: int = 0
    high_spend_low_performance: int = 0
    disapproved_count: int = 0


@dataclass
class CampaignWithMetrics:
    """Campaign data with metrics and warnings."""
    id: str
    name: str
    creative_ids: list[str] = field(default_factory=list)
    creative_count: int = 0
    timeframe_days: int = 7
    metrics: Optional[CampaignMetrics] = None
    warnings: Optional[CampaignWarnings] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class CampaignAggregationService:
    """
    Service for aggregating campaign performance with timeframe context.
    Business logic only - calls CampaignRepository for data.
    """

    def __init__(self, repo: Optional[CampaignRepository] = None):
        self.repo = repo or CampaignRepository()

    async def get_campaigns_with_metrics(
        self,
        days: int = 7,
        include_empty: bool = True,
    ) -> list[CampaignWithMetrics]:
        """Get all campaigns with aggregated metrics for the given timeframe."""
        campaigns_raw = await self.repo.get_all_campaigns()
        results = []

        for camp_row in campaigns_raw:
            campaign_id = camp_row["id"]
            creative_ids = await self.repo.get_creative_ids_for_campaign(campaign_id)
            metrics = await self._compute_metrics(creative_ids, days)
            warnings = await self._compute_warnings(creative_ids, days)

            if not include_empty and metrics.total_impressions == 0 and metrics.total_spend_micros == 0:
                continue

            results.append(CampaignWithMetrics(
                id=campaign_id,
                name=camp_row["name"],
                creative_ids=creative_ids,
                creative_count=len(creative_ids),
                timeframe_days=days,
                metrics=metrics,
                warnings=warnings,
                created_at=str(camp_row["created_at"]) if camp_row["created_at"] else None,
                updated_at=str(camp_row["updated_at"]) if camp_row["updated_at"] else None,
            ))

        return results

    async def get_campaign_with_metrics(
        self,
        campaign_id: str,
        days: int = 7,
    ) -> Optional[CampaignWithMetrics]:
        """Get a single campaign with metrics."""
        camp_row = await self.repo.get_campaign_by_id(campaign_id)
        if not camp_row:
            return None

        creative_ids = await self.repo.get_creative_ids_for_campaign(campaign_id)
        metrics = await self._compute_metrics(creative_ids, days)
        warnings = await self._compute_warnings(creative_ids, days)

        return CampaignWithMetrics(
            id=campaign_id,
            name=camp_row["name"],
            creative_ids=creative_ids,
            creative_count=len(creative_ids),
            timeframe_days=days,
            metrics=metrics,
            warnings=warnings,
            created_at=str(camp_row["created_at"]) if camp_row["created_at"] else None,
            updated_at=str(camp_row["updated_at"]) if camp_row["updated_at"] else None,
        )

    async def _compute_metrics(
        self, creative_ids: list[str], days: int
    ) -> CampaignMetrics:
        """Compute aggregated metrics - business logic."""
        if not creative_ids:
            return CampaignMetrics()

        data = await self.repo.get_campaign_metrics(creative_ids, days)

        total_spend = data["total_spend"] or 0
        total_impressions = data["total_impressions"] or 0
        total_clicks = data["total_clicks"] or 0
        total_reached = data["total_reached"] or 0

        avg_cpm = None
        if total_impressions > 0:
            avg_cpm = (total_spend / 1_000_000) / total_impressions * 1000

        avg_ctr = None
        if total_impressions > 0:
            avg_ctr = total_clicks / total_impressions * 100

        waste_score = None
        if total_reached > 0:
            waste_score = (total_reached - total_impressions) / total_reached * 100

        return CampaignMetrics(
            total_spend_micros=total_spend,
            total_impressions=total_impressions,
            total_clicks=total_clicks,
            total_reached_queries=total_reached,
            avg_cpm=round(avg_cpm, 2) if avg_cpm else None,
            avg_ctr=round(avg_ctr, 4) if avg_ctr else None,
            waste_score=round(waste_score, 2) if waste_score else None,
        )

    async def _compute_warnings(
        self, creative_ids: list[str], days: int
    ) -> CampaignWarnings:
        """Compute warning counts - business logic."""
        if not creative_ids:
            return CampaignWarnings()

        broken_video_count = await self.repo.get_broken_video_count(creative_ids)
        zero_engagement_count = await self.repo.get_zero_engagement_count(creative_ids, days)
        high_spend_low_perf = await self.repo.get_high_spend_low_perf_count(creative_ids, days)
        disapproved_count = await self.repo.get_disapproved_count(creative_ids)

        return CampaignWarnings(
            broken_video_count=broken_video_count,
            zero_engagement_count=zero_engagement_count,
            high_spend_low_performance=high_spend_low_perf,
            disapproved_count=disapproved_count,
        )

    async def get_unclustered_with_activity(self, days: int = 7) -> list[str]:
        """Get unclustered creative IDs that have activity in timeframe."""
        return await self.repo.get_unclustered_with_activity(days)
