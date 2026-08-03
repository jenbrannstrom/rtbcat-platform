"""
Geographic Waste Analyzer for QPS Optimization.

Identifies geographic regions with poor performance metrics,
recommending exclusions for wasteful geos.

Analyzes:
- Countries with high spend but low CTR/conversions
- Regions with traffic but no matching creatives
- Geo-specific fraud patterns
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from analytics.cost_estimator import resolve_request_cost_per_1000
from analytics.recommendation_engine import (
    Action,
    Confidence,
    Evidence,
    Impact,
    Recommendation,
    RecommendationType,
    Severity,
)
from storage.serving_database import db_query, db_query_one

logger = logging.getLogger(__name__)

# Thresholds
MIN_GEO_SPEND_USD = 10  # Minimum spend to analyze a geo
LOW_CTR_THRESHOLD = 0.02  # 2% CTR is below average for display ads
CTR_UNDERPERFORM_RATIO = 0.5  # CTR less than 50% of average = underperformer
HIGH_WASTE_RATE_THRESHOLD = 0.80  # >80% query-to-impression waste is high risk
SECONDS_PER_DAY = 86400


class GeoAnalyzer:
    """
    Analyzes geographic performance and identifies wasteful regions.

    Generates recommendations for:
    - Excluding low-performance countries/regions
    - Adjusting bids for underperforming geos
    - Adding geo-specific creatives
    """

    def __init__(self, db_store: object | None = None):
        self._store = db_store

    async def analyze(self, *, buyer_id: str, days: int = 7) -> list[Recommendation]:
        """
        Run geographic waste analysis and generate recommendations.

        Args:
            days: Number of days of performance data to analyze

        Returns:
            List of Recommendation objects for geo-related issues
        """
        recommendations = await self._check_low_performance_geos(
            buyer_id=buyer_id,
            days=days,
        )
        logger.info(
            "Geo analysis for buyer_id=%s: %d recommendations",
            buyer_id,
            len(recommendations),
        )

        return recommendations

    async def _check_low_performance_geos(
        self, *, buyer_id: str, days: int
    ) -> list[Recommendation]:
        """Check for geos with CTR significantly below average."""
        recommendations: list[Recommendation] = []

        totals = (
            await db_query_one(
                """
            SELECT
                COALESCE(SUM(impressions), 0) as total_impressions,
                COALESCE(SUM(clicks), 0) as total_clicks
            FROM rtb_buyer_spend_daily
            WHERE buyer_account_id = ?
              AND metric_date >= date('now', ?)
        """,
                (buyer_id, f"-{days} days"),
            )
            or {}
        )
        total_imps = totals.get("total_impressions", 0) or 1
        total_clicks = totals.get("total_clicks", 0) or 0
        avg_ctr = total_clicks / total_imps if total_imps > 0 else 0

        results = await db_query(
            """
            SELECT
                country AS geo,
                COALESCE(SUM(impressions), 0) AS impressions,
                COALESCE(SUM(clicks), 0) AS clicks,
                COALESCE(SUM(spend_micros), 0) AS spend_micros
            FROM rtb_app_country_daily
            WHERE buyer_account_id = ?
              AND metric_date >= date('now', ?)
              AND country IS NOT NULL
              AND country != ''
            GROUP BY country
            HAVING COALESCE(SUM(spend_micros), 0) > ?
        """,
            (buyer_id, f"-{days} days", MIN_GEO_SPEND_USD * 1_000_000),
        )

        for row in results:
            geo = row["geo"]
            impressions = row["impressions"]
            clicks = row["clicks"]
            spend_micros = row["spend_micros"]
            spend_usd = spend_micros / 1_000_000
            ctr = clicks / impressions if impressions > 0 else 0

            # Check if CTR is significantly below average OR below absolute threshold
            is_underperformer = avg_ctr > 0 and ctr < avg_ctr * CTR_UNDERPERFORM_RATIO
            is_low_absolute = ctr < LOW_CTR_THRESHOLD

            if (is_underperformer or is_low_absolute) and impressions > 1000:
                # Determine severity based on spend
                if spend_usd > 100:
                    severity = Severity.HIGH
                elif spend_usd > 50:
                    severity = Severity.MEDIUM
                else:
                    severity = Severity.LOW

                rec = Recommendation(
                    id=f"low-perf-geo-{geo}-{uuid.uuid4().hex[:8]}",
                    type=RecommendationType.GEO_EXCLUSION,
                    severity=severity,
                    confidence=Confidence.HIGH
                    if impressions > 10000
                    else Confidence.MEDIUM,
                    title=f"Underperforming geo: {geo}",
                    description=(
                        f"Geographic region '{geo}' has {ctr * 100:.2f}% CTR vs {avg_ctr * 100:.2f}% average. "
                        f"Spent ${spend_usd:.2f} on {impressions:,} impressions with {clicks:,} clicks. "
                        f"Consider reducing bids or excluding this geo."
                    ),
                    evidence=[
                        Evidence(
                            metric_name="ctr",
                            metric_value=ctr * 100,
                            threshold=avg_ctr * 100,
                            comparison="below",
                            time_period_days=days,
                            sample_size=impressions,
                        ),
                        Evidence(
                            metric_name="spend_usd",
                            metric_value=spend_usd,
                            threshold=MIN_GEO_SPEND_USD,
                            comparison="above",
                            time_period_days=days,
                            sample_size=impressions,
                        ),
                    ],
                    impact=Impact(
                        wasted_qps=0,
                        wasted_queries_daily=0,
                        wasted_spend_usd=spend_usd * 0.5,  # Estimate 50% could be saved
                        percent_of_total_waste=0,
                        potential_savings_monthly=spend_usd * 0.5 * 30 / days,
                    ),
                    actions=[
                        Action(
                            action_type="exclude",
                            target_type="geo",
                            target_id=geo,
                            target_name=f"Region: {geo}",
                            pretargeting_field="excluded_geographies",
                            api_example=f"Reduce bid or exclude '{geo}' from targeting",
                        ),
                    ],
                    affected_creatives=[],
                    affected_campaigns=[],
                    expires_at=(datetime.now(UTC) + timedelta(days=7)).isoformat(),
                )
                recommendations.append(rec)

        return recommendations

    async def _check_high_waste_geos(
        self, *, buyer_id: str, days: int
    ) -> list[Recommendation]:
        """Check for geos with high query volume but low impression rate."""
        recommendations: list[Recommendation] = []
        request_cost_per_1000 = await resolve_request_cost_per_1000(
            days=days,
            buyer_id=buyer_id,
        )

        results = await db_query(
            """
            SELECT
                country AS geo,
                COALESCE(SUM(reached_queries), 0) AS queries,
                COALESCE(SUM(impressions), 0) AS impressions,
                COALESCE(SUM(spend_micros), 0) AS spend_micros
            FROM rtb_app_country_daily
            WHERE buyer_account_id = ?
              AND metric_date >= date('now', ?)
              AND country IS NOT NULL
              AND country != ''
            GROUP BY country
            HAVING COALESCE(SUM(reached_queries), 0) > 100000
        """,
            (buyer_id, f"-{days} days"),
        )

        for row in results:
            geo = row["geo"]
            queries = row["queries"]
            impressions = row["impressions"]
            waste_rate = 1 - (impressions / queries) if queries > 0 else 0
            daily_queries = queries / days
            wasted_daily = daily_queries * waste_rate

            if waste_rate > HIGH_WASTE_RATE_THRESHOLD:
                rec = Recommendation(
                    id=f"high-waste-geo-{geo}-{uuid.uuid4().hex[:8]}",
                    type=RecommendationType.GEO_EXCLUSION,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.MEDIUM,
                    title=f"High waste rate in {geo}",
                    description=(
                        f"Geographic region '{geo}' has a {waste_rate * 100:.1f}% waste rate - "
                        f"receiving {queries:,} queries but only {impressions:,} impressions. "
                        f"This could indicate missing creatives for this geo or bid issues."
                    ),
                    evidence=[
                        Evidence(
                            metric_name="waste_rate",
                            metric_value=waste_rate * 100,
                            threshold=HIGH_WASTE_RATE_THRESHOLD * 100,
                            comparison="above",
                            time_period_days=days,
                            sample_size=queries,
                        ),
                    ],
                    impact=Impact(
                        wasted_qps=wasted_daily / SECONDS_PER_DAY,
                        wasted_queries_daily=int(wasted_daily),
                        wasted_spend_usd=0,
                        percent_of_total_waste=0,
                        potential_savings_monthly=(wasted_daily * 30 / 1000)
                        * request_cost_per_1000,
                    ),
                    actions=[
                        Action(
                            action_type="review",
                            target_type="geo",
                            target_id=geo,
                            target_name=f"Region: {geo}",
                            api_example=f"Review creative coverage and bid strategy for {geo}",
                        ),
                    ],
                    affected_creatives=[],
                    affected_campaigns=[],
                    expires_at=(datetime.now(UTC) + timedelta(days=7)).isoformat(),
                )
                recommendations.append(rec)

        return recommendations
