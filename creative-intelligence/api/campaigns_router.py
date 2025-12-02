"""FastAPI router for AI Campaign Clustering endpoints.

This module provides REST API endpoints for:
- Auto-clustering creatives into campaigns
- Managing AI-generated campaigns
- Campaign performance aggregation
"""

import logging
import sqlite3
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from storage.campaign_repository import CampaignRepository, AICampaign
from api.clustering.rule_based import pre_cluster_creatives, merge_small_clusters
from api.clustering.ai_clusterer import AICampaignClusterer, apply_ai_suggestions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai-campaigns", tags=["AI Campaigns"])


# ============================================
# Request/Response Models
# ============================================

class AICampaignResponse(BaseModel):
    """Response model for AI campaign."""
    id: int
    seat_id: Optional[int] = None
    name: str
    description: Optional[str] = None
    ai_generated: bool = True
    ai_confidence: Optional[float] = None
    clustering_method: Optional[str] = None
    status: str = "active"
    creative_count: int = 0
    performance: Optional[dict] = None


class AutoClusterRequest(BaseModel):
    """Request for auto-clustering."""
    seat_id: Optional[int] = None
    use_ai: bool = True
    min_cluster_size: int = 3


class AutoClusterResponse(BaseModel):
    """Response from auto-clustering."""
    campaigns_created: int
    creatives_categorized: int
    campaigns: list[dict]


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
    to_campaign_id: int


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

def get_db_connection() -> sqlite3.Connection:
    """Get a database connection."""
    db_path = Path.home() / ".catscan" / "catscan.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def get_campaign_repo() -> CampaignRepository:
    """Get campaign repository instance."""
    conn = get_db_connection()
    return CampaignRepository(conn)


# ============================================
# Clustering Endpoints
# ============================================

@router.post("/auto-cluster", response_model=AutoClusterResponse)
async def auto_cluster_creatives(request: AutoClusterRequest):
    """
    Automatically cluster all uncategorized creatives into campaigns.

    This endpoint:
    1. Finds all creatives not assigned to a campaign
    2. Groups them using rule-based clustering (domain, URL patterns)
    3. Optionally refines with AI (generates better names, merges similar)
    4. Creates campaigns and assigns creatives
    """
    conn = get_db_connection()
    repo = CampaignRepository(conn)

    try:
        # Get uncategorized creatives
        creatives = repo.get_uncategorized_creatives(request.seat_id)

        if not creatives:
            return AutoClusterResponse(
                campaigns_created=0,
                creatives_categorized=0,
                campaigns=[],
            )

        logger.info(f"Found {len(creatives)} uncategorized creatives")

        # Step 1: Rule-based pre-clustering
        clusters = pre_cluster_creatives(creatives)
        clusters = merge_small_clusters(clusters, request.min_cluster_size)

        logger.info(f"Pre-clustering created {len(clusters)} clusters")

        # Step 2: AI refinement (if enabled)
        if request.use_ai:
            try:
                clusterer = AICampaignClusterer()
                ai_result = clusterer.analyze_and_name_clusters(clusters)
                campaign_defs = apply_ai_suggestions(clusters, ai_result)
            except Exception as e:
                logger.warning(f"AI clustering failed, falling back to rules: {e}")
                # Fallback to rule-based naming
                from api.clustering.rule_based import generate_cluster_name
                campaign_defs = []
                for cluster_key, creatives_in_cluster in clusters.items():
                    campaign_defs.append({
                        "name": generate_cluster_name(cluster_key, creatives_in_cluster),
                        "description": None,
                        "creative_ids": [c["id"] for c in creatives_in_cluster],
                        "ai_confidence": 0.3,
                        "clustering_method": cluster_key.split(":")[0],
                    })
        else:
            # Rule-based only
            from api.clustering.rule_based import generate_cluster_name
            campaign_defs = []
            for cluster_key, creatives_in_cluster in clusters.items():
                campaign_defs.append({
                    "name": generate_cluster_name(cluster_key, creatives_in_cluster),
                    "description": None,
                    "creative_ids": [c["id"] for c in creatives_in_cluster],
                    "ai_confidence": 0.5,
                    "clustering_method": cluster_key.split(":")[0],
                })

        # Step 3: Create campaigns and assign creatives
        created = []
        for campaign_def in campaign_defs:
            campaign_id = repo.create_campaign(
                name=campaign_def["name"],
                seat_id=request.seat_id,
                description=campaign_def.get("description"),
                ai_generated=True,
                ai_confidence=campaign_def.get("ai_confidence"),
                clustering_method=campaign_def.get("clustering_method"),
            )

            # Assign creatives
            creative_ids = campaign_def.get("creative_ids", [])
            repo.assign_creatives_batch(
                creative_ids=creative_ids,
                campaign_id=campaign_id,
                assigned_by="ai" if request.use_ai else "rule",
            )

            created.append({
                "id": campaign_id,
                "name": campaign_def["name"],
                "count": len(creative_ids),
            })

        conn.commit()
        conn.close()

        total_categorized = sum(c["count"] for c in created)

        return AutoClusterResponse(
            campaigns_created=len(created),
            creatives_categorized=total_categorized,
            campaigns=created,
        )

    except Exception as e:
        conn.close()
        logger.error(f"Auto-clustering failed: {e}")
        raise HTTPException(status_code=500, detail=f"Clustering failed: {str(e)}")


