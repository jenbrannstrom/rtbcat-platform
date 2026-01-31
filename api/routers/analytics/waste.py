"""Waste Signal Analysis Router.

Handles waste analysis, waste signals, problem format detection,
viewability waste, and fraud risk endpoints.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends

from analytics.waste_analyzer import TrafficWasteAnalyzer
from analytics.qps_optimizer import QPSOptimizer
from services.waste_analyzer import CreativeHealthService
from api.dependencies import (
    get_store,
    get_current_user,
    resolve_buyer_id,
    require_buyer_access,
    resolve_bidder_id,
)
from services.auth_service import User
from .common import (
    SizeGapResponse,
    SizeCoverageResponse,
    WasteReportResponse,
    WasteSignalResponse,
    ProblemFormatResponse,
    _group_signals_by_type,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Waste Analysis"])


@router.get("/analytics/waste", response_model=WasteReportResponse)
async def get_waste_report(
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    days: int = Query(7, ge=1, le=90, description="Days of traffic to analyze"),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Get waste analysis report comparing bid requests vs creative inventory.

    Analyzes RTB traffic data to identify size gaps - ad sizes that receive
    bid requests but have no matching creatives in inventory. This helps
    identify bandwidth waste and optimization opportunities.

    Returns recommendations for each gap:
    - **Block**: High volume non-standard sizes to block in pretargeting
    - **Add Creative**: Consider adding creative for this size
    - **Use Flexible**: Near-IAB sizes that can use flexible HTML5 creatives
    - **Monitor**: Low volume sizes to watch for growth
    """
    try:
        # TrafficWasteAnalyzer uses its own db connection internally
        buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
        analyzer = TrafficWasteAnalyzer(store)
        report = await analyzer.analyze_waste(buyer_id=buyer_id, days=days)

        return WasteReportResponse(
            buyer_id=report.buyer_id,
            total_requests=report.total_requests,
            total_waste_requests=report.total_waste_requests,
            waste_percentage=round(report.waste_percentage, 2),
            size_gaps=[
                SizeGapResponse(
                    canonical_size=g.canonical_size,
                    request_count=g.request_count,
                    creative_count=g.creative_count,
                    estimated_qps=round(g.estimated_qps, 2),
                    estimated_waste_pct=round(g.estimated_waste_pct, 2),
                    recommendation=g.recommendation,
                    recommendation_detail=g.recommendation_detail,
                    potential_savings_usd=g.potential_savings_usd,
                    closest_iab_size=g.closest_iab_size,
                )
                for g in report.size_gaps
            ],
            size_coverage=[
                SizeCoverageResponse(
                    canonical_size=c.canonical_size,
                    creative_count=c.creative_count,
                    request_count=c.request_count,
                    coverage_status=c.coverage_status,
                    formats=c.formats,
                )
                for c in report.size_coverage
            ],
            potential_savings_qps=round(report.potential_savings_qps, 2),
            potential_savings_usd=report.potential_savings_usd,
            analysis_period_days=report.analysis_period_days,
            generated_at=report.generated_at,
            recommendations_summary=report.recommendations_summary,
        )

    except Exception as e:
        logger.error(f"Waste analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Waste analysis failed: {str(e)}")


