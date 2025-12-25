"""
Analyze size coverage: what sizes do we receive vs what sizes do we have?

This is THE core Cat-Scan analysis - identifying QPS waste from size mismatches.
"""

from dataclasses import dataclass
from typing import Optional
import sqlite3


@dataclass
class SizeCoverageGap:
    """A size we receive traffic for but can't bid on."""
    size: str
    format: str
    queries_received: int          # From rtb_daily.reached_queries or proxy
    impressions_won: int           # From performance_metrics.impressions
    estimated_daily_queries: int
    percent_of_total_traffic: float
    recommendation: str            # "BLOCK_IN_PRETARGETING", "CONSIDER_ADDING_CREATIVE", "LOW_PRIORITY"


@dataclass
class SizeCoverageSummary:
    """Overall size coverage analysis."""
    total_sizes_in_traffic: int
    sizes_with_creatives: int
    sizes_without_creatives: int
    coverage_rate: float           # % of traffic sizes we can bid on
    wasted_queries_daily: int      # Queries for sizes we can't bid on
    wasted_qps: float
    gaps: list[SizeCoverageGap]
    covered_sizes: list[dict]      # Sizes we have creatives for with their stats


class SizeCoverageAnalyzer:
    """Analyze size-based QPS waste."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def analyze(self, days: int = 7, billing_id: Optional[str] = None) -> SizeCoverageSummary:
        """
        Compare sizes in traffic against creative inventory.

        Args:
            days: Number of days to analyze.
            billing_id: Optional billing account ID to filter by. If provided,
                       only analyzes traffic for that specific account.

        Returns:
            Summary of size coverage with specific gaps.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        # Get all sizes we have approved creatives for
        creative_sizes = {}  # size -> {format, count}
        cursor = conn.execute("""
            SELECT
                canonical_size,
                format,
                COUNT(*) as count
            FROM creatives
            WHERE approval_status = 'APPROVED'
              AND canonical_size IS NOT NULL
              AND canonical_size != ''
            GROUP BY canonical_size, format
        """)
        for row in cursor:
            key = f"{row['canonical_size']}|{row['format']}"
            creative_sizes[key] = {
                'size': row['canonical_size'],
                'format': row['format'],
                'creative_count': row['count'],
            }

        # Also get creatives without canonical_size (like VIDEO) by format
        cursor = conn.execute("""
            SELECT
                format,
                COUNT(*) as count
            FROM creatives
            WHERE approval_status = 'APPROVED'
              AND (canonical_size IS NULL OR canonical_size = '')
            GROUP BY format
        """)
        for row in cursor:
            key = f"(any)|{row['format']}"
            creative_sizes[key] = {
                'size': '(any)',
                'format': row['format'],
                'creative_count': row['count'],
            }

        # Get traffic by size and format from performance_metrics
        # Since reached_queries is empty, use impressions as proxy
        traffic_by_size = {}

        # Build query with optional billing_id filter
        billing_filter = ""
        params = []
        if billing_id:
            billing_filter = " AND pm.billing_id = ?"
            params.append(billing_id)

        cursor = conn.execute(f"""
            SELECT
                COALESCE(c.canonical_size, '(any)') as size,
                c.format,
                SUM(pm.impressions) as total_impressions,
                SUM(pm.spend_micros) / 1000000.0 as spend_usd,
                SUM(pm.clicks) as clicks
            FROM performance_metrics pm
            JOIN creatives c ON pm.creative_id = c.id
            WHERE pm.metric_date >= date('now', '-{days} days')
            {billing_filter}
            GROUP BY COALESCE(c.canonical_size, '(any)'), c.format
            ORDER BY total_impressions DESC
        """, params)

        for row in cursor:
            key = f"{row['size']}|{row['format']}"
            traffic_by_size[key] = {
                'size': row['size'],
                'format': row['format'],
                'impressions': row['total_impressions'],
                'spend_usd': row['spend_usd'],
                'clicks': row['clicks'],
            }

        # Calculate coverage
        total_impressions = sum(t['impressions'] for t in traffic_by_size.values())

        covered_sizes = []
        gaps = []

        # Check each size in traffic
        for key, traffic in traffic_by_size.items():
            if key in creative_sizes:
                # We have creatives for this size
                covered_sizes.append({
                    'size': traffic['size'],
                    'format': traffic['format'],
                    'impressions': traffic['impressions'],
                    'spend_usd': traffic['spend_usd'],
                    'creative_count': creative_sizes[key]['creative_count'],
                    'ctr': (traffic['clicks'] / traffic['impressions'] * 100) if traffic['impressions'] > 0 else 0,
                })
            else:
                # This is a gap - traffic but no creatives
                daily_imps = traffic['impressions'] // max(days, 1)
                pct_of_total = (traffic['impressions'] / total_impressions * 100) if total_impressions > 0 else 0

                # Recommend based on volume
                if daily_imps > 10000:
                    recommendation = "BLOCK_IN_PRETARGETING"
                elif daily_imps > 1000:
                    recommendation = "CONSIDER_ADDING_CREATIVE"
                else:
                    recommendation = "LOW_PRIORITY"

                gaps.append(SizeCoverageGap(
                    size=traffic['size'],
                    format=traffic['format'],
                    queries_received=traffic['impressions'],  # Using impressions as proxy
                    impressions_won=traffic['impressions'],
                    estimated_daily_queries=daily_imps,
                    percent_of_total_traffic=pct_of_total,
                    recommendation=recommendation,
                ))

        # Check for sizes we have creatives for but no traffic (potential opportunities)
        for key, creative in creative_sizes.items():
            if key not in traffic_by_size:
                # We have creatives but no traffic for this size
                # This could mean we should request this size in pretargeting
                pass  # Track separately if needed

        # Sort gaps by volume descending
        gaps.sort(key=lambda g: g.queries_received, reverse=True)
        covered_sizes.sort(key=lambda s: s['impressions'], reverse=True)

        # Calculate summary stats
        covered_impressions = sum(s['impressions'] for s in covered_sizes)
        coverage_rate = (covered_impressions / total_impressions * 100) if total_impressions > 0 else 0
        wasted_daily = sum(g.estimated_daily_queries for g in gaps)

        conn.close()

        return SizeCoverageSummary(
            total_sizes_in_traffic=len(traffic_by_size),
            sizes_with_creatives=len(covered_sizes),
            sizes_without_creatives=len(gaps),
            coverage_rate=coverage_rate,
            wasted_queries_daily=wasted_daily,
            wasted_qps=wasted_daily / 86400,
            gaps=gaps,
            covered_sizes=covered_sizes,
        )
