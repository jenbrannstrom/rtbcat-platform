"""QPS Optimization router for Cat-Scan API.

This module provides endpoints for QPS (Queries Per Second) optimization analysis:
- QPS data summary
- Size coverage analysis
- Config performance tracking
- Fraud signal detection
- Comprehensive QPS reports
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from api.schemas.qps import QPSSummaryResponse, QPSReportResponse
from services.qps_service import QpsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/qps", tags=["QPS Optimization"])


@router.get("/summary", response_model=QPSSummaryResponse)
async def get_qps_summary() -> QPSSummaryResponse:
    """
    Get summary of imported QPS data.

    Returns counts of rows, dates, sizes, and totals from size_metrics_daily.
    """
    try:
        summary = QpsService().get_summary()
        return QPSSummaryResponse(
            total_rows=summary["total_rows"],
            unique_dates=summary["unique_dates"],
            unique_billing_ids=summary["unique_billing_ids"],
            unique_sizes=summary["unique_sizes"],
            date_range=summary["date_range"],
            total_reached_queries=summary["total_reached_queries"],
            total_impressions=summary["total_impressions"],
            total_spend_usd=summary["total_spend_usd"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get QPS summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/size-coverage", response_model=QPSReportResponse)
async def get_size_coverage_report(days: int = Query(7, ge=1, le=90)) -> QPSReportResponse:
    """
    Get size coverage analysis report.

    Compares your creative inventory against received traffic to identify:
    - Sizes you can serve
    - Sizes you cannot serve (waste)
    - Recommended pretargeting include list

    Args:
        days: Number of days to analyze (default: 7)
    """
    try:
        report = QpsService().size_coverage_report(days)
        return QPSReportResponse(**report)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate size coverage: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config-performance", response_model=QPSReportResponse)
async def get_config_performance_report(days: int = Query(7, ge=1, le=90)) -> QPSReportResponse:
    """
    Get pretargeting config performance report.

    Compares efficiency across your 10 pretargeting configs to identify
    configs needing investigation.

    Args:
        days: Number of days to analyze (default: 7)
    """
    try:
        report = QpsService().config_performance_report(days)
        return QPSReportResponse(**report)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate config performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fraud-signals", response_model=QPSReportResponse)
async def get_fraud_signals_report(days: int = Query(14, ge=1, le=90)) -> QPSReportResponse:
    """
    Get fraud signals report.

    Detects suspicious patterns for human review:
    - Unusually high CTR
    - Clicks exceeding impressions

    These are PATTERNS, not proof of fraud. All signals require human review.

    Args:
        days: Number of days to analyze (default: 14)
    """
    try:
        report = QpsService().fraud_signals_report(days)
        return QPSReportResponse(**report)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate fraud signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report", response_model=QPSReportResponse)
async def get_full_qps_report(days: int = Query(7, ge=1, le=90)) -> QPSReportResponse:
    """
    Get comprehensive QPS optimization report.

    Combines all analysis modules:
    1. Size Coverage Analysis
    2. Config Performance Tracking
    3. Fraud Signal Detection

    Args:
        days: Number of days to analyze (default: 7)
    """
    try:
        report = QpsService().full_report(days)
        return QPSReportResponse(**report)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate full report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/include-list")
async def get_include_list() -> dict[str, Any]:
    """
    Get recommended pretargeting include list.

    Returns sizes that:
    1. You have creatives for
    2. Are in Google's 114-size pretargeting list

    WARNING: Adding these to pretargeting will EXCLUDE all other sizes!
    """
    try:
        report = QpsService().size_coverage_report(days=7)

        return {
            "include_list": [],
            "count": 0,
            "warning": report.get("report", "Legacy include-list analyzer unavailable."),
            "deprecated": True,
            "instructions": [
                "Go to Authorized Buyers UI",
                "Navigate to Bidder Settings -> Pretargeting",
                "Edit the config you want to modify",
                "Under 'Creative dimensions', add these sizes",
                "Click Save",
                "Monitor traffic for 24-48 hours",
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get include list: {e}")
        raise HTTPException(status_code=500, detail=str(e))
