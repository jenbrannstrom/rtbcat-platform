"""Size Coverage Analyzer for QPS Optimization.

Compares the creative sizes you're receiving (from imported CSV data)
against the creatives you have (from API sync) to identify:

1. Sizes you CAN serve (have creatives for)
2. Sizes you CANNOT serve (receiving QPS but no creatives = WASTE)
3. What an INCLUDE list would look like for pretargeting

Example:
    >>> from qps.size_analyzer import SizeCoverageAnalyzer
    >>> analyzer = SizeCoverageAnalyzer()
    >>> report = analyzer.generate_report(days=7)
    >>> print(report)
"""

import sqlite3
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass

from qps.constants import GOOGLE_AVAILABLE_SIZES, PRETARGETING_CONFIGS
from qps.models import CreativeSizeInfo, SizeCoverageResult

logger = logging.getLogger(__name__)

DB_PATH = os.path.expanduser("~/.catscan/catscan.db")


@dataclass
class CoverageReport:
    """Complete size coverage analysis report."""

    # Summary metrics
    total_creatives: int
    sizes_in_inventory: int
    sizes_in_traffic: int
    sizes_you_can_serve: int
    sizes_you_cannot_serve: int

    # QPS metrics
    total_reached_queries: int
    servable_reached_queries: int
    waste_queries: int
    match_rate_pct: float

    # Detailed data
    inventory_sizes: List[CreativeSizeInfo]
    coverage_results: List[SizeCoverageResult]
    include_list: List[str]
    opportunities: List[Dict]

    # Metadata
    analysis_days: int
    generated_at: str