@router.get("/analytics/waste-signals/{creative_id}", response_model=list[WasteSignalResponse])
async def get_waste_signals(
    creative_id: str,
    include_resolved: bool = Query(False, description="Include resolved signals"),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Get evidence-based waste signals for a creative.

    Phase 11.2: Evidence-Based Waste Detection
    Returns signals with full evidence chain explaining WHY the creative is flagged.
    """
    creative = await store.get_creative(creative_id)
    if not creative:
        raise HTTPException(status_code=404, detail="Creative not found")
    if creative.buyer_id:
        await require_buyer_access(creative.buyer_id, store=store, user=user)

    service = CreativeHealthService()
    signals = service.get_signals_for_creative(creative_id, include_resolved=include_resolved)
    return [WasteSignalResponse(**s) for s in signals]


@router.get("/analytics/problem-formats", response_model=list[ProblemFormatResponse])
async def detect_problem_formats(
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    days: int = Query(7, ge=1, le=90, description="Timeframe for analysis"),
    size_tolerance: int = Query(5, ge=0, le=20, description="Pixel tolerance for size matching"),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """Detect creatives with problems that hurt QPS efficiency.

    Phase 22: Problem format detection identifies creatives that should be
    reviewed or removed.

    Problem types:
    - zero_bids: Has reached_queries but no impressions
    - non_standard: Size doesn't match any IAB standard (even with tolerance)
    - low_bid_rate: impressions / reached_queries < 1%
    - disapproved: approval_status != 'APPROVED'
    """
    buyer_id = await resolve_buyer_id(buyer_id, store=store, user=user)
    analyzer = TrafficWasteAnalyzer(store)
    problems = await analyzer.detect_problem_formats(
        buyer_id=buyer_id,
        days=days,
        size_tolerance=size_tolerance,
    )

    return [
        ProblemFormatResponse(
            creative_id=p.creative_id,
            problem_type=p.problem_type,
            evidence=p.evidence,
            severity=p.severity,
            recommendation=p.recommendation,
        )
        for p in problems
    ]


@router.post("/analytics/waste-signals/analyze")
async def run_waste_analysis(
    days: int = Query(7, ge=1, le=90, description="Timeframe for analysis"),
    save_to_db: bool = Query(True, description="Save signals to database"),
):
    """Run waste analysis on all creatives with recent activity.

    Phase 11.2: Evidence-Based Waste Detection
    Analyzes all creatives and generates signals with evidence.
    """
    service = CreativeHealthService()
    signals = service.analyze_all_creatives(days=days, save_to_db=save_to_db)

    return {
        "status": "complete",
        "signals_generated": len(signals),
        "by_type": _group_signals_by_type(signals),
    }


@router.post("/analytics/waste-signals/{signal_id}/resolve")
async def resolve_waste_signal(
    signal_id: int,
    notes: Optional[str] = Query(None, description="Resolution notes"),
):
    """Mark a waste signal as resolved.

    Phase 11.2: Evidence-Based Waste Detection
    """
    service = CreativeHealthService()
    success = service.resolve_signal(signal_id, resolved_by="user", notes=notes)

    if not success:
        raise HTTPException(status_code=404, detail="Signal not found")

    return {"status": "resolved", "signal_id": signal_id}


@router.get("/analytics/viewability-waste", tags=["QPS Optimization"])
async def get_viewability_waste(
    days: int = Query(7, ge=1, le=30),
    threshold_pct: float = Query(50.0, ge=0, le=100, description="Viewability threshold"),
    bidder_id: Optional[str] = Query(None, description="Filter by bidder account ID"),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """
    Find publishers with low viewability but high spend.

    Returns publishers with viewability below threshold.
    Use this to identify where to reduce bids.
    """
    try:
        bidder_id = await resolve_bidder_id(bidder_id, store=store, user=user)
        optimizer = QPSOptimizer()
        result = await optimizer.get_viewability_waste(days, threshold_pct, bidder_id)
        return {
            "period_days": days,
            "viewability_threshold_pct": threshold_pct,
            "viewability_issues": result,
            "count": len(result),
        }
    except Exception as e:
        logger.error(f"Failed to get viewability waste: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/fraud-risk", tags=["QPS Optimization"])
async def get_fraud_risk_publishers(
    days: int = Query(7, ge=1, le=30),
    threshold_pct: float = Query(5.0, ge=0, le=100, description="IVT rate threshold"),
    bidder_id: Optional[str] = Query(None, description="Filter by bidder account ID"),
    store=Depends(get_store),
    user: User = Depends(get_current_user),
):
    """
    Find publishers with high fraud/IVT rates.

    Returns publishers with IVT rate above threshold.
    Use this to identify publishers to block.
    """
    try:
        bidder_id = await resolve_bidder_id(bidder_id, store=store, user=user)
        optimizer = QPSOptimizer()
        result = await optimizer.get_fraud_risk_publishers(days, threshold_pct, bidder_id)
        return {
            "period_days": days,
            "ivt_threshold_pct": threshold_pct,
            "fraud_risk_publishers": result,
            "count": len(result),
        }
    except Exception as e:
        logger.error(f"Failed to get fraud risk publishers: {e}")
        raise HTTPException(status_code=500, detail=str(e))
