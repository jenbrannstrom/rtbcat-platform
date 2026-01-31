"""Service layer for QPS optimization reporting."""

from __future__ import annotations

from datetime import datetime, timezone

from importers import (
    get_import_summary,
    QpsSizeCoverageAnalyzer,
    ConfigPerformanceTracker,
    FraudSignalDetector,
    ACCOUNT_ID,
    ACCOUNT_NAME,
)


class QpsService:
    """Orchestrates QPS reporting and summaries."""

    def get_summary(self) -> dict:
        """Return summary of imported QPS data."""
        return get_import_summary()

    def size_coverage_report(self, days: int) -> dict:
        analyzer = QpsSizeCoverageAnalyzer()
        return {
            "report": analyzer.generate_report(days),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "analysis_days": days,
        }

    def config_performance_report(self, days: int) -> dict:
        tracker = ConfigPerformanceTracker()
        return {
            "report": tracker.generate_report(days),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "analysis_days": days,
        }

    def fraud_signals_report(self, days: int) -> dict:
        detector = FraudSignalDetector()
        return {
            "report": detector.generate_report(days),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "analysis_days": days,
        }

    def full_report(self, days: int) -> dict:
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

        try:
            analyzer = QpsSizeCoverageAnalyzer()
            lines.append(analyzer.generate_report(days))
            lines.append("")
        except Exception as exc:
            lines.append(f"Size Coverage: Error - {exc}")
            lines.append("")

        try:
            tracker = ConfigPerformanceTracker()
            lines.append(tracker.generate_report(days))
            lines.append("")
        except Exception as exc:
            lines.append(f"Config Performance: Error - {exc}")
            lines.append("")

        try:
            detector = FraudSignalDetector()
            lines.append(detector.generate_report(days * 2))
            lines.append("")
        except Exception as exc:
            lines.append(f"Fraud Signals: Error - {exc}")
            lines.append("")

        lines.append("=" * 80)
        lines.append("END OF FULL REPORT")
        lines.append("=" * 80)

        return {
            "report": "\n".join(lines),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "analysis_days": days,
        }
