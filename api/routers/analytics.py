"""Analytics Router - Waste analysis, QPS analytics, and RTB funnel endpoints.

Handles creative waste analysis, size coverage, geo waste, pretargeting recommendations,
and RTB funnel analytics for Google Authorized Buyers.
"""

import csv
import io
import logging
from collections import defaultdict
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from storage.database import db_query, db_query_one
from analytics.waste_analyzer import WasteAnalyzer
from services.waste_analyzer import WasteAnalyzerService
from analytics.size_coverage_analyzer import SizeCoverageAnalyzer
from analytics.geo_waste_analyzer import GeoWasteAnalyzer
from analytics.pretargeting_recommender import PretargetingRecommender
from analytics.rtb_funnel_analyzer import RTBFunnelAnalyzer
from analytics.qps_optimizer import QPSOptimizer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Analytics"])


async def get_current_bidder_id() -> Optional[str]:
    """Get the current bidder_id from the most recently synced pretargeting config.

    Returns the bidder_id that was most recently synced, which represents
    the currently active account.
    """
    try:
        row = await db_query_one("""
            SELECT bidder_id FROM pretargeting_configs
            WHERE bidder_id IS NOT NULL
            ORDER BY synced_at DESC
            LIMIT 1
        """)
        return row["bidder_id"] if row else None
    except Exception:
        return None


async def get_valid_billing_ids() -> list[str]:
    """Get list of billing_ids from pretargeting_configs table for current account.

    This ensures we only query data for billing IDs that belong to the
    currently configured account, preventing cross-account data mixing.

    The function first identifies the current bidder_id (account), then
    returns only billing_ids associated with that account.
    """
    try:
        # Get the current bidder_id (most recently synced account)
        current_bidder = await get_current_bidder_id()

        if current_bidder:
            # Filter by the current account's bidder_id
            rows = await db_query(
                "SELECT DISTINCT billing_id FROM pretargeting_configs WHERE billing_id IS NOT NULL AND bidder_id = ?",
                (current_bidder,)
            )
        else:
            # Fallback: return all billing_ids if no bidder_id found
            rows = await db_query(
                "SELECT DISTINCT billing_id FROM pretargeting_configs WHERE billing_id IS NOT NULL"
            )

        return [row["billing_id"] for row in rows]
    except Exception:
        return []


# =============================================================================
# Pydantic Models
# =============================================================================

class SizeGapResponse(BaseModel):
    """Response model for a size gap in waste analysis."""
    canonical_size: str
    request_count: int
    creative_count: int
    estimated_qps: float
    estimated_waste_pct: float
    recommendation: str
    recommendation_detail: str
    potential_savings_usd: Optional[float] = None
    closest_iab_size: Optional[str] = None


class SizeCoverageResponse(BaseModel):
    """Response model for size coverage data."""
    canonical_size: str
    creative_count: int
    request_count: int
    coverage_status: str
    formats: dict = Field(default_factory=dict)


class WasteReportResponse(BaseModel):
    """Response model for waste analysis report."""
    buyer_id: Optional[str]
    total_requests: int
    total_waste_requests: int
    waste_percentage: float
    size_gaps: list[SizeGapResponse]
    size_coverage: list[SizeCoverageResponse]
    potential_savings_qps: float
    potential_savings_usd: Optional[float]
    analysis_period_days: int
    generated_at: str
    recommendations_summary: dict = Field(default_factory=dict)


class WasteSignalResponse(BaseModel):
    """Response model for a waste signal."""
    id: int
    creative_id: str
    signal_type: str
    confidence: str
    evidence: dict
    observation: str
    recommendation: str
    detected_at: str
    resolved_at: Optional[str] = None


class ProblemFormatResponse(BaseModel):
    """Response model for problem format detection."""
    creative_id: str
    problem_type: str
    evidence: dict
    severity: str
    recommendation: str


class ImportTrafficResponse(BaseModel):
    """Response model for traffic import operation."""
    status: str
    records_imported: int
    message: str


# =============================================================================
# Helper Functions
# =============================================================================

def _group_signals_by_type(signals) -> dict[str, int]:
    """Group signals by type and count."""
    counts = {}
    for s in signals:
        counts[s.signal_type] = counts.get(s.signal_type, 0) + 1
    return counts


# =============================================================================
# Waste Analysis Endpoints
# =============================================================================

