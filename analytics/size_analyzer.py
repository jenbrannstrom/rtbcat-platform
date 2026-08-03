"""
Size Mismatch Analyzer for QPS Optimization.

Identifies ad sizes where traffic exists but no creatives are available,
generating recommendations to either block the size or add creatives.

This is the canonical size analyzer for the analytics module. It outputs
structured Recommendation objects with evidence, impact, and actions.

Related modules:
    - ``qps.size_analyzer.QpsSizeCoverageAnalyzer``: CLI-focused analyzer
      that generates text reports. Maintained for backwards compatibility.

Usage:
    >>> from analytics.size_analyzer import SizeAnalyzer
    >>> analyzer = SizeAnalyzer()
    >>> recommendations = await analyzer.analyze(buyer_id="123", days=7)
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Optional

from analytics.recommendation_engine import (
    Action,
    Confidence,
    Evidence,
    Impact,
    Recommendation,
    RecommendationType,
    Severity,
)
from storage.serving_database import db_query
from utils.size_normalization import (
    IAB_STANDARD_SIZES,
    get_size_category,
)

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

    def __init__(self, db_store: object | None = None):
        self._store = db_store

    async def analyze(self, *, buyer_id: str, days: int = 7) -> list[Recommendation]:
        """
        Run size mismatch analysis and generate recommendations.

        Args:
            days: Number of days of traffic data to analyze

        Returns:
            List of Recommendation objects for size-related issues
        """
        recommendations: list[Recommendation] = []

        inventory = await self._get_inventory_by_size(buyer_id=buyer_id, days=days)
        traffic = await self._get_traffic_by_size(buyer_id=buyer_id, days=days)

        if not traffic:
            logger.info("No buyer-scoped traffic data available for size analysis")
            return recommendations

        total_requests = sum(t["count"] for t in traffic.values())
        total_waste = 0

        for size, traffic_data in traffic.items():
            request_count = traffic_data["count"]
            creative_count = inventory.get(size, {"count": 0})["count"]

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
            "Size analysis for buyer_id=%s: %d recommendations from %d sizes, "
            "%d wasted of %d total",
            buyer_id,
            len(recommendations),
            len(traffic),
            total_waste,
            total_requests,
        )

        return recommendations

    async def _get_inventory_by_size(
        self, *, buyer_id: str, days: int
    ) -> dict[str, dict]:
        """Get observed buyer creative inventory grouped by canonical size."""
        rows = await db_query(
            """
            SELECT creative_size AS canonical_size,
                   COUNT(DISTINCT creative_id) AS count
            FROM config_creative_daily
            WHERE buyer_account_id = ?
              AND metric_date >= date('now', ?)
              AND creative_size IS NOT NULL
              AND creative_size != ''
            GROUP BY creative_size
        """,
            (buyer_id, f"-{days} days"),
        )

        inventory: dict[str, dict] = {}
        for row in rows:
            size = row["canonical_size"]
            inventory[size] = {"count": row["count"] or 0}

        return inventory

    async def _get_traffic_by_size(
        self, *, buyer_id: str, days: int
    ) -> dict[str, dict]:
        """Get buyer-scoped RTB traffic grouped by canonical size."""
        rows = await db_query(
            """
            SELECT
                creative_size AS canonical_size,
                COALESCE(SUM(reached_queries), 0) AS request_count
            FROM config_size_daily
            WHERE buyer_account_id = ?
              AND metric_date >= date('now', ?)
              AND creative_size IS NOT NULL
              AND creative_size != ''
            GROUP BY creative_size
        """,
            (buyer_id, f"-{days} days"),
        )

        traffic: dict[str, dict] = {}
        for row in rows:
            size = row["canonical_size"]
            count = row["request_count"] or 0
            if size and count > 0:
                traffic[size] = {"count": count}

        return traffic

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
        is_near_iab = (
            closest_iab is not None
            and get_size_category(canonical_size) == "Non-Standard"
        )

        # Build evidence
        evidence = [
            Evidence(
                metric_name="daily_requests",
                metric_value=daily_requests,
                threshold=MEDIUM_VOLUME_THRESHOLD,
                comparison="above"
                if daily_requests >= MEDIUM_VOLUME_THRESHOLD
                else "below",
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
            expires_at=(datetime.now(UTC) + timedelta(days=7)).isoformat(),
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
