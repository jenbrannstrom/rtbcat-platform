"""QPS Optimization Router.

Handles QPS analytics, size coverage, geo waste, pretargeting recommendations,
publisher waste, bid filtering, platform efficiency, and hourly patterns.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends

from analytics.size_coverage_analyzer import SizeCoverageAnalyzer
from analytics.geo_waste_analyzer import GeoWasteAnalyzer
from analytics.pretargeting_recommender import PretargetingRecommender
from analytics.qps_optimizer import QPSOptimizer
from api.dependencies import get_store, get_current_user, resolve_buyer_id, get_allowed_buyer_ids
from storage import SQLiteStore
from storage.repositories.user_repository import User
from .common import get_valid_billing_ids_for_buyer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["QPS Analytics"])


@router.get("/analytics/size-coverage", tags=["QPS Analytics"])
async def get_size_coverage(
    days: int = Query(7, ge=1, le=90),
    billing_id: Optional[str] = Query(None, description="Filter by billing account ID (pretargeting config)"),
    buyer_id: Optional[str] = Query(None, description="Filter by buyer/seat ID"),
    store: SQLiteStore = Depends(get_store),
    user: User = Depends(get_current_user),
):
    """
    Analyze size coverage gaps.

    Returns sizes receiving traffic but missing creatives.
    This is the core Cat-Scan analysis for identifying QPS waste.

    Optional: Filter by billing_id to analyze a specific pretargeting config.
    """
    try:
        # SizeCoverageAnalyzer uses its own db connection pattern
        from storage.database import DB_PATH
        resolved_buyer_id = None
        billing_ids = None
        if buyer_id:
            resolved_buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
            billing_ids = await get_valid_billing_ids_for_buyer(resolved_buyer_id)
        else:
            allowed = await get_allowed_buyer_ids(store=store, user=user)
            if allowed:
                billing_ids = []
                for allowed_buyer in allowed:
                    billing_ids.extend(await get_valid_billing_ids_for_buyer(allowed_buyer))
        analyzer = SizeCoverageAnalyzer(str(DB_PATH))
        summary = analyzer.analyze(
            days,
            billing_id=billing_id,
            billing_ids=billing_ids if billing_ids else None,
            buyer_id=resolved_buyer_id,
        )
        return {
            "period_days": days,
            "billing_id": billing_id,
            "buyer_id": resolved_buyer_id,
            "total_sizes_in_traffic": summary.total_sizes_in_traffic,
            "sizes_with_creatives": summary.sizes_with_creatives,
            "sizes_without_creatives": summary.sizes_without_creatives,
            "coverage_rate_pct": round(summary.coverage_rate, 1),
            "wasted_queries_daily": summary.wasted_queries_daily,
            "wasted_qps": round(summary.wasted_qps, 2),
            "gaps": [
                {
                    "size": g.size,
                    "format": g.format,
                    "queries_received": g.queries_received,
                    "daily_estimate": g.estimated_daily_queries,
                    "percent_of_traffic": round(g.percent_of_total_traffic, 1),
                    "recommendation": g.recommendation,
                }
                for g in summary.gaps[:20]
            ],
            "covered_sizes": [
                {
                    "size": s["size"],
                    "format": s["format"],
                    "reached_queries": s["reached_queries"],
                    "impressions": s["impressions"],
                    "spend_usd": round(s["spend_usd"], 2),
                    "creative_count": s["creative_count"],
                    "ctr_pct": round(s["ctr"], 2),
                }
                for s in summary.covered_sizes[:20]
            ],
        }
    except Exception as e:
        logger.error(f"Failed to analyze size coverage: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/geo-waste", tags=["QPS Analytics"])
async def get_geo_waste(
    days: int = Query(7, ge=1, le=90),
    buyer_id: Optional[str] = Query(None, description="Filter by buyer/seat ID"),
    store: SQLiteStore = Depends(get_store),
    user: User = Depends(get_current_user),
):
    """
    Analyze geographic QPS waste.

    Returns geos with poor performance that should be excluded from pretargeting.
    """
    try:
        from storage.database import DB_PATH
        resolved_buyer_id = None
        billing_ids = None
        if buyer_id:
            resolved_buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
            billing_ids = await get_valid_billing_ids_for_buyer(resolved_buyer_id)
        else:
            allowed = await get_allowed_buyer_ids(store=store, user=user)
            if allowed:
                billing_ids = []
                for allowed_buyer in allowed:
                    billing_ids.extend(await get_valid_billing_ids_for_buyer(allowed_buyer))
        analyzer = GeoWasteAnalyzer(str(DB_PATH))
        summary = analyzer.analyze(days, billing_ids=billing_ids if billing_ids else None)
        return {
            "period_days": days,
            "buyer_id": resolved_buyer_id,
            "total_geos": summary.total_geos,
            "geos_with_traffic": summary.geos_with_traffic,
            "geos_to_exclude": summary.geos_to_exclude,
            "geos_to_monitor": summary.geos_to_monitor,
            "geos_performing_well": summary.geos_performing_well,
            "estimated_waste_pct": round(summary.estimated_waste_pct, 1),
            "total_spend_usd": round(summary.total_spend_usd, 2),
            "wasted_spend_usd": round(summary.wasted_spend_usd, 2),
            "geos": [
                {
                    "country": g.country_name,
                    "code": g.country_code,
                    "impressions": g.impressions,
                    "clicks": g.clicks,
                    "spend_usd": round(g.spend_usd, 2),
                    "ctr_pct": round(g.ctr, 2),
                    "cpm": round(g.cpm, 2),
                    "creative_count": g.creative_count,
                    "recommendation": g.recommendation,
                }
                for g in summary.geo_breakdown
            ],
        }
    except Exception as e:
        logger.error(f"Failed to analyze geo waste: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/pretargeting-recommendations", tags=["QPS Analytics"])
async def get_pretargeting_recommendations(
    days: int = Query(7, ge=1, le=90),
    max_configs: int = Query(10, ge=1, le=10),
):
    """
    Generate optimal pretargeting configurations.

    Given the 10-config limit, recommends how to configure them for
    maximum QPS efficiency.
    """
    try:
        from storage.database import DB_PATH
        recommender = PretargetingRecommender(str(DB_PATH))
        recommendation = recommender.generate_recommendations(days, max_configs)
        return {
            "config_limit": recommendation.config_limit,
            "summary": recommendation.summary,
            "total_waste_reduction_pct": round(recommendation.total_estimated_waste_reduction_pct, 1),
            "configs": [
                recommender.get_config_as_json(config)
                for config in recommendation.configs
            ],
        }
    except Exception as e:
        logger.error(f"Failed to generate pretargeting recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/qps-summary", tags=["QPS Analytics"])
async def get_qps_summary(
    days: int = Query(7, ge=1, le=90),
    buyer_id: Optional[str] = Query(None, description="Filter by buyer/seat ID"),
    store: SQLiteStore = Depends(get_store),
    user: User = Depends(get_current_user),
):
    """
    High-level QPS efficiency summary.

    Combines size coverage and geo waste analysis into a single dashboard view.
    """
    try:
        from storage.database import DB_PATH
        resolved_buyer_id = None
        billing_ids = None
        if buyer_id:
            resolved_buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
            billing_ids = await get_valid_billing_ids_for_buyer(resolved_buyer_id)
        else:
            allowed = await get_allowed_buyer_ids(store=store, user=user)
            if allowed:
                billing_ids = []
                for allowed_buyer in allowed:
                    billing_ids.extend(await get_valid_billing_ids_for_buyer(allowed_buyer))
        size_analyzer = SizeCoverageAnalyzer(str(DB_PATH))
        geo_analyzer = GeoWasteAnalyzer(str(DB_PATH))

        size_summary = size_analyzer.analyze(
            days,
            billing_ids=billing_ids if billing_ids else None,
            buyer_id=resolved_buyer_id,
        )
        geo_summary = geo_analyzer.analyze(days, billing_ids=billing_ids if billing_ids else None)

        # Calculate total estimated waste
        # Size gaps are 100% waste, geo waste is partial
        size_waste_pct = 100 - size_summary.coverage_rate if size_summary.coverage_rate > 0 else 0

        return {
            "period_days": days,
            "buyer_id": resolved_buyer_id,
            "size_coverage": {
                "coverage_rate_pct": round(size_summary.coverage_rate, 1),
                "sizes_covered": size_summary.sizes_with_creatives,
                "sizes_missing": size_summary.sizes_without_creatives,
                "wasted_qps": round(size_summary.wasted_qps, 2),
            },
            "geo_efficiency": {
                "geos_analyzed": geo_summary.total_geos,
                "geos_to_exclude": geo_summary.geos_to_exclude,
                "geos_to_monitor": geo_summary.geos_to_monitor,
                "waste_pct": round(geo_summary.estimated_waste_pct, 1),
                "wasted_spend_usd": round(geo_summary.wasted_spend_usd, 2),
            },
            "action_items": {
                "sizes_to_block": len([g for g in size_summary.gaps if g.recommendation == "BLOCK_IN_PRETARGETING"]),
                "sizes_to_consider": len([g for g in size_summary.gaps if g.recommendation == "CONSIDER_ADDING_CREATIVE"]),
                "geos_to_exclude": geo_summary.geos_to_exclude,
            },
            "estimated_savings": {
                "geo_waste_monthly_usd": round(geo_summary.wasted_spend_usd * 30 / max(days, 1), 2),
            },
        }
    except Exception as e:
        logger.error(f"Failed to get QPS summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/geo-pretargeting-config", tags=["QPS Analytics"])
async def get_geo_pretargeting_config(days: int = Query(7, ge=1, le=90)):
    """
    Get ready-to-use geo configuration for pretargeting.

    Returns include and exclude lists for geo targeting.
    """
    try:
        from storage.database import DB_PATH
        analyzer = GeoWasteAnalyzer(str(DB_PATH))
        config = analyzer.get_pretargeting_geo_config(days)
        return {
            "period_days": days,
            "include_geos": config["include"],
            "exclude_geos": config["exclude"],
            "estimated_monthly_savings_usd": round(config["estimated_savings_usd"] * 30 / max(days, 1), 2),
        }
    except Exception as e:
        logger.error(f"Failed to get geo pretargeting config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/qps-optimization", tags=["QPS Optimization"])
async def get_qps_optimization_report(
    days: int = Query(7, ge=1, le=30),
    bidder_id: Optional[str] = Query(None, description="Filter by bidder account ID"),
):
    """
    Get comprehensive QPS optimization report with actionable recommendations.

    This endpoint JOINs data from:
    - rtb_bidstream (bid pipeline metrics)
    - rtb_daily (creative/app performance)
    - rtb_bid_filtering (bid filtering reasons)
    - rtb_quality (fraud/viewability signals)

    Returns:
    - Summary statistics (efficiency, waste estimate)
    - Actionable recommendations
    - Publisher waste ranking
    - Platform efficiency breakdown
    - Hourly patterns
    - Bid filtering analysis
    - Fraud risk publishers
    - Viewability issues

    This is the main endpoint for AI-driven QPS optimization.
    """
    try:
        optimizer = QPSOptimizer()
        report = await optimizer.get_full_optimization_report(days, bidder_id)
        return report
    except Exception as e:
        logger.error(f"Failed to generate QPS optimization report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/publisher-waste", tags=["QPS Optimization"])
async def get_publisher_waste(
    days: int = Query(7, ge=1, le=30),
    limit: int = Query(50, ge=1, le=100),
    bidder_id: Optional[str] = Query(None, description="Filter by bidder account ID"),
):
    """
    Get publishers ranked by QPS waste.

    JOINs rtb_bidstream + rtb_daily to calculate:
    - Bid requests vs auctions won
    - Waste percentage
    - Win rate
    - Spend

    Use this to identify publishers to block in pretargeting.
    """
    try:
        optimizer = QPSOptimizer()
        result = await optimizer.get_publisher_waste_ranking(days, limit, bidder_id)
        return {
            "period_days": days,
            "publishers": result,
            "count": len(result),
        }
    except Exception as e:
        logger.error(f"Failed to get publisher waste ranking: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/bid-filtering", tags=["QPS Optimization"])
async def get_bid_filtering_analysis(
    days: int = Query(7, ge=1, le=30),
    bidder_id: Optional[str] = Query(None, description="Filter by bidder account ID"),
):
    """
    Analyze why bids are being filtered.

    Returns bid filtering reasons ranked by:
    - Volume (bids filtered)
    - Opportunity cost

    Use this to identify and fix creative policy issues.
    """
    try:
        optimizer = QPSOptimizer()
        result = await optimizer.get_bid_filtering_analysis(days, bidder_id)
        return {
            "period_days": days,
            "filtering_reasons": result,
            "count": len(result),
        }
    except Exception as e:
        logger.error(f"Failed to get bid filtering analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/platform-efficiency", tags=["QPS Optimization"])
async def get_platform_efficiency(
    days: int = Query(7, ge=1, le=30),
    bidder_id: Optional[str] = Query(None, description="Filter by bidder account ID"),
):
    """
    Analyze efficiency by platform (Desktop/Mobile/Tablet).

    Returns win rates and spend by device type for bid adjustments.
    """
    try:
        optimizer = QPSOptimizer()
        result = await optimizer.get_platform_efficiency(days, bidder_id)
        result["period_days"] = days
        return result
    except Exception as e:
        logger.error(f"Failed to get platform efficiency: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/hourly-patterns", tags=["QPS Optimization"])
async def get_hourly_patterns(
    days: int = Query(7, ge=1, le=30),
    bidder_id: Optional[str] = Query(None, description="Filter by bidder account ID"),
):
    """
    Analyze hourly bidding patterns for QPS throttling.

    Returns bid requests, win rate, and efficiency by hour of day.
    """
    try:
        optimizer = QPSOptimizer()
        result = await optimizer.get_hourly_patterns(days, bidder_id)
        return {
            "period_days": days,
            "hourly_patterns": result,
        }
    except Exception as e:
        logger.error(f"Failed to get hourly patterns: {e}")
        raise HTTPException(status_code=500, detail=str(e))