# ============================================
# Campaign CRUD Endpoints
# ============================================

@router.get("", response_model=list[AICampaignResponse])
async def list_campaigns(
    seat_id: Optional[int] = Query(None),
    status: Optional[str] = Query(None),
    include_performance: bool = Query(True),
    period: str = Query("7d"),
):
    """
    List all AI campaigns with optional performance data.
    """
    conn = get_db_connection()
    repo = CampaignRepository(conn)

    try:
        campaigns = repo.list_campaigns(seat_id=seat_id, status=status)

        result = []
        for campaign in campaigns:
            campaign_data = AICampaignResponse(
                id=campaign.id,
                seat_id=campaign.seat_id,
                name=campaign.name,
                description=campaign.description,
                ai_generated=campaign.ai_generated,
                ai_confidence=campaign.ai_confidence,
                clustering_method=campaign.clustering_method,
                status=campaign.status,
                creative_count=campaign.creative_count,
            )

            if include_performance:
                days = {"1d": 1, "7d": 7, "30d": 30, "all": 365}.get(period, 7)
                perf = repo.get_campaign_performance(campaign.id, days=days)
                campaign_data.performance = perf

            result.append(campaign_data)

        conn.close()
        return result

    except Exception as e:
        conn.close()
        logger.error(f"Failed to list campaigns: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{campaign_id}", response_model=AICampaignResponse)
async def get_campaign(
    campaign_id: int,
    include_creatives: bool = Query(False),
):
    """
    Get campaign details.
    """
    conn = get_db_connection()
    repo = CampaignRepository(conn)

    try:
        campaign = repo.get_campaign(campaign_id)

        if not campaign:
            conn.close()
            raise HTTPException(status_code=404, detail="Campaign not found")

        result = AICampaignResponse(
            id=campaign.id,
            seat_id=campaign.seat_id,
            name=campaign.name,
            description=campaign.description,
            ai_generated=campaign.ai_generated,
            ai_confidence=campaign.ai_confidence,
            clustering_method=campaign.clustering_method,
            status=campaign.status,
            creative_count=campaign.creative_count,
        )

        conn.close()
        return result

    except HTTPException:
        raise
    except Exception as e:
        conn.close()
        logger.error(f"Failed to get campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/{campaign_id}")
async def update_campaign(campaign_id: int, request: CampaignUpdateRequest):
    """
    Update campaign name or description.
    """
    conn = get_db_connection()
    repo = CampaignRepository(conn)

    try:
        success = repo.update_campaign(
            campaign_id=campaign_id,
            name=request.name,
            description=request.description,
            status=request.status,
        )

        conn.commit()
        conn.close()

        if not success:
            raise HTTPException(status_code=404, detail="Campaign not found")

        return {"status": "updated"}

    except HTTPException:
        raise
    except Exception as e:
        conn.close()
        logger.error(f"Failed to update campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{campaign_id}")
