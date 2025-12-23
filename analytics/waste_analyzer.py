"""Waste analysis engine for RTB traffic.

This module provides the WasteAnalyzer class that compares RTB bid requests
against creative inventory to identify bandwidth waste and generate
actionable recommendations.

Example:
    >>> from analytics import WasteAnalyzer
    >>> from storage import SQLiteStore
    >>>
    >>> store = SQLiteStore()
    >>> await store.initialize()
    >>>
    >>> analyzer = WasteAnalyzer(store)
    >>> report = await analyzer.analyze_waste(buyer_id="456", days=7)
    >>>
    >>> print(f"Waste: {report.waste_percentage}%")
    >>> for gap in report.size_gaps[:5]:
    ...     print(f"  {gap.canonical_size}: {gap.recommendation}")
"""

import logging
import re
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from analytics.waste_models import SizeCoverage, SizeGap, TrafficRecord, WasteReport, ProblemFormat
from utils.size_normalization import (
    IAB_STANDARD_SIZES,
    canonical_size,
    canonical_size_with_tolerance,
    get_size_category,
)

if TYPE_CHECKING:
    from storage.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)

# Constants for recommendations
HIGH_VOLUME_THRESHOLD = 10000  # requests/day
MEDIUM_VOLUME_THRESHOLD = 1000  # requests/day
SECONDS_PER_DAY = 86400

# Estimated cost per 1000 requests (CPM) for waste calculation
# This is a rough estimate for bandwidth/processing costs
ESTIMATED_COST_PER_1000 = 0.002  # $0.002 per 1000 requests


