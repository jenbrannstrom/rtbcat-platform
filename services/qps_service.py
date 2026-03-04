"""Service layer for QPS optimization reporting.

NOTE: The legacy SQLite-based CLI analyzers (QpsSizeCoverageAnalyzer,
ConfigPerformanceTracker, FraudSignalDetector) have been archived.
This service now returns deprecation notices. QPS efficiency metrics
are being rebuilt as part of the endpoint-efficiency API (see
docs/efficiency-qps-reconciliation-plan-2026-02-07.md).
"""

from __future__ import annotations

from datetime import datetime, timezone

from importers import ACCOUNT_ID, ACCOUNT_NAME

_DEPRECATED_MSG = (
    "This report relied on legacy SQLite analyzers which have been removed. "
    "QPS efficiency metrics are being rebuilt via the endpoint-efficiency API."
)


class QpsService:
    """Orchestrates QPS reporting and summaries."""

    def get_summary(self) -> dict:
        return {
            "total_rows": 0,
            "unique_dates": 0,
            "unique_billing_ids": 0,
            "unique_sizes": 0,
            "date_range": {"start": None, "end": None},
            "total_reached_queries": 0,
            "total_impressions": 0,
            "total_spend_usd": 0.0,
            "message": _DEPRECATED_MSG,
        }

    def size_coverage_report(self, days: int) -> dict:
        return {
            "report": _DEPRECATED_MSG,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "analysis_days": days,
        }

    def config_performance_report(self, days: int) -> dict:
        return {
            "report": _DEPRECATED_MSG,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "analysis_days": days,
        }

    def fraud_signals_report(self, days: int) -> dict:
        return {
            "report": _DEPRECATED_MSG,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "analysis_days": days,
        }

    def full_report(self, days: int) -> dict:
        return {
            "report": _DEPRECATED_MSG,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "analysis_days": days,
            "account_name": ACCOUNT_NAME,
            "account_id": ACCOUNT_ID,
        }