@router.get("/analytics/waste", response_model=WasteReportResponse)
async def get_waste_report(
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    days: int = Query(7, ge=1, le=90, description="Days of traffic to analyze"),
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
        # WasteAnalyzer uses its own db connection internally
        analyzer = WasteAnalyzer()
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
):
    """Get evidence-based waste signals for a creative.

    Phase 11.2: Evidence-Based Waste Detection
    Returns signals with full evidence chain explaining WHY the creative is flagged.
    """
    service = WasteAnalyzerService()
    signals = service.get_signals_for_creative(creative_id, include_resolved=include_resolved)
    return [WasteSignalResponse(**s) for s in signals]


@router.get("/analytics/problem-formats", response_model=list[ProblemFormatResponse])
async def detect_problem_formats(
    buyer_id: Optional[str] = Query(None, description="Filter by buyer seat ID"),
    days: int = Query(7, ge=1, le=90, description="Timeframe for analysis"),
    size_tolerance: int = Query(5, ge=0, le=20, description="Pixel tolerance for size matching"),
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
    analyzer = WasteAnalyzer()
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
    service = WasteAnalyzerService()
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
    service = WasteAnalyzerService()
    success = service.resolve_signal(signal_id, resolved_by="user", notes=notes)

    if not success:
        raise HTTPException(status_code=404, detail="Signal not found")

    return {"status": "resolved", "signal_id": signal_id}


@router.post("/analytics/import-traffic", response_model=ImportTrafficResponse)
async def import_traffic_data(
    file: UploadFile = File(..., description="CSV file with traffic data"),
):
    """Import RTB traffic data from CSV file.

    The CSV file should have the following columns:
    - **canonical_size**: Normalized size category (e.g., "300x250 (Medium Rectangle)")
    - **raw_size**: Original requested size (e.g., "300x250")
    - **request_count**: Number of bid requests
    - **date**: Date in YYYY-MM-DD format
    - **buyer_id** (optional): Buyer seat ID

    Example CSV:
    ```
    canonical_size,raw_size,request_count,date,buyer_id
    "300x250 (Medium Rectangle)",300x250,50000,2024-01-15,456
    "Non-Standard (320x481)",320x481,12000,2024-01-15,456
    ```
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a CSV")

    try:
        # Read and parse CSV
        contents = await file.read()
        text = contents.decode("utf-8")
        reader = csv.DictReader(io.StringIO(text))

        # Validate required columns
        required_columns = {"canonical_size", "raw_size", "request_count", "date"}
        if reader.fieldnames is None:
            raise HTTPException(status_code=400, detail="CSV file is empty or malformed")

        missing = required_columns - set(reader.fieldnames)
        if missing:
            raise HTTPException(
                status_code=400,
                detail=f"CSV missing required columns: {', '.join(missing)}",
            )

        # Parse records
        records = []
        for row in reader:
            try:
                records.append(
                    {
                        "canonical_size": row["canonical_size"],
                        "raw_size": row["raw_size"],
                        "request_count": int(row["request_count"]),
                        "date": row["date"],
                        "buyer_id": row.get("buyer_id") or None,
                    }
                )
            except (ValueError, KeyError) as e:
                logger.warning(f"Skipping invalid row: {row}, error: {e}")
                continue

        if not records:
            raise HTTPException(status_code=400, detail="No valid records found in CSV")

        # Store traffic data - use db_execute for inserts
        from storage.database import db_execute
        count = 0
        for r in records:
            await db_execute(
                """INSERT OR REPLACE INTO rtb_traffic
                (canonical_size, raw_size, request_count, traffic_date, buyer_id)
                VALUES (?, ?, ?, ?, ?)""",
                (r["canonical_size"], r["raw_size"], r["request_count"], r["date"], r["buyer_id"])
            )
            count += 1

        return ImportTrafficResponse(
            status="completed",
            records_imported=count,
            message=f"Successfully imported {count} traffic records.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Traffic import failed: {e}")
        raise HTTPException(status_code=500, detail=f"Traffic import failed: {str(e)}")


@router.post("/analytics/generate-mock-traffic", response_model=ImportTrafficResponse)
async def generate_mock_traffic_endpoint(
    days: int = Query(7, ge=1, le=30, description="Days of traffic to generate"),
    buyer_id: Optional[str] = Query(None, description="Buyer ID to associate"),
    base_daily_requests: int = Query(100000, ge=1000, le=1000000, description="Base daily request volume"),
    waste_bias: float = Query(0.3, ge=0.0, le=1.0, description="Bias towards waste traffic (0-1)"),
):
    """Generate mock RTB traffic data for testing and demos.

    Creates synthetic bid request data with realistic distributions including:
    - IAB standard sizes (high volume)
    - Non-standard sizes (configurable waste)
    - Video sizes
    - Day-over-day variance

    Use `waste_bias` to control how much non-standard (waste) traffic is generated:
    - 0.0 = minimal waste, mostly standard sizes
    - 0.5 = balanced mix
    - 1.0 = heavy waste traffic
    """
    from analytics import generate_mock_traffic
    from storage.database import db_execute

    try:
        # Generate mock traffic
        traffic_records = generate_mock_traffic(
            days=days,
            buyer_id=buyer_id,
            base_daily_requests=base_daily_requests,
            waste_bias=waste_bias,
        )

        # Store traffic data
        count = 0
        for r in traffic_records:
            await db_execute(
                """INSERT OR REPLACE INTO rtb_traffic
                (canonical_size, raw_size, request_count, traffic_date, buyer_id)
                VALUES (?, ?, ?, ?, ?)""",
                (r.canonical_size, r.raw_size, r.request_count, r.date, r.buyer_id)
            )
            count += 1

        return ImportTrafficResponse(
            status="completed",
            records_imported=count,
            message=f"Generated and imported {count} mock traffic records for {days} days.",
        )

    except Exception as e:
        logger.error(f"Mock traffic generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Mock traffic generation failed: {str(e)}")


# =============================================================================
# QPS Analytics Endpoints (Phase 27)
# =============================================================================

@router.get("/analytics/size-coverage", tags=["QPS Analytics"])
async def get_size_coverage(
    days: int = Query(7, ge=1, le=90),
    billing_id: Optional[str] = Query(None, description="Filter by billing account ID (pretargeting config)")
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
        analyzer = SizeCoverageAnalyzer(str(DB_PATH))
        summary = analyzer.analyze(days, billing_id=billing_id)
        return {
            "period_days": days,
            "billing_id": billing_id,
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
async def get_geo_waste(days: int = Query(7, ge=1, le=90)):
    """
    Analyze geographic QPS waste.

    Returns geos with poor performance that should be excluded from pretargeting.
    """
    try:
        from storage.database import DB_PATH
        analyzer = GeoWasteAnalyzer(str(DB_PATH))
        summary = analyzer.analyze(days)
        return {
            "period_days": days,
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
async def get_qps_summary(days: int = Query(7, ge=1, le=90)):
    """
    High-level QPS efficiency summary.

    Combines size coverage and geo waste analysis into a single dashboard view.
    """
    try:
        from storage.database import DB_PATH
        size_analyzer = SizeCoverageAnalyzer(str(DB_PATH))
        geo_analyzer = GeoWasteAnalyzer(str(DB_PATH))

        size_summary = size_analyzer.analyze(days)
        geo_summary = geo_analyzer.analyze(days)

        # Calculate total estimated waste
        # Size gaps are 100% waste, geo waste is partial
        size_waste_pct = 100 - size_summary.coverage_rate if size_summary.coverage_rate > 0 else 0

        return {
            "period_days": days,
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


# =============================================================================
# RTB Funnel Analytics Endpoints (Phase 28)
# =============================================================================

@router.get("/analytics/spend-stats", tags=["RTB Analytics"])
async def get_spend_stats(
    days: int = Query(7, ge=1, le=90),
    billing_id: Optional[str] = Query(None, description="Filter by specific billing account ID")
):
    """
    Get overall spend statistics for the selected period.

    Returns total spend, impressions, and avg CPM from rtb_daily table.
    Only includes data for billing_ids that belong to the current account.
    Optionally filter by a specific billing_id.
    """
    try:
        if billing_id:
            # Filter by specific billing_id
            row = await db_query_one("""
                SELECT
                    COALESCE(SUM(impressions), 0) as total_impressions,
                    COALESCE(SUM(spend_micros), 0) as total_spend_micros
                FROM rtb_daily
                WHERE metric_date >= date('now', ?)
                  AND billing_id = ?
            """, (f'-{days} days', billing_id))
        else:
            # Get valid billing IDs for current account to prevent cross-account data mixing
            valid_billing_ids = await get_valid_billing_ids()

            if valid_billing_ids:
                # Filter by valid billing IDs
                placeholders = ",".join("?" * len(valid_billing_ids))
                row = await db_query_one(f"""
                    SELECT
                        COALESCE(SUM(impressions), 0) as total_impressions,
                        COALESCE(SUM(spend_micros), 0) as total_spend_micros
                    FROM rtb_daily
                    WHERE metric_date >= date('now', ?)
                      AND billing_id IN ({placeholders})
                """, (f'-{days} days', *valid_billing_ids))
            else:
                # No pretargeting configs synced yet - return all data as fallback
                row = await db_query_one("""
                    SELECT
                        COALESCE(SUM(impressions), 0) as total_impressions,
                        COALESCE(SUM(spend_micros), 0) as total_spend_micros
                    FROM rtb_daily
                    WHERE metric_date >= date('now', ?)
                """, (f'-{days} days',))

        total_impressions = row["total_impressions"] if row else 0
        total_spend_micros = row["total_spend_micros"] if row else 0
        total_spend_usd = total_spend_micros / 1_000_000

        # Calculate CPM: (spend / impressions) * 1000
        avg_cpm = None
        if total_impressions > 0 and total_spend_micros > 0:
            avg_cpm = (total_spend_usd / total_impressions) * 1000

        return {
            "period_days": days,
            "total_impressions": total_impressions,
            "total_spend_usd": round(total_spend_usd, 2),
            "avg_cpm_usd": round(avg_cpm, 2) if avg_cpm else None,
            "has_spend_data": total_spend_micros > 0,
        }
    except Exception as e:
        logger.error(f"Failed to get spend stats: {e}")
        return {
            "period_days": days,
            "total_impressions": 0,
            "total_spend_usd": 0,
            "avg_cpm_usd": None,
            "has_spend_data": False,
        }


@router.get("/analytics/rtb-funnel", tags=["RTB Analytics"])
async def get_rtb_funnel():
    """
    Get RTB funnel analysis from Google Authorized Buyers data.

    Parses the bidding metrics CSVs to provide:
    - Funnel summary: Bid Requests → Reached Queries → Impressions
    - Publisher performance with win rates
    - Geographic breakdown
    - Creative-level metrics
    """
    try:
        analyzer = RTBFunnelAnalyzer()
        return analyzer.get_full_analysis()
    except Exception as e:
        logger.error(f"Failed to get RTB funnel data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/rtb-funnel/publishers", tags=["RTB Analytics"])
async def get_rtb_publishers(limit: int = Query(30, ge=1, le=100)):
    """
    Get publisher performance breakdown.

    Shows win rates and pretargeting filter rates by publisher.
    """
    try:
        analyzer = RTBFunnelAnalyzer()
        return {
            "publishers": analyzer.get_publisher_performance(limit=limit),
            "count": len(analyzer._publishers) if analyzer._data_loaded else 0,
        }
    except Exception as e:
        logger.error(f"Failed to get publisher performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/rtb-funnel/geos", tags=["RTB Analytics"])
async def get_rtb_geos(limit: int = Query(30, ge=1, le=100)):
    """
    Get geographic performance breakdown.

    Shows win rates and auction participation by country.
    """
    try:
        analyzer = RTBFunnelAnalyzer()
        return {
            "geos": analyzer.get_geo_performance(limit=limit),
            "count": len(analyzer._geos) if analyzer._data_loaded else 0,
        }
    except Exception as e:
        logger.error(f"Failed to get geo performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Phase 29: Multi-View Waste Analysis Endpoints
# =============================================================================

@router.get("/analytics/rtb-funnel/configs", tags=["RTB Analytics"])
async def get_config_performance(
    days: int = Query(7, ge=1, le=30),
):
    """
    Get performance breakdown by pretargeting config (billing_id).

    Reads from the rtb_daily table (populated by CSV import) and aggregates
    by billing_id to show:
    - Reached queries and impressions per config
    - Size-level performance within each config
    - Win rate vs waste percentages
    - Settings derived from the data (format, geos, platforms)

    Only returns data for billing_ids that belong to the current account
    (those synced in pretargeting_configs table).
    """
    try:
        # Get valid billing IDs for current account to prevent cross-account data mixing
        valid_billing_ids = await get_valid_billing_ids()

        # Query aggregated data by billing_id from rtb_daily
        if valid_billing_ids:
            placeholders = ",".join("?" * len(valid_billing_ids))
            rows = await db_query(f"""
                SELECT
                    billing_id,
                    creative_size,
                    creative_format,
                    country,
                    platform,
                    SUM(reached_queries) as total_reached,
                    SUM(impressions) as total_impressions
                FROM rtb_daily
                WHERE metric_date >= date('now', ?)
                  AND billing_id IN ({placeholders})
                GROUP BY billing_id, creative_size, creative_format, country, platform
                ORDER BY total_reached DESC
            """, (f'-{days} days', *valid_billing_ids))
        else:
            # No pretargeting configs synced yet - return all data as fallback
            rows = await db_query("""
                SELECT
                    billing_id,
                    creative_size,
                    creative_format,
                    country,
                    platform,
                    SUM(reached_queries) as total_reached,
                    SUM(impressions) as total_impressions
                FROM rtb_daily
                WHERE metric_date >= date('now', ?)
                GROUP BY billing_id, creative_size, creative_format, country, platform
                ORDER BY total_reached DESC
            """, (f'-{days} days',))

        if not rows:
            # No data in database
            return {
                "period_days": days,
                "data_source": "database",
                "configs": [],
                "total_reached": 0,
                "total_impressions": 0,
                "overall_win_rate_pct": 0,
                "overall_waste_pct": 100,
            }

        # Aggregate by billing_id
        configs_by_billing: dict = defaultdict(lambda: {
            "reached": 0,
            "impressions": 0,
            "sizes": defaultdict(lambda: {"reached": 0, "impressions": 0}),
            "formats": set(),
            "countries": set(),
            "platforms": set(),
        })

        for row in rows:
            billing_id = row["billing_id"]
            config = configs_by_billing[billing_id]
            config["reached"] += row["total_reached"] or 0
            config["impressions"] += row["total_impressions"] or 0

            # Track size breakdown
            size = row["creative_size"] or "unknown"
            config["sizes"][size]["reached"] += row["total_reached"] or 0
            config["sizes"][size]["impressions"] += row["total_impressions"] or 0

            # Track settings
            if row["creative_format"]:
                config["formats"].add(row["creative_format"])
            if row["country"]:
                config["countries"].add(row["country"])
            if row["platform"]:
                config["platforms"].add(row["platform"])

        # Convert to response format
        configs = []
        total_reached = 0
        total_impressions = 0

        for billing_id, config in sorted(configs_by_billing.items(), key=lambda x: x[1]["reached"], reverse=True):
            reached = config["reached"]
            impressions = config["impressions"]
            win_rate = (impressions / reached * 100) if reached > 0 else 0
            waste = 100 - win_rate

            total_reached += reached
            total_impressions += impressions

            # Convert sizes dict to list
            sizes_list = []
            for size, size_data in sorted(config["sizes"].items(), key=lambda x: x[1]["reached"], reverse=True):
                size_reached = size_data["reached"]
                size_impressions = size_data["impressions"]
                size_win = (size_impressions / size_reached * 100) if size_reached > 0 else 0
                sizes_list.append({
                    "size": size,
                    "reached": size_reached,
                    "impressions": size_impressions,
                    "win_rate_pct": round(size_win, 1),
                    "waste_pct": round(100 - size_win, 1),
                })

            # Determine format from collected formats
            formats = list(config["formats"])
            primary_format = formats[0] if formats else "BANNER"

            configs.append({
                "billing_id": billing_id,
                "name": f"Config {billing_id}",
                "reached": reached,
                "bids": 0,
                "impressions": impressions,
                "win_rate_pct": round(win_rate, 1),
                "waste_pct": round(waste, 1),
                "settings": {
                    "format": primary_format,
                    "geos": sorted(list(config["countries"]))[:10],
                    "platforms": sorted(list(config["platforms"])),
                    "qps_limit": None,
                    "budget_usd": None,
                },
                "sizes": sizes_list[:5],
            })

        overall_win = (total_impressions / total_reached * 100) if total_reached > 0 else 0

        return {
            "period_days": days,
            "data_source": "database",
            "configs": configs[:20],
            "total_reached": total_reached,
            "total_impressions": total_impressions,
            "overall_win_rate_pct": round(overall_win, 1),
            "overall_waste_pct": round(100 - overall_win, 1),
        }

    except Exception as e:
        logger.error(f"Failed to get config performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/rtb-funnel/configs/{billing_id}/breakdown", tags=["RTB Analytics"])
async def get_config_breakdown(
    billing_id: str,
    by: str = Query("size", regex="^(size|geo|publisher|creative)$"),
    days: int = Query(7, ge=1, le=30),
):
    """
    Get detailed breakdown for a specific pretargeting config.

    Breakdown types:
    - size: By creative size (300x250, 320x50, etc.)
    - geo: By country/region
    - publisher: By app/publisher
    - creative: By individual creative ID
    """
    # Map breakdown type to column
    column_map = {
        "size": "creative_size",
        "geo": "country",
        "publisher": "app_name",
        "creative": "creative_id",
    }
    group_col = column_map.get(by, "creative_size")

    try:
        # Query aggregated data for this billing_id
        rows = await db_query(f"""
            SELECT
                {group_col} as name,
                SUM(reached_queries) as total_reached,
                SUM(impressions) as total_impressions
            FROM rtb_daily
            WHERE billing_id = ?
              AND metric_date >= date('now', ?)
              AND {group_col} IS NOT NULL
              AND {group_col} != ''
            GROUP BY {group_col}
            ORDER BY total_reached DESC
            LIMIT 50
        """, (billing_id, f'-{days} days'))

        breakdown = []
        for row in rows:
            reached = row["total_reached"] or 0
            impressions = row["total_impressions"] or 0
            win_rate = (impressions / reached * 100) if reached > 0 else 0
            waste_rate = 100 - win_rate

            breakdown.append({
                "name": row["name"] or "Unknown",
                "reached": reached,
                "win_rate": round(win_rate, 1),
                "waste_rate": round(waste_rate, 1),
            })

        return {
            "billing_id": billing_id,
            "breakdown_by": by,
            "breakdown": breakdown,
        }

    except Exception as e:
        logger.error(f"Failed to get config breakdown: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/rtb-funnel/creatives", tags=["RTB Analytics"])
async def get_creative_win_performance(
    days: int = Query(7, ge=1, le=30),
    limit: int = Query(50, ge=1, le=200)
):
    """
    Get creative performance using WIN RATE metrics.

    Shows: reached, bids, impressions won, win rate, waste
    NOT: clicks, CTR, conversions (that's media buyer's job)

    Status classification:
    - great: >50% win rate
    - ok: 20-50% win rate
    - review: <20% win rate
    """
    try:
        analyzer = RTBFunnelAnalyzer()
        result = analyzer.get_creative_win_performance(limit=limit)
        result["period_days"] = days
        return result
    except Exception as e:
        logger.error(f"Failed to get creative win performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# QPS Optimization Endpoints (Enhanced Analysis)
# =============================================================================

@router.get("/analytics/qps-optimization", tags=["QPS Optimization"])
async def get_qps_optimization_report(
    days: int = Query(7, ge=1, le=30),
    bidder_id: Optional[str] = Query(None, description="Filter by bidder account ID"),
):
    """
    Get comprehensive QPS optimization report with actionable recommendations.

    This endpoint JOINs data from:
    - rtb_funnel (bid pipeline metrics)
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

    JOINs rtb_funnel + rtb_daily to calculate:
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


@router.get("/analytics/fraud-risk", tags=["QPS Optimization"])
async def get_fraud_risk_publishers(
    days: int = Query(7, ge=1, le=30),
    threshold_pct: float = Query(5.0, ge=0, le=100, description="IVT rate threshold"),
    bidder_id: Optional[str] = Query(None, description="Filter by bidder account ID"),
):
    """
    Find publishers with high fraud/IVT rates.

    Returns publishers with IVT rate above threshold.
    Use this to identify publishers to block.
    """
    try:
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


@router.get("/analytics/viewability-waste", tags=["QPS Optimization"])
async def get_viewability_waste(
    days: int = Query(7, ge=1, le=30),
    threshold_pct: float = Query(50.0, ge=0, le=100, description="Viewability threshold"),
    bidder_id: Optional[str] = Query(None, description="Filter by bidder account ID"),
):
    """
    Find publishers with low viewability but high spend.

    Returns publishers with viewability below threshold.
    Use this to identify where to reduce bids.
    """
    try:
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