class WasteAnalyzer:
    """Analyze RTB traffic waste by comparing requests vs creative inventory.

    This analyzer compares what sizes publishers request via bid requests
    against what creatives you have available, identifying gaps where
    you're receiving traffic but cannot bid.

    Attributes:
        store: SQLiteStore instance for database access.
    """

    def __init__(self, db_store: "SQLiteStore"):
        """Initialize the waste analyzer.

        Args:
            db_store: SQLiteStore instance for accessing creative inventory
                and traffic data.
        """
        self.store = db_store

    async def analyze_waste(
        self,
        buyer_id: Optional[str] = None,
        days: int = 7,
    ) -> WasteReport:
        """Perform complete waste analysis comparing requests vs inventory.

        This is the main analysis method that:
        1. Fetches creative inventory grouped by canonical size
        2. Fetches RTB traffic data grouped by size
        3. Identifies gaps (sizes with requests but no creatives)
        4. Calculates waste metrics and generates recommendations

        Args:
            buyer_id: Optional buyer seat ID to filter analysis.
            days: Number of days of traffic data to analyze.

        Returns:
            WasteReport with complete analysis results.

        Example:
            >>> report = await analyzer.analyze_waste(buyer_id="456")
            >>> print(f"Found {len(report.size_gaps)} size gaps")
        """
        logger.info(f"Starting waste analysis for buyer_id={buyer_id}, days={days}")

        # Get creative inventory by size
        inventory = await self._get_inventory_by_size(buyer_id)
        logger.debug(f"Found {len(inventory)} unique sizes in inventory")

        # Get traffic data
        traffic = await self._get_traffic_by_size(buyer_id, days)
        logger.debug(f"Found {len(traffic)} unique sizes in traffic")

        # Calculate totals
        total_requests = sum(t["count"] for t in traffic.values())

        # Find gaps and calculate coverage
        size_gaps: List[SizeGap] = []
        size_coverage: List[SizeCoverage] = []
        total_waste_requests = 0

        # Process all sizes (from both traffic and inventory)
        all_sizes = set(traffic.keys()) | set(inventory.keys())

        for size in all_sizes:
            traffic_data = traffic.get(size, {"count": 0, "raw_sizes": set()})
            inv_data = inventory.get(size, {"count": 0, "formats": {}})

            request_count = traffic_data["count"]
            creative_count = inv_data["count"]

            # Determine coverage status
            if creative_count == 0 and request_count > 0:
                coverage_status = "none"
                total_waste_requests += request_count
            elif creative_count > 0 and request_count == 0:
                coverage_status = "excess"  # Have creatives but no traffic
            elif creative_count == 0 and request_count == 0:
                continue  # Skip sizes with no data
            elif creative_count < 3 and request_count > MEDIUM_VOLUME_THRESHOLD:
                coverage_status = "low"
            else:
                coverage_status = "good"

            # Create coverage record
            size_coverage.append(
                SizeCoverage(
                    canonical_size=size,
                    creative_count=creative_count,
                    request_count=request_count,
                    coverage_status=coverage_status,
                    formats=inv_data.get("formats", {}),
                )
            )

            # Create gap record if no creatives
            if creative_count == 0 and request_count > 0:
                gap = self._create_size_gap(
                    canonical_size=size,
                    request_count=request_count,
                    creative_count=creative_count,
                    total_requests=total_requests,
                    days=days,
                )
                size_gaps.append(gap)

        # Sort gaps by impact (request count descending)
        size_gaps.sort(key=lambda g: g.request_count, reverse=True)

        # Sort coverage by request count descending
        size_coverage.sort(key=lambda c: c.request_count, reverse=True)

        # Calculate totals
        waste_percentage = (
            (total_waste_requests / total_requests * 100)
            if total_requests > 0
            else 0.0
        )
        potential_savings_qps = sum(g.estimated_qps for g in size_gaps)
        potential_savings_usd = self._estimate_monthly_savings(total_waste_requests, days)

        # Generate recommendations summary
        recommendations_summary = self._generate_recommendations_summary(size_gaps)

        return WasteReport(
            buyer_id=buyer_id,
            total_requests=total_requests,
            total_waste_requests=total_waste_requests,
            waste_percentage=waste_percentage,
            size_gaps=size_gaps,
            size_coverage=size_coverage,
            potential_savings_qps=potential_savings_qps,
            potential_savings_usd=potential_savings_usd,
            analysis_period_days=days,
            generated_at=datetime.now(timezone.utc).isoformat(),
            recommendations_summary=recommendations_summary,
        )

    async def get_size_gaps(
        self,
        buyer_id: Optional[str] = None,
        days: int = 7,
        min_requests: int = 100,
    ) -> List[SizeGap]:
        """Get sizes with traffic but no creatives.

        Convenience method to get just the gap data without full report.

        Args:
            buyer_id: Optional buyer seat ID to filter.
            days: Number of days of traffic to analyze.
            min_requests: Minimum request count to include.

        Returns:
            List of SizeGap objects sorted by request count.
        """
        report = await self.analyze_waste(buyer_id, days)
        return [g for g in report.size_gaps if g.request_count >= min_requests]

    async def get_size_coverage(
        self,
        buyer_id: Optional[str] = None,
    ) -> Dict[str, dict]:
        """Get creative coverage by size with traffic correlation.

        Returns a dictionary mapping sizes to their coverage status,
        useful for quick lookups and dashboard display.

        Args:
            buyer_id: Optional buyer seat ID to filter.

        Returns:
            Dictionary with size as key and coverage data as value.

        Example:
            >>> coverage = await analyzer.get_size_coverage()
            >>> coverage["300x250"]
            {"creatives": 45, "requests": 45000, "coverage": "good"}
        """
        report = await self.analyze_waste(buyer_id, days=7)

        return {
            c.canonical_size: {
                "creatives": c.creative_count,
                "requests": c.request_count,
                "coverage": c.coverage_status,
                "formats": c.formats,
            }
            for c in report.size_coverage
        }

    async def _get_inventory_by_size(
        self,
        buyer_id: Optional[str] = None,
    ) -> Dict[str, dict]:
        """Get creative inventory grouped by canonical size.

        Args:
            buyer_id: Optional buyer seat ID to filter.

        Returns:
            Dictionary mapping canonical_size to count and format breakdown.
        """
        # Get all creatives
        creatives = await self.store.list_creatives(
            buyer_id=buyer_id,
            limit=10000,
        )

        inventory: Dict[str, dict] = {}

        for creative in creatives:
            size = creative.canonical_size
            if not size:
                continue

            if size not in inventory:
                inventory[size] = {"count": 0, "formats": {}}

            inventory[size]["count"] += 1

            # Track format breakdown
            fmt = creative.format or "UNKNOWN"
            inventory[size]["formats"][fmt] = inventory[size]["formats"].get(fmt, 0) + 1

        return inventory

    async def _get_traffic_by_size(
        self,
        buyer_id: Optional[str] = None,
        days: int = 7,
    ) -> Dict[str, dict]:
        """Get RTB traffic data grouped by canonical size.

        Args:
            buyer_id: Optional buyer seat ID to filter.
            days: Number of days of traffic to include.

        Returns:
            Dictionary mapping canonical_size to request count and raw sizes.
        """
        # Get traffic data from database
        traffic_data = await self.store.get_traffic_data(buyer_id=buyer_id, days=days)

        traffic: Dict[str, dict] = {}

        for record in traffic_data:
            size = record.get("canonical_size")
            if not size:
                continue

            if size not in traffic:
                traffic[size] = {"count": 0, "raw_sizes": set()}

            traffic[size]["count"] += record.get("request_count", 0)
            raw_size = record.get("raw_size")
            if raw_size:
                traffic[size]["raw_sizes"].add(raw_size)

        return traffic

    def _create_size_gap(
        self,
        canonical_size: str,
        request_count: int,
        creative_count: int,
        total_requests: int,
        days: int,
    ) -> SizeGap:
        """Create a SizeGap with recommendation.

        Args:
            canonical_size: The normalized size category.
            request_count: Number of requests for this size.
            creative_count: Number of creatives (should be 0 for gaps).
            total_requests: Total requests for percentage calculation.
            days: Analysis period for QPS calculation.

        Returns:
            Configured SizeGap object with recommendation.
        """
        # Calculate metrics
        daily_requests = request_count / days if days > 0 else request_count
        estimated_qps = daily_requests / SECONDS_PER_DAY
        waste_pct = (request_count / total_requests * 100) if total_requests > 0 else 0.0

        # Generate recommendation
        recommendation, detail, closest_iab = self._generate_recommendation(
            canonical_size=canonical_size,
            daily_requests=daily_requests,
        )

        # Estimate savings
        potential_savings = self._estimate_monthly_savings(request_count, days)

        return SizeGap(
            canonical_size=canonical_size,
            request_count=request_count,
            creative_count=creative_count,
            estimated_qps=estimated_qps,
            estimated_waste_pct=waste_pct,
            recommendation=recommendation,
            recommendation_detail=detail,
            potential_savings_usd=potential_savings,
            closest_iab_size=closest_iab,
        )

    def _generate_recommendation(
        self,
        canonical_size: str,
        daily_requests: float,
    ) -> Tuple[str, str, Optional[str]]:
        """Generate actionable recommendation for a size gap.

        Rules:
        - High volume (>10k/day) + zero creatives → "Block in pretargeting"
        - Medium volume (1k-10k/day) + zero creatives → "Consider adding creative"
        - Low volume (<1k/day) → "Monitor"
        - Non-standard size close to IAB → "Use flexible HTML5 creative"

        Args:
            canonical_size: The canonical size string.
            daily_requests: Average daily request volume.

        Returns:
            Tuple of (recommendation, detail, closest_iab_size).
        """
        category = get_size_category(canonical_size)
        closest_iab = self._find_closest_iab_size(canonical_size)

        # Check if this is a near-IAB size
        is_near_iab = closest_iab is not None and category == "Non-Standard"

        if daily_requests >= HIGH_VOLUME_THRESHOLD:
            if is_near_iab:
                return (
                    "Use Flexible",
                    f"High volume ({int(daily_requests):,}/day). Use flexible HTML5 creative "
                    f"that can render at nearby IAB size {closest_iab}",
                    closest_iab,
                )
            else:
                qps = daily_requests / SECONDS_PER_DAY
                return (
                    "Block",
                    f"Block in pretargeting config. Saving {qps:.1f} QPS "
                    f"({int(daily_requests):,} requests/day)",
                    closest_iab,
                )

        elif daily_requests >= MEDIUM_VOLUME_THRESHOLD:
            if is_near_iab:
                return (
                    "Use Flexible",
                    f"Medium volume ({int(daily_requests):,}/day). Consider flexible HTML5 "
                    f"creative for {closest_iab}",
                    closest_iab,
                )
            else:
                return (
                    "Add Creative",
                    f"Consider adding creative for this size ({int(daily_requests):,}/day)",
                    closest_iab,
                )

        else:
            return (
                "Monitor",
                f"Low volume ({int(daily_requests):,}/day). Monitor for growth",
                closest_iab,
            )

    def _find_closest_iab_size(
        self,
        canonical_size: str,
        tolerance: int = 5,
    ) -> Optional[str]:
        """Find the closest IAB standard size to a non-standard size.

        Args:
            canonical_size: The canonical size string (e.g., "Non-Standard (301x250)").
            tolerance: Maximum pixel difference to consider "close".

        Returns:
            Closest IAB size string if within tolerance, None otherwise.
        """
        # Extract dimensions from canonical size
        match = re.search(r"\((\d+)x(\d+)\)", canonical_size)
        if not match:
            return None

        width, height = int(match.group(1)), int(match.group(2))

        # Check each IAB standard
        for (iab_w, iab_h), iab_name in IAB_STANDARD_SIZES.items():
            if abs(width - iab_w) <= tolerance and abs(height - iab_h) <= tolerance:
                return iab_name

        return None

    def _estimate_monthly_savings(
        self,
        request_count: int,
        days: int,
    ) -> float:
        """Estimate monthly cost savings from blocking waste traffic.

        This is a rough estimate based on:
        - Bandwidth costs per request
        - Processing/compute costs
        - Does NOT include opportunity cost of missing bids

        Args:
            request_count: Number of wasted requests in period.
            days: Number of days in the analysis period.

        Returns:
            Estimated monthly savings in USD.
        """
        if days <= 0:
            return 0.0

        daily_requests = request_count / days
        monthly_requests = daily_requests * 30

        # Cost per 1000 requests
        savings = (monthly_requests / 1000) * ESTIMATED_COST_PER_1000

        return round(savings, 2)

    def _generate_recommendations_summary(
        self,
        size_gaps: List[SizeGap],
    ) -> dict:
        """Generate high-level recommendations summary.

        Args:
            size_gaps: List of size gaps from analysis.

        Returns:
            Dictionary with summary counts by recommendation type.
        """
        summary = {
            "block": 0,
            "add_creative": 0,
            "use_flexible": 0,
            "monitor": 0,
            "top_savings_size": None,
            "top_savings_qps": 0.0,
        }

        for gap in size_gaps:
            rec = gap.recommendation.lower().replace(" ", "_")
            if rec in summary:
                summary[rec] += 1

            # Track top savings
            if gap.estimated_qps > summary["top_savings_qps"]:
                summary["top_savings_qps"] = gap.estimated_qps
                summary["top_savings_size"] = gap.canonical_size

        return summary

    async def detect_problem_formats(
        self,
        buyer_id: Optional[str] = None,
        days: int = 7,
        size_tolerance: int = 5,
    ) -> List[ProblemFormat]:
        """Detect creatives with problems that hurt QPS efficiency.

        Phase 22: Problem format detection identifies creatives that should
        be reviewed or removed.

        Problem types:
        - zero_bids: Has reached_queries but no impressions
        - non_standard: Size doesn't match any IAB standard (even with tolerance)
        - low_bid_rate: impressions / reached_queries < 1%
        - disapproved: approval_status != 'APPROVED'

        Args:
            buyer_id: Optional buyer seat ID to filter.
            days: Number of days of performance data to analyze.
            size_tolerance: Pixel tolerance for size matching (default 5).

        Returns:
            List of ProblemFormat objects sorted by severity.
        """
        problems: List[ProblemFormat] = []

        try:
            async with self.store._connection() as conn:
                import asyncio
                loop = asyncio.get_event_loop()

                def _detect():
                    result = []

                    # Build buyer filter
                    buyer_filter = ""
                    buyer_param = ()
                    if buyer_id:
                        buyer_filter = "AND c.buyer_id = ?"
                        buyer_param = (buyer_id,)

                    # 1. Disapproved creatives
                    cursor = conn.execute(f"""
                        SELECT c.id, c.approval_status, c.format, c.width, c.height
                        FROM creatives c
                        WHERE c.approval_status != 'APPROVED'
                          AND c.approval_status IS NOT NULL
                          {buyer_filter}
                    """, buyer_param)

                    for row in cursor.fetchall():
                        result.append(ProblemFormat(
                            creative_id=row['id'],
                            problem_type='disapproved',
                            evidence={
                                'approval_status': row['approval_status'],
                                'format': row['format'],
                            },
                            severity='high',
                            recommendation='Review disapproval reason and fix or remove creative',
                        ))

                    # 2. Non-standard sizes (using tolerance)
                    cursor = conn.execute(f"""
                        SELECT c.id, c.width, c.height, c.format
                        FROM creatives c
                        WHERE c.width > 0 AND c.height > 0
                          {buyer_filter}
                    """, buyer_param)

                    for row in cursor.fetchall():
                        width = row['width']
                        height = row['height']
                        # Use tolerance-based check
                        canonical = canonical_size_with_tolerance(width, height, size_tolerance)
                        if canonical.startswith('Non-Standard'):
                            result.append(ProblemFormat(
                                creative_id=row['id'],
                                problem_type='non_standard',
                                evidence={
                                    'width': width,
                                    'height': height,
                                    'canonical_size': canonical,
                                    'format': row['format'],
                                },
                                severity='medium',
                                recommendation=f'Size {width}x{height} is non-standard. Consider resizing to nearest IAB standard.',
                            ))

                    # 3. Zero bids and low bid rate (from performance_metrics)
                    cursor = conn.execute(f"""
                        SELECT c.id, c.format,
                               COALESCE(SUM(pm.reached_queries), 0) as queries,
                               COALESCE(SUM(pm.impressions), 0) as impressions,
                               COALESCE(SUM(pm.spend_micros), 0) as spend
                        FROM creatives c
                        LEFT JOIN performance_metrics pm ON c.id = pm.creative_id
                          AND pm.metric_date >= date('now', '-{days} days')
                        WHERE 1=1 {buyer_filter}
                        GROUP BY c.id
                        HAVING queries > 1000  -- Only check creatives with significant traffic
                    """, buyer_param)

                    for row in cursor.fetchall():
                        queries = row['queries']
                        impressions = row['impressions']

                        if queries > 0 and impressions == 0:
                            # Zero bids
                            result.append(ProblemFormat(
                                creative_id=row['id'],
                                problem_type='zero_bids',
                                evidence={
                                    'reached_queries': queries,
                                    'impressions': impressions,
                                    'format': row['format'],
                                },
                                severity='high',
                                recommendation='Creative receives queries but never wins. Check bid strategy or creative quality.',
                            ))
                        elif queries > 0 and (impressions / queries) < 0.01:
                            # Low bid rate (< 1%)
                            bid_rate = (impressions / queries) * 100
                            result.append(ProblemFormat(
                                creative_id=row['id'],
                                problem_type='low_bid_rate',
                                evidence={
                                    'reached_queries': queries,
                                    'impressions': impressions,
                                    'bid_rate_pct': round(bid_rate, 4),
                                    'format': row['format'],
                                },
                                severity='medium',
                                recommendation=f'Bid rate {bid_rate:.2f}% is very low. Review bid strategy or creative quality.',
                            ))

                    return result

                problems = await loop.run_in_executor(None, _detect)

        except Exception as e:
            logger.error(f"Problem format detection failed: {e}")

        # Sort by severity (high first)
        severity_order = {'high': 0, 'medium': 1, 'low': 2}
        problems.sort(key=lambda p: (severity_order.get(p.severity, 2), p.creative_id))

        return problems
