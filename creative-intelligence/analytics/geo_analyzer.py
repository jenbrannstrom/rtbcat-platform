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
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from analytics.recommendation_engine import (
    Action,
    Confidence,
    Evidence,
    Impact,
    Recommendation,
    RecommendationType,
    Severity,
)

if TYPE_CHECKING:
    from storage.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)

# Thresholds
MIN_GEO_SPEND_USD = 10  # Minimum spend to analyze a geo
LOW_CTR_THRESHOLD = 0.02  # 2% CTR is below average for display ads
CTR_UNDERPERFORM_RATIO = 0.5  # CTR less than 50% of average = underperformer
SECONDS_PER_DAY = 86400


class GeoAnalyzer:
    """
    Analyzes geographic performance and identifies wasteful regions.

    Generates recommendations for:
    - Excluding low-performance countries/regions
    - Adjusting bids for underperforming geos
    - Adding geo-specific creatives
    """

    def __init__(self, db_store: "SQLiteStore"):
        self.store = db_store

    async def analyze(self, days: int = 7) -> list[Recommendation]:
        """
        Run geographic waste analysis and generate recommendations.

        Args:
            days: Number of days of performance data to analyze

        Returns:
            List of Recommendation objects for geo-related issues
        """
        recommendations: list[Recommendation] = []

        try:
            # Check for low-performing geos (compares CTR to average)
            low_perf_recs = await self._check_low_performance_geos(days)
            recommendations.extend(low_perf_recs)

            # Note: _check_high_waste_geos and _check_geo_coverage_gaps
            # require reached_queries data which may not be available
            # in all CSV imports. Skip if no query data.

            logger.info(f"Geo analysis: {len(recommendations)} recommendations")

        except Exception as e:
            logger.error(f"Geo analysis failed: {e}")

        return recommendations

    async def _check_low_performance_geos(self, days: int) -> list[Recommendation]:
        """Check for geos with CTR significantly below average."""
        import asyncio

        recommendations: list[Recommendation] = []

        async with self.store._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                # First get overall average CTR
                cursor = conn.execute("""
                    SELECT
                        COALESCE(SUM(impressions), 0) as total_impressions,
                        COALESCE(SUM(clicks), 0) as total_clicks
                    FROM performance_metrics
                    WHERE metric_date >= date('now', ?)
                """, (f"-{days} days",))
                totals = dict(cursor.fetchone())
                total_imps = totals.get("total_impressions", 0) or 1
                total_clicks = totals.get("total_clicks", 0) or 0
                avg_ctr = total_clicks / total_imps if total_imps > 0 else 0

                # Get per-geo performance
                cursor = conn.execute("""
                    SELECT
                        pm.geography as geo,
                        COALESCE(SUM(pm.impressions), 0) as impressions,
                        COALESCE(SUM(pm.clicks), 0) as clicks,
                        COALESCE(SUM(pm.spend_micros), 0) as spend_micros,
                        COUNT(DISTINCT pm.creative_id) as creative_count
                    FROM performance_metrics pm
                    WHERE pm.metric_date >= date('now', ?)
                      AND pm.geography IS NOT NULL
                      AND pm.geography != ''
                    GROUP BY pm.geography
                    HAVING SUM(pm.spend_micros) > ?
                """, (f"-{days} days", MIN_GEO_SPEND_USD * 1_000_000))

                return [dict(row) for row in cursor.fetchall()], avg_ctr

            results, avg_ctr = await loop.run_in_executor(None, _query)

        for row in results:
            geo = row["geo"]
            impressions = row["impressions"]
            clicks = row["clicks"]
            spend_micros = row["spend_micros"]
            spend_usd = spend_micros / 1_000_000
            ctr = clicks / impressions if impressions > 0 else 0

            # Check if CTR is significantly below average OR below absolute threshold
            is_underperformer = (avg_ctr > 0 and ctr < avg_ctr * CTR_UNDERPERFORM_RATIO)
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
                    confidence=Confidence.HIGH if impressions > 10000 else Confidence.MEDIUM,
                    title=f"Underperforming geo: {geo}",
                    description=(
                        f"Geographic region '{geo}' has {ctr*100:.2f}% CTR vs {avg_ctr*100:.2f}% average. "
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
                    expires_at=(datetime.utcnow() + timedelta(days=7)).isoformat(),
                )
                recommendations.append(rec)

        return recommendations

    async def _check_high_waste_geos(self, days: int) -> list[Recommendation]:
        """Check for geos with high query volume but low impression rate."""
        import asyncio

        recommendations: list[Recommendation] = []

        async with self.store._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute("""
                    SELECT
                        pm.geography as geo,
                        COALESCE(SUM(pm.reached_queries), 0) as queries,
                        COALESCE(SUM(pm.impressions), 0) as impressions,
                        COALESCE(SUM(pm.spend_micros), 0) as spend_micros
                    FROM performance_metrics pm
                    WHERE pm.metric_date >= date('now', ?)
                      AND pm.geography IS NOT NULL
                      AND pm.geography != ''
                    GROUP BY pm.geography
                    HAVING queries > 100000
                """, (f"-{days} days",))

                return [dict(row) for row in cursor.fetchall()]

            results = await loop.run_in_executor(None, _query)

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
                        f"Geographic region '{geo}' has a {waste_rate*100:.1f}% waste rate - "
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
                        potential_savings_monthly=wasted_daily * 30 * 0.002 / 1000,
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
                    expires_at=(datetime.utcnow() + timedelta(days=7)).isoformat(),
                )
                recommendations.append(rec)

        return recommendations

    async def _check_geo_coverage_gaps(self, days: int) -> list[Recommendation]:
        """Check for geos with traffic but limited creative coverage."""
        import asyncio

        recommendations: list[Recommendation] = []

        async with self.store._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                # Find geos with queries from creatives that don't target them
                cursor = conn.execute("""
                    SELECT
                        pm.geography as geo,
                        COUNT(DISTINCT pm.creative_id) as active_creatives,
                        COALESCE(SUM(pm.reached_queries), 0) as queries,
                        COALESCE(SUM(pm.impressions), 0) as impressions
                    FROM performance_metrics pm
                    WHERE pm.metric_date >= date('now', ?)
                      AND pm.geography IS NOT NULL
                      AND pm.geography != ''
                    GROUP BY pm.geography
                    HAVING queries > 50000 AND active_creatives < 3
                """, (f"-{days} days",))

                return [dict(row) for row in cursor.fetchall()]

            results = await loop.run_in_executor(None, _query)

        for row in results:
            geo = row["geo"]
            creative_count = row["active_creatives"]
            queries = row["queries"]
            impressions = row["impressions"]
            win_rate = impressions / queries if queries > 0 else 0

            rec = Recommendation(
                id=f"geo-gap-{geo}-{uuid.uuid4().hex[:8]}",
                type=RecommendationType.CONFIG_INEFFICIENCY,
                severity=Severity.LOW,
                confidence=Confidence.MEDIUM,
                title=f"Limited creative coverage in {geo}",
                description=(
                    f"Geographic region '{geo}' has {queries:,} queries but only "
                    f"{creative_count} active creative(s). Consider adding more geo-targeted "
                    f"creatives or reviewing pretargeting configuration."
                ),
                evidence=[
                    Evidence(
                        metric_name="creative_count",
                        metric_value=creative_count,
                        threshold=3,
                        comparison="below",
                        time_period_days=days,
                        sample_size=creative_count,
                    ),
                    Evidence(
                        metric_name="queries",
                        metric_value=queries,
                        threshold=50000,
                        comparison="above",
                        time_period_days=days,
                        sample_size=queries,
                    ),
                ],
                impact=Impact(
                    wasted_qps=0,
                    wasted_queries_daily=0,
                    wasted_spend_usd=0,
                    percent_of_total_waste=0,
                    potential_savings_monthly=0,
                ),
                actions=[
                    Action(
                        action_type="add",
                        target_type="creative",
                        target_id=geo,
                        target_name=f"Geo-targeted creative for {geo}",
                        api_example=f"Add creatives targeting {geo} specifically",
                    ),
                ],
                affected_creatives=[],
                affected_campaigns=[],
                expires_at=(datetime.utcnow() + timedelta(days=14)).isoformat(),
            )
            recommendations.append(rec)

        return recommendations