async def delete_campaign(campaign_id: int):
    """
    Delete a campaign and unassign all its creatives.
    """
    conn = get_db_connection()
    repo = CampaignRepository(conn)

    try:
        success = repo.delete_campaign(campaign_id)
        conn.commit()
        conn.close()

        if not success:
            raise HTTPException(status_code=404, detail="Campaign not found")

        return {"status": "deleted"}

    except HTTPException:
        raise
    except Exception as e:
        conn.close()
        logger.error(f"Failed to delete campaign: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Creative Assignment Endpoints
# ============================================

@router.get("/{campaign_id}/creatives")
async def get_campaign_creatives(campaign_id: int):
    """
    Get all creative IDs in a campaign.
    """
    conn = get_db_connection()
    repo = CampaignRepository(conn)

    try:
        creative_ids = repo.get_campaign_creatives(campaign_id)
        conn.close()
        return {"creative_ids": creative_ids, "count": len(creative_ids)}

    except Exception as e:
        conn.close()
        logger.error(f"Failed to get campaign creatives: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{campaign_id}/creatives")
async def add_creatives_to_campaign(campaign_id: int, request: AssignCreativesRequest):
    """
    Manually assign creatives to a campaign.
    """
    conn = get_db_connection()
    repo = CampaignRepository(conn)

    try:
        count = repo.assign_creatives_batch(
            creative_ids=request.creative_ids,
            campaign_id=campaign_id,
            assigned_by="user",
            manually_assigned=True,
        )

        conn.commit()
        conn.close()

        return {"status": "assigned", "count": count}

    except Exception as e:
        conn.close()
        logger.error(f"Failed to assign creatives: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{campaign_id}/creatives/{creative_id}")
async def remove_creative_from_campaign(campaign_id: int, creative_id: str):
    """
    Remove a creative from a campaign.
    """
    conn = get_db_connection()
    repo = CampaignRepository(conn)

    try:
        success = repo.remove_creative_from_campaign(creative_id)
        conn.commit()
        conn.close()

        if not success:
            raise HTTPException(status_code=404, detail="Creative not in campaign")

        return {"status": "removed"}

    except HTTPException:
        raise
    except Exception as e:
        conn.close()
        logger.error(f"Failed to remove creative: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/creatives/{creative_id}/move")
async def move_creative(creative_id: str, request: MoveCreativeRequest):
    """
    Move a creative from one campaign to another.
    """
    conn = get_db_connection()
    repo = CampaignRepository(conn)

    try:
        success = repo.assign_creative_to_campaign(
            creative_id=creative_id,
            campaign_id=request.to_campaign_id,
            assigned_by="user",
            manually_assigned=True,
        )

        conn.commit()
        conn.close()

        return {"status": "moved"}

    except Exception as e:
        conn.close()
        logger.error(f"Failed to move creative: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# Performance Endpoints
# ============================================

@router.get("/{campaign_id}/performance", response_model=CampaignPerformanceResponse)
async def get_campaign_performance(
    campaign_id: int,
    period: str = Query("7d"),
):
    """
    Get performance metrics for a campaign.
    """
    conn = get_db_connection()
    repo = CampaignRepository(conn)

    try:
        days = {"1d": 1, "7d": 7, "30d": 30, "all": 365}.get(period, 7)
        perf = repo.get_campaign_performance(campaign_id, days=days)
        conn.close()

        return CampaignPerformanceResponse(**perf)

    except Exception as e:
        conn.close()
        logger.error(f"Failed to get campaign performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{campaign_id}/performance/daily")
async def get_campaign_daily_trend(
    campaign_id: int,
    days: int = Query(30),
):
    """
    Get daily performance trend for a campaign.
    """
    conn = get_db_connection()
    repo = CampaignRepository(conn)

    try:
        trend = repo.get_campaign_daily_trend(campaign_id, days=days)
        conn.close()
        return {"trend": trend}

    except Exception as e:
        conn.close()
        logger.error(f"Failed to get campaign trend: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/refresh-summaries")
async def refresh_campaign_summaries(seat_id: Optional[int] = None):
    """
    Recalculate campaign_daily_summary from performance_metrics.
    Run this after importing new data.
    """
    conn = get_db_connection()
    repo = CampaignRepository(conn)

    try:
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

        conn.commit()
        conn.close()

        return {"status": "refreshed", "campaigns_updated": len(campaigns), "dates_processed": len(dates)}

    except Exception as e:
        conn.close()
        logger.error(f"Failed to refresh summaries: {e}")
        raise HTTPException(status_code=500, detail=str(e))
