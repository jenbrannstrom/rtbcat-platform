"""FastAPI router for Campaign Clustering endpoints.

This module provides REST API endpoints for:
- Auto-clustering creatives into campaigns
- Managing campaigns
- Campaign performance aggregation
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from storage.database import db_query, db_transaction_async, DB_PATH
from storage.campaign_repository import CampaignRepository, AICampaign
from api.clustering.rule_based import pre_cluster_creatives, merge_small_clusters
from api.clustering.ai_clusterer import AICampaignClusterer, apply_ai_suggestions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


# ============================================
# Request/Response Models
# ============================================

class CountryBreakdownEntry(BaseModel):
    """Country breakdown entry for a campaign."""
    creative_ids: list[str] = []
    spend_micros: int = 0
    impressions: int = 0


class AICampaignResponse(BaseModel):
    """Response model for AI campaign."""
    id: str
    seat_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    ai_generated: bool = True
    ai_confidence: Optional[float] = None
    clustering_method: Optional[str] = None
    status: str = "active"
    creative_count: int = 0
    creative_ids: list[str] = []  # Added for frontend compatibility
    country_breakdown: Optional[dict[str, CountryBreakdownEntry]] = None  # Phase 22
    performance: Optional[dict] = None


class AutoClusterRequest(BaseModel):
    """Request body for auto-clustering."""
    by_url: bool = True
    by_country: bool = False
    buyer_id: Optional[str] = None  # Filter by buyer_id for multi-account support


class ClusterSuggestion(BaseModel):
    """A suggested campaign cluster."""
    suggested_name: str
    creative_ids: list[str]
    domain: Optional[str] = None
    country: Optional[str] = None


class AutoClusterResponse(BaseModel):
    """Response model for auto-cluster suggestions."""
    suggestions: list[ClusterSuggestion]
    unclustered_count: int


class CampaignCreateRequest(BaseModel):
    """Request for creating a new campaign."""
    name: str
    creative_ids: list[str] = []
    description: Optional[str] = None


class CampaignUpdateRequest(BaseModel):
    """Request for updating campaign."""
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


class AssignCreativesRequest(BaseModel):
    """Request for assigning creatives."""
    creative_ids: list[str]


class MoveCreativeRequest(BaseModel):
    """Request for moving a creative."""
    to_campaign_id: str


class CampaignPerformanceResponse(BaseModel):
    """Response for campaign performance."""
    impressions: int = 0
    clicks: int = 0
    spend: float = 0
    queries: int = 0
    win_rate: Optional[float] = None
    ctr: Optional[float] = None
    cpm: Optional[float] = None


# ============================================
# Helper Functions
# ============================================

# Note: get_db_connection() and get_campaign_repo() removed
# All endpoints now use db_transaction_async() for thread-safe database access


# ============================================
# Clustering Endpoints
# ============================================

async def _get_creative_countries(creative_ids: list[str], days: int = 30) -> dict[str, str]:
    """Get the primary country (by spend) for each creative."""
    if not creative_ids:
        return {}

    placeholders = ",".join("?" * len(creative_ids))
    rows = await db_query(f"""
        WITH ranked AS (
            SELECT creative_id, geography,
                   SUM(spend_micros) as total_spend,
                   ROW_NUMBER() OVER (
                       PARTITION BY creative_id
                       ORDER BY SUM(spend_micros) DESC
                   ) as rn
            FROM performance_metrics
            WHERE creative_id IN ({placeholders})
              AND geography IS NOT NULL
              AND metric_date >= date('now', '-{days} days')
            GROUP BY creative_id, geography
        )
        SELECT creative_id, geography
        FROM ranked
        WHERE rn = 1
    """, tuple(creative_ids))

    return {row['creative_id']: row['geography'] for row in rows}


def _split_clusters_by_country(
    clusters: dict[str, list[dict]],
    creative_countries: dict[str, str],
) -> dict[str, list[dict]]:
    """Split clusters by country, creating 'domain:example.com:US' style keys."""
    result: dict[str, list[dict]] = {}

    for cluster_key, creatives in clusters.items():
        # Group by country within this cluster
        by_country: dict[str, list[dict]] = {}
        for creative in creatives:
            country = creative_countries.get(creative["id"], "UNKNOWN")
            if country not in by_country:
                by_country[country] = []
            by_country[country].append(creative)

        # Create new cluster keys with country suffix
        for country, country_creatives in by_country.items():
            new_key = f"{cluster_key}:{country}"
            result[new_key] = country_creatives

    return result


@router.post("/auto-cluster", response_model=AutoClusterResponse)
async def auto_cluster_creatives(request: AutoClusterRequest):
    """
    Auto-cluster unclustered creatives by destination URL (and optionally country).

    Returns suggested clusters without saving them. User must confirm to create.
    Supports buyer_id filtering for multi-account scenarios.
    """
    try:
        # Build query for unclustered creatives, optionally filtered by buyer_id
        if request.buyer_id:
            rows = await db_query("""
                SELECT c.id as creative_id, c.final_url, c.buyer_id
                FROM creatives c
                LEFT JOIN creative_campaigns cc ON c.id = cc.creative_id
                WHERE cc.creative_id IS NULL
                  AND c.buyer_id = ?
                ORDER BY c.id
            """, (request.buyer_id,))
        else:
            rows = await db_query("""
                SELECT c.id as creative_id, c.final_url, c.buyer_id
                FROM creatives c
                LEFT JOIN creative_campaigns cc ON c.id = cc.creative_id
                WHERE cc.creative_id IS NULL
                ORDER BY c.id
            """)

        unclustered_count = len(rows)

        if not rows:
            return AutoClusterResponse(suggestions=[], unclustered_count=0)

        logger.info(f"Found {unclustered_count} unclustered creatives for buyer_id={request.buyer_id}")

        # Group by final_url (domain extraction)
        from urllib.parse import urlparse
        from collections import defaultdict

        url_groups: dict[str, list[str]] = defaultdict(list)

        for row in rows:
            creative_id = str(row['creative_id'])
            final_url = row['final_url'] or ''

            # Extract domain from URL
            domain = None
            if final_url:
                try:
                    parsed = urlparse(final_url)
                    domain = parsed.netloc or parsed.path.split('/')[0]
                    # Clean up domain
                    domain = domain.replace('www.', '').lower()
                except Exception:
                    domain = final_url[:50]

            if not domain:
                domain = 'unknown'

            url_groups[domain].append(creative_id)

        # Generate cluster suggestions
        suggestions: list[ClusterSuggestion] = []

        for domain, creative_ids in url_groups.items():
            if len(creative_ids) < 1:
                continue

            # Generate a clean name from domain
            suggested_name = _generate_name_from_domain(domain)

            suggestions.append(ClusterSuggestion(
                suggested_name=suggested_name,
                creative_ids=creative_ids,
                domain=domain,
                country=None,  # Could be populated if by_country is True
            ))

        # Sort by number of creatives (largest first)
        suggestions.sort(key=lambda s: len(s.creative_ids), reverse=True)

        return AutoClusterResponse(
            suggestions=suggestions,
            unclustered_count=unclustered_count,
        )

    except Exception as e:
        logger.error(f"Auto-clustering failed: {e}")
        raise HTTPException(status_code=500, detail=f"Clustering failed: {str(e)}")


def _generate_name_from_domain(domain: str) -> str:
    """Generate a clean campaign name from a domain."""
    if not domain or domain == 'unknown':
        return 'Unknown'

    # Handle app store URLs
    if 'play.google.com' in domain:
        return 'Google Play'
    if 'apps.apple.com' in domain or 'itunes.apple.com' in domain:
        return 'App Store'
    if 'app.appsflyer.com' in domain:
        return 'AppsFlyer'
    if 'app.adjust.com' in domain or 'adjust.com' in domain:
        return 'Adjust'

    # Handle bundle IDs (com.example.app)
    if domain.startswith('com.') or domain.startswith('org.') or domain.startswith('io.'):
        parts = domain.split('.')
        if len(parts) >= 3:
            # Take the last two meaningful parts
            name_parts = parts[-2:]
            name = ' '.join(p.replace('_', ' ').replace('-', ' ').title() for p in name_parts)
            return name
        return domain.split('.')[-1].title()

    # Clean up domain
    # Remove common TLDs
    for tld in ['.com', '.io', '.app', '.net', '.org', '.co', '.me']:
        if domain.endswith(tld):
            domain = domain[:-len(tld)]
            break

    # Convert to title case, replace separators with spaces
    name = domain.replace('.', ' ').replace('-', ' ').replace('_', ' ')
    name = ' '.join(word.capitalize() for word in name.split())

    return name or 'Unknown'


# ============================================
# Campaign CRUD Endpoints
# ============================================

@router.get("", response_model=list[AICampaignResponse])
async def list_campaigns(
    seat_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    include_performance: bool = Query(True),
    include_country_breakdown: bool = Query(False, description="Include country breakdown per campaign"),
    period: str = Query("7d"),
):
    """
    List all AI campaigns with optional performance data.

    Phase 22: Country-aware clustering support via include_country_breakdown.
    """
    try:
        days = {"1d": 1, "7d": 7, "30d": 30, "all": 365}.get(period, 7)

        def _list_campaigns(conn):
            repo = CampaignRepository(conn)
            campaigns = repo.list_campaigns(seat_id=seat_id, status=status)

            result = []
            for campaign in campaigns:
                # Get creative IDs for this campaign
                creative_ids = repo.get_campaign_creatives(campaign.id)

                campaign_data = {
                    "id": campaign.id,
                    "seat_id": campaign.seat_id,
                    "name": campaign.name,
                    "description": campaign.description,
                    "ai_generated": campaign.ai_generated,
                    "ai_confidence": campaign.ai_confidence,
                    "clustering_method": campaign.clustering_method,
                    "status": campaign.status,
                    "creative_count": campaign.creative_count,
                    "creative_ids": creative_ids,
                    "performance": None,
                    "country_breakdown": None,
                }

                if include_performance:
                    perf = repo.get_campaign_performance(campaign.id, days=days)
                    campaign_data["performance"] = perf

                if include_country_breakdown:
                    breakdown_raw = repo.get_campaign_country_breakdown(campaign.id, days=days)
                    campaign_data["country_breakdown"] = {
                        country: {
                            "creative_ids": data['creative_ids'],
                            "spend_micros": data['spend_micros'],
                            "impressions": data['impressions'],
                        }
                        for country, data in breakdown_raw.items()
                    }

                result.append(campaign_data)

            return result

        campaigns_data = await db_transaction_async(_list_campaigns)
        return [AICampaignResponse(**c) for c in campaigns_data]

    except Exception as e:
        logger.error(f"Failed to list campaigns: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("", response_model=AICampaignResponse)
async def create_campaign(request: CampaignCreateRequest):
    """
    Create a new campaign and optionally assign creatives to it.
    """
    try:
        def _create_campaign(conn):
            repo = CampaignRepository(conn)

            # Create the campaign
            campaign_id = repo.create_campaign(
                name=request.name,
                seat_id=None,  # Could be added to request if needed
                description=request.description,
                ai_generated=False,
                ai_confidence=None,
                clustering_method="manual",
            )

            # Assign creatives if provided
            if request.creative_ids:
                repo.assign_creatives_batch(
                    creative_ids=request.creative_ids,
                    campaign_id=campaign_id,
                    assigned_by="user",
                    manually_assigned=True,
                )

            # Fetch the created campaign
            campaign = repo.get_campaign(campaign_id)
            creative_ids = repo.get_campaign_creatives(campaign_id)

            return {
                "id": campaign.id,
                "seat_id": campaign.seat_id,
                "name": campaign.name,
                "description": campaign.description,
                "ai_generated": campaign.ai_generated,
                "ai_confidence": campaign.ai_confidence,
                "clustering_method": campaign.clustering_method,
                "status": campaign.status,
                "creative_count": len(creative_ids),
                "creative_ids": creative_ids,
            }

        campaign_data = await db_transaction_async(_create_campaign)
        return AICampaignResponse(**campaign_data)

    except Exception as e:
        logger.error(f"Failed to create campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{campaign_id}", response_model=AICampaignResponse)
async def get_campaign(
    campaign_id: str,
    include_creatives: bool = Query(False),
):
    """
    Get campaign details.
    """
    try:
        def _get_campaign(conn):
            repo = CampaignRepository(conn)
            campaign = repo.get_campaign(campaign_id)

            if not campaign:
                return None

            # Get creative IDs for this campaign
            creative_ids = repo.get_campaign_creatives(campaign_id)

            return {
                "id": campaign.id,
                "seat_id": campaign.seat_id,
                "name": campaign.name,
                "description": campaign.description,
                "ai_generated": campaign.ai_generated,
                "ai_confidence": campaign.ai_confidence,
                "clustering_method": campaign.clustering_method,
                "status": campaign.status,
                "creative_count": campaign.creative_count,
                "creative_ids": creative_ids,
            }

        campaign_data = await db_transaction_async(_get_campaign)

        if not campaign_data:
            raise HTTPException(status_code=404, detail="Campaign not found")

        return AICampaignResponse(**campaign_data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{campaign_id}")
async def update_campaign(campaign_id: str, request: CampaignUpdateRequest):
    """
    Update campaign name or description.
    """
    try:
        def _update_campaign(conn):
            repo = CampaignRepository(conn)
            return repo.update_campaign(
                campaign_id=campaign_id,
                name=request.name,
                description=request.description,
                status=request.status,
            )

        success = await db_transaction_async(_update_campaign)

        if not success:
            raise HTTPException(status_code=404, detail="Campaign not found")

        return {"status": "updated"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{campaign_id}")
async def delete_campaign(campaign_id: str):
    """
    Delete a campaign and unassign all its creatives.
    """
    try:
        def _delete_campaign(conn):
            repo = CampaignRepository(conn)
            return repo.delete_campaign(campaign_id)

        success = await db_transaction_async(_delete_campaign)

        if not success:
            raise HTTPException(status_code=404, detail="Campaign not found")

        return {"status": "deleted"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Creative Assignment Endpoints
# ============================================

@router.get("/{campaign_id}/creatives")
async def get_campaign_creatives(campaign_id: str):
    """
    Get all creative IDs in a campaign.
    """
    try:
        def _get_creatives(conn):
            repo = CampaignRepository(conn)
            return repo.get_campaign_creatives(campaign_id)

        creative_ids = await db_transaction_async(_get_creatives)
        return {"creative_ids": creative_ids, "count": len(creative_ids)}

    except Exception as e:
        logger.error(f"Failed to get campaign creatives: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{campaign_id}/creatives")
async def add_creatives_to_campaign(campaign_id: str, request: AssignCreativesRequest):
    """
    Manually assign creatives to a campaign.
    """
    try:
        def _assign_creatives(conn):
            repo = CampaignRepository(conn)
            return repo.assign_creatives_batch(
                creative_ids=request.creative_ids,
                campaign_id=campaign_id,
                assigned_by="user",
                manually_assigned=True,
            )

        count = await db_transaction_async(_assign_creatives)
        return {"status": "assigned", "count": count}

    except Exception as e:
        logger.error(f"Failed to assign creatives: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{campaign_id}/creatives/{creative_id}")
async def remove_creative_from_campaign(campaign_id: str, creative_id: str):
    """
    Remove a creative from a campaign.
    """
    try:
        def _remove_creative(conn):
            repo = CampaignRepository(conn)
            return repo.remove_creative_from_campaign(creative_id)

        success = await db_transaction_async(_remove_creative)

        if not success:
            raise HTTPException(status_code=404, detail="Creative not in campaign")

        return {"status": "removed"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove creative: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/creatives/{creative_id}/move")
async def move_creative(creative_id: str, request: MoveCreativeRequest):
    """
    Move a creative from one campaign to another.
    """
    try:
        def _move_creative(conn):
            repo = CampaignRepository(conn)
            return repo.assign_creative_to_campaign(
                creative_id=creative_id,
                campaign_id=request.to_campaign_id,
                assigned_by="user",
                manually_assigned=True,
            )

        await db_transaction_async(_move_creative)
        return {"status": "moved"}

    except Exception as e:
        logger.error(f"Failed to move creative: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Performance Endpoints
# ============================================

@router.get("/{campaign_id}/performance", response_model=CampaignPerformanceResponse)
async def get_campaign_performance(
    campaign_id: str,
    period: str = Query("7d"),
):
    """
    Get performance metrics for a campaign.
    """
    try:
        days = {"1d": 1, "7d": 7, "30d": 30, "all": 365}.get(period, 7)

        def _get_perf(conn):
            repo = CampaignRepository(conn)
            return repo.get_campaign_performance(campaign_id, days=days)

        perf = await db_transaction_async(_get_perf)
        return CampaignPerformanceResponse(**perf)

    except Exception as e:
        logger.error(f"Failed to get campaign performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{campaign_id}/performance/daily")
async def get_campaign_daily_trend(
    campaign_id: str,
    days: int = Query(30),
):
    """
    Get daily performance trend for a campaign.
    """
    try:
        def _get_trend(conn):
            repo = CampaignRepository(conn)
            return repo.get_campaign_daily_trend(campaign_id, days=days)

        trend = await db_transaction_async(_get_trend)
        return {"trend": trend}

    except Exception as e:
        logger.error(f"Failed to get campaign trend: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh-summaries")
async def refresh_campaign_summaries(seat_id: Optional[int] = None):
    """
    Recalculate campaign_daily_summary from performance_metrics.
    Run this after importing new data.
    """
    try:
        def _refresh_summaries(conn):
            repo = CampaignRepository(conn)
            campaigns = repo.list_campaigns(seat_id=seat_id)

            # Get date range from performance data
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT metric_date FROM performance_metrics
                ORDER BY metric_date DESC LIMIT 30
            """)
            dates = [row['metric_date'] for row in cursor.fetchall()]

            updated = 0
            for campaign in campaigns:
                for date in dates:
                    repo.update_campaign_summary(campaign.id, date)
                    updated += 1

            return {"campaigns": len(campaigns), "dates": len(dates)}

        result = await db_transaction_async(_refresh_summaries)
        return {"status": "refreshed", "campaigns_updated": result["campaigns"], "dates_processed": result["dates"]}

    except Exception as e:
        logger.error(f"Failed to refresh summaries: {e}")
        raise HTTPException(status_code=500, detail=str(e))
