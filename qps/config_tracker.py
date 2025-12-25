"""Config Performance Tracker for QPS Optimization.

Compares efficiency and performance across your 10 pretargeting configs,
identifying configs that need investigation.

Example:
    >>> from qps.config_tracker import ConfigPerformanceTracker
    >>> tracker = ConfigPerformanceTracker()
    >>> report = tracker.generate_report(days=7)
    >>> print(report)
"""

import sqlite3
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass

from qps.constants import PRETARGETING_CONFIGS
from qps.models import ConfigPerformance

logger = logging.getLogger(__name__)

DB_PATH = os.path.expanduser("~/.catscan/catscan.db")


@dataclass
class ConfigReport:
    """Complete config performance report."""

    configs: List[ConfigPerformance]
    total_reached: int
    total_impressions: int
    total_spend_usd: float
    average_efficiency: float
    configs_needing_review: List[str]
    analysis_days: int
    generated_at: str


class ConfigPerformanceTracker:
    """Tracks performance metrics by pretargeting config (billing_id)."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def get_config_metrics(self, days: int = 7) -> Dict[str, Dict]:
        """
        Get aggregated metrics by billing_id from rtb_daily.
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        metrics: Dict[str, Dict] = {}

        try:
            cursor.execute("""
                SELECT
                    billing_id,
                    SUM(COALESCE(reached_queries, 0)) as total_reached,
                    SUM(COALESCE(impressions, 0)) as total_impressions,
                    SUM(COALESCE(clicks, 0)) as total_clicks,
                    SUM(COALESCE(spend_micros, 0)) as total_spend_micros
                FROM rtb_daily
                WHERE metric_date >= ?
                  AND billing_id IS NOT NULL
                GROUP BY billing_id
            """, (cutoff_date,))

            for row in cursor.fetchall():
                billing_id = str(row[0])
                metrics[billing_id] = {
                    "reached_queries": row[1] or 0,
                    "impressions": row[2] or 0,
                    "clicks": row[3] or 0,
                    "spend_micros": row[4] or 0,
                }

        finally:
            conn.close()

        return metrics

    def analyze_configs(self, days: int = 7) -> ConfigReport:
        """
        Analyze performance across all pretargeting configs.

        Args:
            days: Number of days of data to analyze

        Returns:
            ConfigReport with complete analysis
        """
        metrics = self.get_config_metrics(days)

        configs: List[ConfigPerformance] = []
        configs_needing_review: List[str] = []

        # Process each known billing ID
        for billing_id, config_info in PRETARGETING_CONFIGS.items():
            data = metrics.get(billing_id, {})

            reached = data.get("reached_queries", 0)
            impressions = data.get("impressions", 0)
            clicks = data.get("clicks", 0)
            spend_micros = data.get("spend_micros", 0)
            spend_usd = spend_micros / 1_000_000

            # Calculate efficiency (impressions / reached)
            efficiency = (impressions / reached * 100) if reached > 0 else 0

            # Identify issues
            issues: List[str] = []

            if reached == 0:
                issues.append("No data")
            elif efficiency < 60:
                issues.append("Low efficiency")
                configs_needing_review.append(billing_id)

            if reached > 0 and reached < 100:
                issues.append("Low volume")

            configs.append(ConfigPerformance(
                billing_id=billing_id,
                name=config_info["name"],
                reached_queries=reached,
                impressions=impressions,
                clicks=clicks,
                spend_usd=spend_usd,
                efficiency_pct=efficiency,
                issues=issues,
            ))

        # Also check for billing IDs in data that aren't in our known list
        for billing_id, data in metrics.items():
            if billing_id not in PRETARGETING_CONFIGS:
                reached = data.get("reached_queries", 0)
                impressions = data.get("impressions", 0)
                clicks = data.get("clicks", 0)
                spend_usd = data.get("spend_micros", 0) / 1_000_000
                efficiency = (impressions / reached * 100) if reached > 0 else 0

                configs.append(ConfigPerformance(
                    billing_id=billing_id,
                    name=f"Unknown Config {billing_id}",
                    reached_queries=reached,
                    impressions=impressions,
                    clicks=clicks,
                    spend_usd=spend_usd,
                    efficiency_pct=efficiency,
                    issues=["Unknown billing ID"],
                ))

        # Sort by reached queries
        configs.sort(key=lambda x: x.reached_queries, reverse=True)

        # Calculate totals
        total_reached = sum(c.reached_queries for c in configs)
        total_impressions = sum(c.impressions for c in configs)
        total_spend = sum(c.spend_usd for c in configs)
        avg_efficiency = (total_impressions / total_reached * 100) if total_reached > 0 else 0

        return ConfigReport(
            configs=configs,
            total_reached=total_reached,
            total_impressions=total_impressions,
            total_spend_usd=total_spend,
            average_efficiency=avg_efficiency,
            configs_needing_review=configs_needing_review,
            analysis_days=days,
            generated_at=datetime.now().isoformat(),
        )

    def generate_report(self, days: int = 7) -> str:
        """Generate human-readable config performance report (printout)."""
        report = self.analyze_configs(days)

        lines = []
        lines.append("=" * 80)
        lines.append(f"CONFIG PERFORMANCE REPORT (last {report.analysis_days} days)")
        lines.append("=" * 80)
        lines.append(f"Generated: {report.generated_at}")
        lines.append("")

        # Summary
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"Total Reached Queries: {report.total_reached:>15,}")
        lines.append(f"Total Impressions:     {report.total_impressions:>15,}")
        lines.append(f"Total Spend:           ${report.total_spend_usd:>14,.2f}")
        lines.append(f"Average Efficiency:    {report.average_efficiency:>14.1f}%")
        lines.append("")

        # Config breakdown
        lines.append("-" * 80)
        lines.append(f"{'Billing ID':<15} {'Name':<20} {'Reached':>12} {'Impr':>10} {'Eff%':>8} {'Issues'}")
        lines.append("-" * 80)

        for config in report.configs:
            issues_str = ", ".join(config.issues) if config.issues else "None"
            name_truncated = config.name[:18] if len(config.name) > 18 else config.name

            lines.append(
                f"{config.billing_id:<15} "
                f"{name_truncated:<20} "
                f"{config.reached_queries:>12,} "
                f"{config.impressions:>10,} "
                f"{config.efficiency_pct:>7.1f}% "
                f"{issues_str}"
            )

        lines.append("")

        # Investigation needed
        if report.configs_needing_review:
            lines.append("=" * 80)
            lines.append("INVESTIGATION NEEDED")
            lines.append("=" * 80)
            lines.append("")

            for billing_id in report.configs_needing_review:
                config = next((c for c in report.configs if c.billing_id == billing_id), None)
                if config:
                    lines.append(f"Config {billing_id} ({config.name})")
                    lines.append(f"  - Efficiency: {config.efficiency_pct:.1f}% (below 60% threshold)")
                    lines.append("  - Possible causes:")
                    lines.append("    * Size mismatch (check size distribution for this config)")
                    lines.append("    * Poor inventory quality in target geos")
                    lines.append("    * Pretargeting too broad")
                    lines.append("")

        lines.append("=" * 80)
        lines.append("END OF CONFIG PERFORMANCE REPORT")
        lines.append("=" * 80)

        return "\n".join(lines)


if __name__ == "__main__":
    import sys

    days = 7
    if "--days" in sys.argv:
        idx = sys.argv.index("--days")
        if idx + 1 < len(sys.argv):
            days = int(sys.argv[idx + 1])

    tracker = ConfigPerformanceTracker()
    print(tracker.generate_report(days))
