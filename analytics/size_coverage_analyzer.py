"""
Analyze size coverage: what sizes do we receive vs what sizes do we have?

This is THE core Cat-Scan analysis - identifying QPS waste from size mismatches.
"""

from dataclasses import dataclass
from typing import Optional
import os

import psycopg
from psycopg.rows import dict_row


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

    def __init__(self, db_path_or_dsn: str):
        # Accept either path (ignored) or use env var for Postgres DSN
        self.dsn = os.getenv("POSTGRES_SERVING_DSN", db_path_or_dsn)

    def analyze(
        self,
        days: int = 7,
        billing_id: Optional[str] = None,
        billing_ids: Optional[list[str]] = None,
        buyer_id: Optional[str] = None,
    ) -> SizeCoverageSummary:
        """
        Compare sizes in traffic against creative inventory.

        Args:
            days: Number of days to analyze.
            billing_id: Optional billing account ID to filter by. If provided,
                       only analyzes traffic for that specific account.

        Returns:
            Summary of size coverage with specific gaps.
        """
        conn = psycopg.connect(self.dsn, row_factory=dict_row)

        # Get all sizes we have approved creatives for
        # Normalize sizes to just WxH format (strip descriptions like "(Mobile Banner)")
        creative_sizes = {}  # size -> {format, count}
        creative_params = []
        creative_filter = ""
        if buyer_id:
            creative_filter = " AND buyer_id = %s"
            creative_params.append(buyer_id)

        cursor = conn.execute(f"""
            SELECT
                CASE
                    WHEN width IS NOT NULL AND height IS NOT NULL AND width > 0 AND height > 0
                    THEN CAST(width AS TEXT) || 'x' || CAST(height AS TEXT)
                    ELSE
                        CASE
                            WHEN canonical_size LIKE '%%(%%'
                            THEN TRIM(SUBSTRING(canonical_size FROM 1 FOR POSITION('(' IN canonical_size) - 1))
                            ELSE canonical_size
                        END
                END as normalized_size,
                format,
                COUNT(*) as count
            FROM creatives
            WHERE approval_status = 'APPROVED'
              AND (
                  (width IS NOT NULL AND height IS NOT NULL AND width > 0 AND height > 0)
                  OR (canonical_size IS NOT NULL AND canonical_size != '')
              ){creative_filter}
            GROUP BY 1, 2
        """, creative_params)
        for row in cursor:
            size = row['normalized_size']
            if not size or size.strip() == '':
                continue
            size = size.strip()
            key = f"{size}|{row['format']}"
            creative_sizes[key] = {
                'size': size,
                'format': row['format'],
                'creative_count': row['count'],
            }

        # Also get creatives without canonical_size (like VIDEO) by format
        cursor = conn.execute(f"""
            SELECT
                format,
                COUNT(*) as count
            FROM creatives
            WHERE approval_status = 'APPROVED'
              AND (canonical_size IS NULL OR canonical_size = ''){creative_filter}
            GROUP BY format
        """, creative_params)
        for row in cursor:
            key = f"(any)|{row['format']}"
            creative_sizes[key] = {
                'size': '(any)',
                'format': row['format'],
                'creative_count': row['count'],
            }

        # Get traffic by size and format from rtb_daily
        # This is the actual imported CSV data
        traffic_by_size = {}

        # Build query with optional billing_id and buyer filters
        billing_filter = ""
        params = [days]
        if billing_ids:
            placeholders = ",".join("%s" for _ in billing_ids)
            billing_filter = f" AND billing_id IN ({placeholders})"
            params.extend(billing_ids)
        elif billing_id:
            billing_filter = " AND billing_id = %s"
            params.append(billing_id)
        buyer_filter = ""
        if buyer_id:
            buyer_filter = " AND buyer_account_id = %s"
            params.append(buyer_id)

        cursor = conn.execute(f"""
            SELECT
                creative_size as size,
                COALESCE(creative_format, 'BANNER') as format,
                SUM(COALESCE(reached_queries, 0)) as total_reached,
                SUM(COALESCE(impressions, 0)) as total_impressions,
                SUM(COALESCE(spend_micros, 0)) / 1000000.0 as spend_usd,
                SUM(COALESCE(clicks, 0)) as clicks
            FROM rtb_daily
            WHERE metric_date >= CURRENT_DATE - (%s || ' days')::interval
              AND creative_size IS NOT NULL
              AND creative_size != ''
            {billing_filter}
            {buyer_filter}
            GROUP BY creative_size, COALESCE(creative_format, 'BANNER')
            ORDER BY total_impressions DESC
        """, params)

        for row in cursor:
            key = f"{row['size']}|{row['format']}"
            traffic_by_size[key] = {
                'size': row['size'],
                'format': row['format'],
                'reached_queries': row['total_reached'],
                'impressions': row['total_impressions'],
                'spend_usd': row['spend_usd'],
                'clicks': row['clicks'],
            }

        creative_counts_from_traffic = {}
        cursor = conn.execute(f"""
            SELECT
                creative_size as size,
                COALESCE(creative_format, 'BANNER') as format,
                COUNT(DISTINCT creative_id) as creative_count
            FROM rtb_daily
            WHERE metric_date >= CURRENT_DATE - (%s || ' days')::interval
              AND creative_size IS NOT NULL
              AND creative_size != ''
            {billing_filter}
            {buyer_filter}
            GROUP BY creative_size, COALESCE(creative_format, 'BANNER')
        """, params)
        for row in cursor:
            key = f"{row['size']}|{row['format']}"
            creative_counts_from_traffic[key] = row['creative_count']

        # Calculate coverage using reached_queries (the actual QPS metric)
        total_reached = sum(t['reached_queries'] for t in traffic_by_size.values())
        total_impressions = sum(t['impressions'] for t in traffic_by_size.values())

        covered_sizes = []
        gaps = []

        # Build a lookup for just the size part (without format) for more flexible matching
        creative_size_only = {size.split('|')[0] for size in creative_sizes.keys()}

        # Check each size in traffic
        for key, traffic in traffic_by_size.items():
            size_only = traffic['size']

            # Check if we have this size (try exact key first, then just size)
            # IMPORTANT: If impressions > 0, we're serving this size (HTML5/video are flexible)
            has_creative = key in creative_sizes or size_only in creative_size_only or traffic['impressions'] > 0

            if has_creative:
                # We have creatives for this size
                creative_count = 0
                if key in creative_sizes:
                    creative_count = creative_sizes[key]['creative_count']
                else:
                    # Sum up all creatives for this size across formats
                    creative_count = sum(
                        v['creative_count'] for k, v in creative_sizes.items()
                        if k.startswith(f"{size_only}|")
                    )
                if creative_count == 0:
                    creative_count = creative_counts_from_traffic.get(key, 0)

                covered_sizes.append({
                    'size': traffic['size'],
                    'format': traffic['format'],
                    'reached_queries': traffic['reached_queries'],
                    'impressions': traffic['impressions'],
                    'spend_usd': traffic['spend_usd'],
                    'creative_count': creative_count,
                    'ctr': (traffic['clicks'] / traffic['impressions'] * 100) if traffic['impressions'] > 0 else 0,
                })
            else:
                # This is a gap - traffic but no creatives
                daily_queries = traffic['reached_queries'] / max(days, 1)
                pct_of_total = (traffic['reached_queries'] / total_reached * 100) if total_reached > 0 else 0

                # Recommend based on daily query volume
                if daily_queries > 10000:
                    recommendation = "BLOCK_IN_PRETARGETING"
                elif daily_queries > 1000:
                    recommendation = "CONSIDER_ADDING_CREATIVE"
                else:
                    recommendation = "LOW_PRIORITY"

                gaps.append(SizeCoverageGap(
                    size=traffic['size'],
                    format=traffic['format'],
                    queries_received=traffic['reached_queries'],
                    impressions_won=traffic['impressions'],
                    estimated_daily_queries=daily_queries,
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

        # Calculate summary stats based on reached_queries (QPS metric)
        covered_queries = total_reached - sum(g.queries_received for g in gaps)
        coverage_rate = (covered_queries / total_reached * 100) if total_reached > 0 else 0
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
