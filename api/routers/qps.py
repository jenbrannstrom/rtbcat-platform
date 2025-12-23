"""QPS Optimization router for Cat-Scan API.

This module provides endpoints for QPS (Queries Per Second) optimization analysis:
- QPS data summary
- Size coverage analysis
- Config performance tracking
- Fraud signal detection
- Comprehensive QPS reports
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query

from api.schemas.qps import QPSSummaryResponse, QPSReportResponse
from qps import (
    get_import_summary,
    SizeCoverageAnalyzer,
    ConfigPerformanceTracker,
    FraudSignalDetector,
    ACCOUNT_ID,
    ACCOUNT_NAME,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/qps", tags=["QPS Optimization"])


@router.get("/summary", response_model=QPSSummaryResponse)
async def get_qps_summary():
    """
    Get summary of imported QPS data.

    Returns counts of rows, dates, sizes, and totals from size_metrics_daily.
    """
    try:
        summary = get_import_summary()
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
    except Exception as e:
        logger.error(f"Failed to get QPS summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/size-coverage", response_model=QPSReportResponse)
async def get_size_coverage_report(days: int = Query(7, ge=1, le=90)):
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
        analyzer = SizeCoverageAnalyzer()
        report_text = analyzer.generate_report(days)

        return QPSReportResponse(
            report=report_text,
            generated_at=datetime.now(timezone.utc).isoformat(),
            analysis_days=days,
        )
    except Exception as e:
        logger.error(f"Failed to generate size coverage: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config-performance", response_model=QPSReportResponse)
async def get_config_performance_report(days: int = Query(7, ge=1, le=90)):
    """
    Get pretargeting config performance report.

    Compares efficiency across your 10 pretargeting configs to identify
    configs needing investigation.

    Args:
        days: Number of days to analyze (default: 7)
    """
    try:
        tracker = ConfigPerformanceTracker()
        report_text = tracker.generate_report(days)

        return QPSReportResponse(
            report=report_text,
            generated_at=datetime.now(timezone.utc).isoformat(),
            analysis_days=days,
        )
    except Exception as e:
        logger.error(f"Failed to generate config performance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fraud-signals", response_model=QPSReportResponse)
async def get_fraud_signals_report(days: int = Query(14, ge=1, le=90)):
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
        detector = FraudSignalDetector()
        report_text = detector.generate_report(days)

        return QPSReportResponse(
            report=report_text,
            generated_at=datetime.now(timezone.utc).isoformat(),
            analysis_days=days,
        )
    except Exception as e:
        logger.error(f"Failed to generate fraud signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report", response_model=QPSReportResponse)
async def get_full_qps_report(days: int = Query(7, ge=1, le=90)):
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
        lines = []
        lines.append("")
        lines.append("=" * 80)
        lines.append("Cat-Scan QPS OPTIMIZATION FULL REPORT")
        lines.append("=" * 80)
        lines.append("")
        lines.append(f"Account: {ACCOUNT_NAME} (ID: {ACCOUNT_ID})")
        lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
        lines.append(f"Analysis Period: {days} days")
        lines.append("")

        # Size Coverage
        try:
            analyzer = SizeCoverageAnalyzer()
            lines.append(analyzer.generate_report(days))
            lines.append("")
        except Exception as e:
            lines.append(f"Size Coverage: Error - {e}")
            lines.append("")

        # Config Performance
        try:
            tracker = ConfigPerformanceTracker()
            lines.append(tracker.generate_report(days))
            lines.append("")
        except Exception as e:
            lines.append(f"Config Performance: Error - {e}")
            lines.append("")

        # Fraud Signals
        try:
            detector = FraudSignalDetector()
            lines.append(detector.generate_report(days * 2))
            lines.append("")
        except Exception as e:
            lines.append(f"Fraud Signals: Error - {e}")
            lines.append("")

        lines.append("=" * 80)
        lines.append("END OF FULL REPORT")
        lines.append("=" * 80)

        report_text = "\n".join(lines)

        return QPSReportResponse(
            report=report_text,
            generated_at=datetime.now(timezone.utc).isoformat(),
            analysis_days=days,
        )
    except Exception as e:
        logger.error(f"Failed to generate full report: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/include-list")
async def get_include_list():
    """
    Get recommended pretargeting include list.

    Returns sizes that:
    1. You have creatives for
    2. Are in Google's 114-size pretargeting list

    WARNING: Adding these to pretargeting will EXCLUDE all other sizes!
    """
    try:
        analyzer = SizeCoverageAnalyzer()
        report = analyzer.analyze_coverage(days=7)

        return {
            "include_list": report.include_list,
            "count": len(report.include_list),
            "warning": "Adding these sizes will EXCLUDE all other sizes!",
            "instructions": [
                "Go to Authorized Buyers UI",
                "Navigate to Bidder Settings -> Pretargeting",
                "Edit the config you want to modify",
                "Under 'Creative dimensions', add these sizes",
                "Click Save",
                "Monitor traffic for 24-48 hours",
            ],
        }
    except Exception as e:
        logger.error(f"Failed to get include list: {e}")
        raise HTTPException(status_code=500, detail=str(e))
