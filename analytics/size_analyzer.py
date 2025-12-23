"""
Size Mismatch Analyzer for QPS Optimization.

Identifies ad sizes where traffic exists but no creatives are available,
generating recommendations to either block the size or add creatives.

This builds on the existing WasteAnalyzer but outputs structured
Recommendation objects with evidence, impact, and actions.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional

from analytics.recommendation_engine import (
    Action,
    Confidence,
    Evidence,
    Impact,
    Recommendation,
    RecommendationType,
    Severity,
    severity_from_waste_rate,
)
from utils.size_normalization import (
    IAB_STANDARD_SIZES,
    canonical_size_with_tolerance,
    get_size_category,
)

if TYPE_CHECKING:
    from storage.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)

# Constants
HIGH_VOLUME_THRESHOLD = 10000  # requests/day
MEDIUM_VOLUME_THRESHOLD = 1000  # requests/day
SECONDS_PER_DAY = 86400
ESTIMATED_COST_PER_1000 = 0.002  # $0.002 per 1000 requests for processing


class SizeAnalyzer:
    """
    Analyzes size mismatches between RTB traffic and creative inventory.

    Generates recommendations for:
    - Blocking sizes with high traffic but no creatives (waste reduction)
    - Adding creatives for sizes with moderate traffic
    - Using flexible HTML5 for near-IAB sizes
    """

    def __init__(self, db_store: "SQLiteStore"):
        self.store = db_store

    async def analyze(self, days: int = 7) -> list[Recommendation]:
        """
        Run size mismatch analysis and generate recommendations.

        Args:
            days: Number of days of traffic data to analyze

        Returns:
            List of Recommendation objects for size-related issues
        """
        recommendations: list[Recommendation] = []

        try:
            # Get creative inventory by size
            inventory = await self._get_inventory_by_size()

            # Get traffic data by size
            traffic = await self._get_traffic_by_size(days)

            if not traffic:
                logger.warning("No traffic data available for size analysis")
                return recommendations

            # Calculate totals for context
            total_requests = sum(t["count"] for t in traffic.values())
            total_waste = 0

            # Find gaps: sizes with traffic but no creatives
            for size, traffic_data in traffic.items():
                request_count = traffic_data["count"]
                inv_data = inventory.get(size, {"count": 0})
                creative_count = inv_data["count"]

                # Only analyze gaps (have traffic, no creatives)
                if creative_count == 0 and request_count > 0:
                    total_waste += request_count

                    rec = self._create_size_recommendation(
                        canonical_size=size,
                        request_count=request_count,
                        total_requests=total_requests,
                        days=days,
                    )
                    if rec:
                        recommendations.append(rec)

            logger.info(
                f"Size analysis: {len(recommendations)} recommendations from "
                f"{len(traffic)} sizes, {total_waste:,} wasted of {total_requests:,} total"
            )

        except Exception as e:
            logger.error(f"Size analysis failed: {e}")

        return recommendations

    async def _get_inventory_by_size(self) -> dict[str, dict]:
        """Get creative inventory grouped by canonical size."""
        import asyncio

        async with self.store._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute("""
                    SELECT canonical_size, COUNT(*) as count, format
                    FROM creatives
                    WHERE canonical_size IS NOT NULL
                    GROUP BY canonical_size, format
                """)

                inventory: dict[str, dict] = {}
                for row in cursor.fetchall():
                    size = row["canonical_size"]
                    if size not in inventory:
                        inventory[size] = {"count": 0, "formats": {}}
                    inventory[size]["count"] += row["count"]
                    fmt = row["format"] or "UNKNOWN"
                    inventory[size]["formats"][fmt] = row["count"]

                return inventory

            return await loop.run_in_executor(None, _query)

    async def _get_traffic_by_size(self, days: int) -> dict[str, dict]:
        """
        Get RTB traffic data grouped by canonical size.

        Uses performance_metrics table to aggregate queries by size.
        """
        import asyncio

        async with self.store._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                # Try to get size data from traffic
                # Note: We need to join with creatives to get sizes
                # If no direct size in traffic, aggregate from creatives performance
                cursor = conn.execute("""
                    SELECT
                        c.canonical_size,
                        COALESCE(SUM(pm.reached_queries), 0) as request_count
                    FROM performance_metrics pm
                    JOIN creatives c ON pm.creative_id = c.id
                    WHERE pm.metric_date >= date('now', ?)
                      AND c.canonical_size IS NOT NULL
                    GROUP BY c.canonical_size
                """, (f"-{days} days",))

                traffic: dict[str, dict] = {}
                for row in cursor.fetchall():
                    size = row["canonical_size"]
                    count = row["request_count"] or 0
                    if size and count > 0:
                        traffic[size] = {"count": count}

                return traffic

            return await loop.run_in_executor(None, _query)

    def _create_size_recommendation(
        self,
        canonical_size: str,
        request_count: int,
        total_requests: int,
        days: int,
    ) -> Optional[Recommendation]:
        """
        Create a recommendation for a size gap.

        Args:
            canonical_size: The normalized size category
            request_count: Number of requests for this size
            total_requests: Total requests for percentage calculation
            days: Analysis period for QPS calculation

        Returns:
            Recommendation object or None if below thresholds
        """
        # Calculate metrics
        daily_requests = request_count / days if days > 0 else request_count
        qps = daily_requests / SECONDS_PER_DAY
        waste_pct = (request_count / total_requests * 100) if total_requests > 0 else 0
        monthly_savings = self._estimate_monthly_savings(request_count, days)

        # Skip low volume sizes
        if daily_requests < 100:
            return None

        # Determine recommendation type and severity
        closest_iab = self._find_closest_iab_size(canonical_size)
        is_near_iab = closest_iab is not None and get_size_category(canonical_size) == "Non-Standard"

        # Build evidence
        evidence = [
            Evidence(
                metric_name="daily_requests",
                metric_value=daily_requests,
                threshold=MEDIUM_VOLUME_THRESHOLD,
                comparison="above" if daily_requests >= MEDIUM_VOLUME_THRESHOLD else "below",
                time_period_days=days,
                sample_size=request_count,
                trend=None,  # Could compute if we have historical data
            ),
            Evidence(
                metric_name="creative_count",
                metric_value=0,
                threshold=1,
                comparison="below",
                time_period_days=days,
                sample_size=1,
            ),
        ]

        # Build impact
        impact = Impact(
            wasted_qps=qps,
            wasted_queries_daily=int(daily_requests),
            wasted_spend_usd=monthly_savings / 30,  # Daily waste
            percent_of_total_waste=waste_pct,
            potential_savings_monthly=monthly_savings,
        )

        # Determine action based on volume and IAB proximity
        if daily_requests >= HIGH_VOLUME_THRESHOLD:
            severity = Severity.HIGH if waste_pct > 5 else Severity.MEDIUM

            if is_near_iab:
                # Recommend flexible HTML5
                action = Action(
                    action_type="add",
                    target_type="creative",
                    target_id=canonical_size,
                    target_name=f"Flexible HTML5 for {closest_iab}",
                    pretargeting_field=None,
                    api_example=f"Create HTML5 creative that renders at {closest_iab}",
                )
                title = f"Add flexible creative for {canonical_size}"
                description = (
                    f"High traffic size {canonical_size} is close to IAB standard {closest_iab}. "
                    f"Add a flexible HTML5 creative that can render at {closest_iab} to capture "
                    f"{int(daily_requests):,} requests/day ({qps:.2f} QPS)."
                )
            else:
                # Recommend blocking
                action = Action(
                    action_type="block",
                    target_type="size",
                    target_id=canonical_size,
                    target_name=canonical_size,
                    pretargeting_field="excluded_creative_dimensions",
                    api_example=f"Add {canonical_size} to pretargeting excludedCreativeDimensions",
                )
                title = f"Block size {canonical_size}"
                description = (
                    f"Size {canonical_size} receives {int(daily_requests):,} requests/day "
                    f"({qps:.2f} QPS) but has no matching creatives. Block in pretargeting "
                    f"to save ${monthly_savings:.2f}/month."
                )

        elif daily_requests >= MEDIUM_VOLUME_THRESHOLD:
            severity = Severity.MEDIUM if waste_pct > 2 else Severity.LOW

            action = Action(
                action_type="add",
                target_type="creative",
                target_id=canonical_size,
                target_name=f"New creative for {canonical_size}",
                pretargeting_field=None,
                api_example=f"Create creative with dimensions {canonical_size}",
            )
            title = f"Consider adding creative for {canonical_size}"
            description = (
                f"Size {canonical_size} receives moderate traffic ({int(daily_requests):,}/day). "
                f"Adding a creative could capture {qps:.2f} QPS. "
                f"Closest IAB: {closest_iab or 'none'}."
            )

        else:
            # Low volume - just monitor
            severity = Severity.LOW
            action = Action(
                action_type="review",
                target_type="size",
                target_id=canonical_size,
                target_name=canonical_size,
            )
            title = f"Monitor size {canonical_size}"
            description = (
                f"Low volume size {canonical_size} ({int(daily_requests):,}/day). "
                f"Monitor for growth before taking action."
            )

        # Determine confidence based on data volume
        if request_count > 100000:
            confidence = Confidence.HIGH
        elif request_count > 10000:
            confidence = Confidence.MEDIUM
        else:
            confidence = Confidence.LOW

        return Recommendation(
            id=f"size-{canonical_size.replace(' ', '-')}-{uuid.uuid4().hex[:8]}",
            type=RecommendationType.SIZE_MISMATCH,
            severity=severity,
            confidence=confidence,
            title=title,
            description=description,
            evidence=evidence,
            impact=impact,
            actions=[action],
            affected_creatives=[],
            affected_campaigns=[],
            expires_at=(datetime.utcnow() + timedelta(days=7)).isoformat(),
        )

    def _find_closest_iab_size(
        self,
        canonical_size: str,
        tolerance: int = 5,
    ) -> Optional[str]:
        """Find the closest IAB standard size to a non-standard size."""
        # Extract dimensions from canonical size
        match = re.search(r"\((\d+)x(\d+)\)", canonical_size)
        if not match:
            # Try direct format like "300x250"
            match = re.search(r"(\d+)x(\d+)", canonical_size)
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
        """Estimate monthly cost savings from blocking waste traffic."""
        if days <= 0:
            return 0.0

        daily_requests = request_count / days
        monthly_requests = daily_requests * 30
        savings = (monthly_requests / 1000) * ESTIMATED_COST_PER_1000

        return round(savings, 2)