class SizeCoverageAnalyzer:
    """Analyzes size coverage between your inventory and market traffic."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def get_inventory_sizes(self) -> Dict[str, CreativeSizeInfo]:
        """
        Get sizes from your creative inventory (creatives table).

        Returns dict of {size_string: CreativeSizeInfo}
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        sizes: Dict[str, CreativeSizeInfo] = {}

        try:
            # Get sizes from creatives table
            # Handle both width/height and canonical_size fields
            cursor.execute("""
                SELECT
                    CASE
                        WHEN width IS NOT NULL AND height IS NOT NULL AND width > 0 AND height > 0
                        THEN CAST(width AS TEXT) || 'x' || CAST(height AS TEXT)
                        ELSE canonical_size
                    END as size,
                    format,
                    id
                FROM creatives
                WHERE (width IS NOT NULL AND height IS NOT NULL AND width > 0 AND height > 0)
                   OR (canonical_size IS NOT NULL AND canonical_size != '')
            """)

            for row in cursor.fetchall():
                size_str = row[0]
                format_type = row[1] or "UNKNOWN"
                creative_id = str(row[2])

                if not size_str:
                    continue

                if size_str not in sizes:
                    sizes[size_str] = CreativeSizeInfo(
                        size=size_str,
                        creative_count=0,
                        formats={},
                        creative_ids=[],
                    )

                info = sizes[size_str]
                info.creative_count += 1
                info.formats[format_type] = info.formats.get(format_type, 0) + 1
                if len(info.creative_ids) < 10:  # Keep sample of IDs
                    info.creative_ids.append(creative_id)

        finally:
            conn.close()

        return sizes

    def get_traffic_sizes(self, days: int = 7) -> Dict[str, Dict]:
        """
        Get sizes from rtb_daily table.
        Aggregates at query time (not import time).
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cutoff_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        sizes: Dict[str, Dict] = {}

        try:
            cursor.execute("""
                SELECT
                    creative_size,
                    SUM(COALESCE(reached_queries, 0)) as total_reached,
                    SUM(COALESCE(impressions, 0)) as total_impressions,
                    SUM(COALESCE(clicks, 0)) as total_clicks,
                    SUM(COALESCE(spend_micros, 0)) as total_spend
                FROM rtb_daily
                WHERE metric_date >= ?
                  AND creative_size IS NOT NULL
                  AND creative_size != ''
                GROUP BY creative_size
                ORDER BY SUM(COALESCE(reached_queries, 0)) DESC
            """, (cutoff_date,))

            for row in cursor.fetchall():
                size_str = row[0]
                sizes[size_str] = {
                    "reached_queries": row[1] or 0,
                    "impressions": row[2] or 0,
                    "clicks": row[3] or 0,
                    "spend_micros": row[4] or 0,
                }

        finally:
            conn.close()

        return sizes

    def analyze_coverage(self, days: int = 7) -> CoverageReport:
        """
        Analyze size coverage: what you can serve vs. what you're receiving.

        Args:
            days: Number of days of traffic to analyze

        Returns:
            CoverageReport with complete analysis
        """
        inventory = self.get_inventory_sizes()
        traffic = self.get_traffic_sizes(days)

        inventory_size_set = set(inventory.keys())
        traffic_size_set = set(traffic.keys())

        # Analyze each size in traffic
        coverage_results: List[SizeCoverageResult] = []

        for size_str, data in traffic.items():
            reached = data["reached_queries"]
            impressions = data["impressions"]
            efficiency = (impressions / reached * 100) if reached > 0 else 0

            can_serve = size_str in inventory_size_set
            creative_count = inventory[size_str].creative_count if can_serve else 0
            in_google_list = size_str in GOOGLE_AVAILABLE_SIZES

            # Determine recommendation
            if can_serve:
                recommendation = "INCLUDE"
            elif in_google_list and reached > 1000:
                recommendation = "CREATE_CREATIVE"  # High volume, worth creating
            elif in_google_list:
                recommendation = "CONSIDER"
            else:
                recommendation = "IGNORE"  # Not in Google's list, can't filter anyway

            coverage_results.append(SizeCoverageResult(
                size=size_str,
                reached_queries=reached,
                impressions=impressions,
                you_can_serve=can_serve,
                creative_count=creative_count,
                in_google_list=in_google_list,
                efficiency_pct=efficiency,
                recommendation=recommendation,
            ))

        # Sort by reached queries
        coverage_results.sort(key=lambda x: x.reached_queries, reverse=True)

        # Calculate totals
        total_reached = sum(r.reached_queries for r in coverage_results)
        servable_reached = sum(r.reached_queries for r in coverage_results if r.you_can_serve)
        waste_queries = total_reached - servable_reached
        match_rate = (servable_reached / total_reached * 100) if total_reached > 0 else 0

        # Generate include list (only sizes you have AND are in Google's list)
        include_list = sorted([
            size for size in inventory_size_set
            if size in GOOGLE_AVAILABLE_SIZES
        ])

        # Find opportunities (high-volume sizes you don't have but could filter)
        opportunities = [
            {
                "size": r.size,
                "reached_queries": r.reached_queries,
                "priority": "HIGH" if r.reached_queries > 10000 else "MEDIUM",
            }
            for r in coverage_results
            if not r.you_can_serve and r.in_google_list and r.reached_queries > 1000
        ][:10]

        return CoverageReport(
            total_creatives=sum(info.creative_count for info in inventory.values()),
            sizes_in_inventory=len(inventory),
            sizes_in_traffic=len(traffic),
            sizes_you_can_serve=len([r for r in coverage_results if r.you_can_serve]),
            sizes_you_cannot_serve=len([r for r in coverage_results if not r.you_can_serve]),
            total_reached_queries=total_reached,
            servable_reached_queries=servable_reached,
            waste_queries=waste_queries,
            match_rate_pct=match_rate,
            inventory_sizes=sorted(inventory.values(), key=lambda x: x.creative_count, reverse=True),
            coverage_results=coverage_results,
            include_list=include_list,
            opportunities=opportunities,
            analysis_days=days,
            generated_at=datetime.now().isoformat(),
        )

    def generate_report(self, days: int = 7) -> str:
        """Generate human-readable size coverage report (printout)."""
        report = self.analyze_coverage(days)

        lines = []
        lines.append("=" * 80)
        lines.append("SIZE COVERAGE ANALYSIS REPORT")
        lines.append("=" * 80)
        lines.append(f"Generated: {report.generated_at}")
        lines.append(f"Analysis Period: Last {report.analysis_days} days")
        lines.append("")

        # Executive Summary
        lines.append("EXECUTIVE SUMMARY")
        lines.append("-" * 40)
        lines.append(f"Sizes in your inventory:       {report.sizes_in_inventory}")
        lines.append(f"Sizes in traffic (from CSV):   {report.sizes_in_traffic}")
        lines.append(f"Sizes you can serve:           {report.sizes_you_can_serve}")
        lines.append(f"Sizes you cannot serve:        {report.sizes_you_cannot_serve}")
        lines.append("")
        lines.append(f"Total Reached Queries:    {report.total_reached_queries:>15,}")
        lines.append(f"Servable Queries:         {report.servable_reached_queries:>15,}")
        lines.append(f"Waste (can't serve):      {report.waste_queries:>15,}")
        lines.append(f"Match Rate:               {report.match_rate_pct:>14.1f}%")
        lines.append("")

        if report.match_rate_pct < 80:
            lines.append(f"WARNING: {100 - report.match_rate_pct:.1f}% of your QPS is for sizes you can't serve!")
        else:
            lines.append(f"Good match rate - {report.match_rate_pct:.1f}% of QPS is servable")
        lines.append("")

        # Your inventory
        lines.append("=" * 80)
        lines.append("YOUR CREATIVE INVENTORY")
        lines.append("=" * 80)
        lines.append("")
        lines.append(f"Total creatives: {report.total_creatives}")
        lines.append("")

        for info in report.inventory_sizes[:15]:
            formats_str = ", ".join(f"{k}:{v}" for k, v in info.formats.items())
            google_marker = "[Y]" if info.size in GOOGLE_AVAILABLE_SIZES else "[N]"
            lines.append(f"  {google_marker} {info.size:<20} {info.creative_count:>5} creatives ({formats_str})")

        if len(report.inventory_sizes) > 15:
            lines.append(f"  ... and {len(report.inventory_sizes) - 15} more sizes")
        lines.append("")
        lines.append("  [Y] = In Google's pretargeting list  [N] = Not filterable")
        lines.append("")

        # Sizes you CAN serve (in traffic)
        if report.coverage_results:
            servable = [r for r in report.coverage_results if r.you_can_serve]

            lines.append("=" * 80)
            lines.append("SIZES YOU CAN SERVE (from traffic)")
            lines.append("=" * 80)
            lines.append("")
            lines.append(f"{'Size':<20} {'Reached':>12} {'Impressions':>12} {'Eff%':>8} {'Creatives':>10}")
            lines.append("-" * 65)

            for r in servable[:15]:
                google_marker = "[Y]" if r.in_google_list else "[N]"
                lines.append(
                    f"{google_marker} {r.size:<18} {r.reached_queries:>12,} {r.impressions:>12,} "
                    f"{r.efficiency_pct:>7.1f}% {r.creative_count:>10}"
                )
            lines.append("")

            # Sizes you CANNOT serve
            waste = [r for r in report.coverage_results if not r.you_can_serve]

            if waste:
                lines.append("=" * 80)
                lines.append("SIZES YOU CANNOT SERVE (WASTE QPS)")
                lines.append("=" * 80)
                lines.append("")
                lines.append(f"{'Size':<20} {'Reached':>12} {'In Google List':>15} {'Recommendation'}")
                lines.append("-" * 65)

                for r in waste[:15]:
                    google = "Yes" if r.in_google_list else "No"
                    lines.append(f"  {r.size:<18} {r.reached_queries:>12,} {google:>15} {r.recommendation}")

                if len(waste) > 15:
                    lines.append(f"  ... and {len(waste) - 15} more sizes")
                lines.append("")

        # Recommended include list
        lines.append("=" * 80)
        lines.append("RECOMMENDED INCLUDE LIST FOR PRETARGETING")
        lines.append("=" * 80)
        lines.append("")

        if report.include_list:
            lines.append("If you set pretargeting to INCLUDE only these sizes,")
            lines.append("you will eliminate waste from sizes you can't serve.")
            lines.append("")
            lines.append("WARNING: Once you add ANY size, all unlisted sizes are EXCLUDED!")
            lines.append("Double-check this list carefully before applying!")
            lines.append("")
            lines.append("SIZES TO INCLUDE:")
            lines.append("")

            # Format as rows of 5 for easy copy-paste
            for i in range(0, len(report.include_list), 5):
                chunk = report.include_list[i:i+5]
                lines.append("  " + ", ".join(chunk))

            lines.append("")
            lines.append("TO IMPLEMENT:")
            lines.append("  1. Go to Authorized Buyers UI")
            lines.append("  2. Navigate to Bidder Settings -> Pretargeting")
            lines.append("  3. Edit the config you want to modify")
            lines.append("  4. Under 'Creative dimensions', add the sizes above")
            lines.append("  5. Click Save")
            lines.append("  6. Monitor traffic for 24-48 hours after applying")
        else:
            lines.append("No sizes found to include. Check that creatives are imported.")
        lines.append("")

        # Opportunities
        if report.opportunities:
            lines.append("=" * 80)
            lines.append("OPPORTUNITIES: High-volume sizes worth creating creatives for")
            lines.append("=" * 80)
            lines.append("")
            lines.append(f"{'Size':<20} {'Daily QPS':>15} {'Priority'}")
            lines.append("-" * 45)

            for opp in report.opportunities:
                lines.append(f"  {opp['size']:<18} {opp['reached_queries']:>15,} {opp['priority']}")

            lines.append("")
            lines.append("ACTION: Brief creative team to produce these sizes")

        lines.append("")
        lines.append("=" * 80)
        lines.append("END OF SIZE COVERAGE REPORT")
        lines.append("=" * 80)

        return "\n".join(lines)


if __name__ == "__main__":
    import sys

    days = 7
    if "--days" in sys.argv:
        idx = sys.argv.index("--days")
        if idx + 1 < len(sys.argv):
            days = int(sys.argv[idx + 1])

    analyzer = SizeCoverageAnalyzer()
    print(analyzer.generate_report(days))
