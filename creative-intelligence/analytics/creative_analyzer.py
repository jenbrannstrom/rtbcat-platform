"""
Creative Health Analyzer for QPS Optimization.

Identifies problematic creatives that waste QPS due to:
- Broken videos (can't play, no transcodes)
- Zero engagement (impressions but no clicks ever)
- Low win rate (queries but no impressions)
- Disapproved creatives still receiving traffic
"""

from __future__ import annotations

import logging
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
)

if TYPE_CHECKING:
    from storage.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)

# Thresholds
MIN_IMPRESSIONS_FOR_ANALYSIS = 1000  # Need enough data
ZERO_ENGAGEMENT_CTR_THRESHOLD = 0.001  # < 0.1% CTR = zero engagement
LOW_CTR_RATIO = 0.3  # CTR less than 30% of average = underperformer
MIN_SPEND_FOR_REVIEW = 10  # $10+ spend to flag for review
SECONDS_PER_DAY = 86400


class CreativeAnalyzer:
    """
    Analyzes creative health and identifies problematic creatives.

    Generates recommendations for:
    - Pausing broken/disapproved creatives
    - Reviewing zero-engagement creatives
    - Fixing low win rate issues
    """

    def __init__(self, db_store: "SQLiteStore"):
        self.store = db_store

    async def analyze(self, days: int = 7) -> list[Recommendation]:
        """
        Run creative health analysis and generate recommendations.

        Args:
            days: Number of days of performance data to analyze

        Returns:
            List of Recommendation objects for creative issues
        """
        recommendations: list[Recommendation] = []

        try:
            # Check for creatives with very low CTR compared to average
            low_ctr_recs = await self._check_low_ctr_creatives(days)
            recommendations.extend(low_ctr_recs)

            # Check for zero engagement (if any exist)
            zero_engagement_recs = await self._check_zero_engagement(days)
            recommendations.extend(zero_engagement_recs)

            # Check disapproved creatives
            disapproved_recs = await self._check_disapproved(days)
            recommendations.extend(disapproved_recs)

            # Note: _check_broken_videos and _check_low_win_rate
            # require reached_queries data which may not be available

            logger.info(f"Creative analysis: {len(recommendations)} recommendations")

        except Exception as e:
            logger.error(f"Creative analysis failed: {e}")

        return recommendations

    async def _check_low_ctr_creatives(self, days: int) -> list[Recommendation]:
        """Check for creatives with CTR significantly below average."""
        import asyncio

        recommendations: list[Recommendation] = []

        async with self.store._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                # Get average CTR first
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

                # Find underperforming creatives
                cursor = conn.execute("""
                    SELECT
                        c.id,
                        c.format,
                        COALESCE(SUM(pm.impressions), 0) as impressions,
                        COALESCE(SUM(pm.clicks), 0) as clicks,
                        COALESCE(SUM(pm.spend_micros), 0) as spend_micros
                    FROM creatives c
                    JOIN performance_metrics pm ON c.id = pm.creative_id
                    WHERE pm.metric_date >= date('now', ?)
                    GROUP BY c.id
                    HAVING SUM(pm.impressions) > ? AND SUM(pm.spend_micros) > ?
                """, (f"-{days} days", MIN_IMPRESSIONS_FOR_ANALYSIS, MIN_SPEND_FOR_REVIEW * 1_000_000))

                return [dict(row) for row in cursor.fetchall()], avg_ctr

            results, avg_ctr = await loop.run_in_executor(None, _query)

        for row in results:
            creative_id = row["id"]
            impressions = row["impressions"]
            clicks = row["clicks"]
            spend_micros = row["spend_micros"]
            spend_usd = spend_micros / 1_000_000
            ctr = clicks / impressions if impressions > 0 else 0

            # Check if CTR is significantly below average
            if avg_ctr > 0 and ctr < avg_ctr * LOW_CTR_RATIO:
                severity = Severity.HIGH if spend_usd > 50 else Severity.MEDIUM

                rec = Recommendation(
                    id=f"low-ctr-creative-{creative_id}-{uuid.uuid4().hex[:8]}",
                    type=RecommendationType.CREATIVE_REVIEW,
                    severity=severity,
                    confidence=Confidence.HIGH if impressions > 10000 else Confidence.MEDIUM,
                    title=f"Underperforming creative #{creative_id}",
                    description=(
                        f"Creative #{creative_id} has {ctr*100:.2f}% CTR vs {avg_ctr*100:.2f}% average. "
                        f"Spent ${spend_usd:.2f} on {impressions:,} impressions with only {clicks:,} clicks. "
                        f"Review creative quality or pause to reduce waste."
                    ),
                    evidence=[
                        Evidence(
                            metric_name="ctr",
                            metric_value=ctr * 100,
                            threshold=avg_ctr * LOW_CTR_RATIO * 100,
                            comparison="below",
                            time_period_days=days,
                            sample_size=impressions,
                        ),
                        Evidence(
                            metric_name="spend_usd",
                            metric_value=spend_usd,
                            threshold=MIN_SPEND_FOR_REVIEW,
                            comparison="above",
                            time_period_days=days,
                            sample_size=impressions,
                        ),
                    ],
                    impact=Impact(
                        wasted_qps=0,
                        wasted_queries_daily=0,
                        wasted_spend_usd=spend_usd * 0.5,
                        percent_of_total_waste=0,
                        potential_savings_monthly=spend_usd * 0.5 * 30 / days,
                    ),
                    actions=[
                        Action(
                            action_type="review",
                            target_type="creative",
                            target_id=str(creative_id),
                            target_name=f"Creative #{creative_id}",
                            api_example="Review creative quality, targeting, or landing page",
                        ),
                        Action(
                            action_type="pause",
                            target_type="creative",
                            target_id=str(creative_id),
                            target_name=f"Creative #{creative_id}",
                            api_example=f"Pause creative {creative_id} to stop spend waste",
                        ),
                    ],
                    affected_creatives=[str(creative_id)],
                    expires_at=(datetime.utcnow() + timedelta(days=7)).isoformat(),
                )
                recommendations.append(rec)

        return recommendations

    async def _check_broken_videos(self, days: int) -> list[Recommendation]:
        """Check for video creatives that may be broken."""
        import asyncio

        recommendations: list[Recommendation] = []

        async with self.store._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                # Find video creatives with high queries but zero impressions
                cursor = conn.execute("""
                    SELECT
                        c.id,
                        c.format,
                        c.video_url,
                        COALESCE(SUM(pm.reached_queries), 0) as queries,
                        COALESCE(SUM(pm.impressions), 0) as impressions,
                        COALESCE(SUM(pm.spend_micros), 0) as spend_micros
                    FROM creatives c
                    LEFT JOIN performance_metrics pm ON c.id = pm.creative_id
                        AND pm.metric_date >= date('now', ?)
                    WHERE c.format = 'VIDEO'
                    GROUP BY c.id
                    HAVING queries > 10000 AND impressions = 0
                """, (f"-{days} days",))

                return [dict(row) for row in cursor.fetchall()]

            results = await loop.run_in_executor(None, _query)

        for row in results:
            creative_id = row["id"]
            queries = row["queries"]
            daily_queries = queries / days

            rec = Recommendation(
                id=f"broken-video-{creative_id}-{uuid.uuid4().hex[:8]}",
                type=RecommendationType.CREATIVE_REVIEW,
                severity=Severity.HIGH,
                confidence=Confidence.MEDIUM,
                title=f"Possible broken video creative #{creative_id}",
                description=(
                    f"Video creative #{creative_id} received {queries:,} queries over {days} days "
                    f"but won zero impressions. This may indicate a broken video file, "
                    f"missing transcodes, or VAST parsing issues. Review and fix or pause."
                ),
                evidence=[
                    Evidence(
                        metric_name="queries",
                        metric_value=queries,
                        threshold=10000,
                        comparison="above",
                        time_period_days=days,
                        sample_size=queries,
                    ),
                    Evidence(
                        metric_name="impressions",
                        metric_value=0,
                        threshold=1,
                        comparison="below",
                        time_period_days=days,
                        sample_size=queries,
                    ),
                ],
                impact=Impact(
                    wasted_qps=daily_queries / SECONDS_PER_DAY,
                    wasted_queries_daily=int(daily_queries),
                    wasted_spend_usd=0,  # No spend if no impressions
                    percent_of_total_waste=0,  # Would need total for this
                    potential_savings_monthly=daily_queries * 30 * 0.002 / 1000,
                ),
                actions=[
                    Action(
                        action_type="review",
                        target_type="creative",
                        target_id=str(creative_id),
                        target_name=f"Video #{creative_id}",
                        api_example="Check video file, transcodes, and VAST response",
                    ),
                    Action(
                        action_type="pause",
                        target_type="creative",
                        target_id=str(creative_id),
                        target_name=f"Video #{creative_id}",
                        api_example=f"PATCH /creatives/{creative_id} {{status: 'PAUSED'}}",
                    ),
                ],
                affected_creatives=[str(creative_id)],
                expires_at=(datetime.utcnow() + timedelta(days=3)).isoformat(),
            )
            recommendations.append(rec)

        return recommendations

    async def _check_zero_engagement(self, days: int) -> list[Recommendation]:
        """Check for creatives with impressions but zero clicks."""
        import asyncio

        recommendations: list[Recommendation] = []

        async with self.store._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute("""
                    SELECT
                        c.id,
                        c.format,
                        COALESCE(SUM(pm.impressions), 0) as impressions,
                        COALESCE(SUM(pm.clicks), 0) as clicks,
                        COALESCE(SUM(pm.spend_micros), 0) as spend_micros
                    FROM creatives c
                    LEFT JOIN performance_metrics pm ON c.id = pm.creative_id
                        AND pm.metric_date >= date('now', ?)
                    GROUP BY c.id
                    HAVING impressions > ? AND clicks = 0
                """, (f"-{days} days", MIN_IMPRESSIONS_FOR_ANALYSIS))

                return [dict(row) for row in cursor.fetchall()]

            results = await loop.run_in_executor(None, _query)

        for row in results:
            creative_id = row["id"]
            impressions = row["impressions"]
            spend_micros = row["spend_micros"]
            spend_usd = spend_micros / 1_000_000

            # Higher severity for higher spend
            if spend_usd > 100:
                severity = Severity.HIGH
            elif spend_usd > 10:
                severity = Severity.MEDIUM
            else:
                severity = Severity.LOW

            rec = Recommendation(
                id=f"zero-engagement-{creative_id}-{uuid.uuid4().hex[:8]}",
                type=RecommendationType.CREATIVE_PAUSE,
                severity=severity,
                confidence=Confidence.HIGH,
                title=f"Zero engagement creative #{creative_id}",
                description=(
                    f"Creative #{creative_id} has {impressions:,} impressions and ${spend_usd:.2f} "
                    f"spend but zero clicks over {days} days. This creative may have targeting "
                    f"issues, poor creative quality, or broken click tracking."
                ),
                evidence=[
                    Evidence(
                        metric_name="impressions",
                        metric_value=impressions,
                        threshold=MIN_IMPRESSIONS_FOR_ANALYSIS,
                        comparison="above",
                        time_period_days=days,
                        sample_size=impressions,
                    ),
                    Evidence(
                        metric_name="clicks",
                        metric_value=0,
                        threshold=1,
                        comparison="below",
                        time_period_days=days,
                        sample_size=impressions,
                    ),
                    Evidence(
                        metric_name="ctr",
                        metric_value=0,
                        threshold=ZERO_ENGAGEMENT_CTR_THRESHOLD * 100,
                        comparison="below",
                        time_period_days=days,
                        sample_size=impressions,
                    ),
                ],
                impact=Impact(
                    wasted_qps=0,  # Not wasting QPS, wasting spend
                    wasted_queries_daily=0,
                    wasted_spend_usd=spend_usd,
                    percent_of_total_waste=0,
                    potential_savings_monthly=spend_usd * 30 / days,
                ),
                actions=[
                    Action(
                        action_type="pause",
                        target_type="creative",
                        target_id=str(creative_id),
                        target_name=f"Creative #{creative_id}",
                        api_example=f"Pause creative {creative_id} to stop spend waste",
                    ),
                ],
                affected_creatives=[str(creative_id)],
                expires_at=(datetime.utcnow() + timedelta(days=7)).isoformat(),
            )
            recommendations.append(rec)

        return recommendations

    async def _check_low_win_rate(self, days: int) -> list[Recommendation]:
        """Check for creatives with very low win rates."""
        import asyncio

        recommendations: list[Recommendation] = []

        async with self.store._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute("""
                    SELECT
                        c.id,
                        c.format,
                        c.canonical_size,
                        COALESCE(SUM(pm.reached_queries), 0) as queries,
                        COALESCE(SUM(pm.impressions), 0) as impressions,
                        COALESCE(SUM(pm.spend_micros), 0) as spend_micros
                    FROM creatives c
                    LEFT JOIN performance_metrics pm ON c.id = pm.creative_id
                        AND pm.metric_date >= date('now', ?)
                    GROUP BY c.id
                    HAVING queries > 50000
                        AND impressions > 0
                        AND CAST(impressions AS FLOAT) / queries < ?
                """, (f"-{days} days", LOW_WIN_RATE_THRESHOLD))

                return [dict(row) for row in cursor.fetchall()]

            results = await loop.run_in_executor(None, _query)

        for row in results:
            creative_id = row["id"]
            queries = row["queries"]
            impressions = row["impressions"]
            win_rate = impressions / queries if queries > 0 else 0
            daily_queries = queries / days

            rec = Recommendation(
                id=f"low-win-rate-{creative_id}-{uuid.uuid4().hex[:8]}",
                type=RecommendationType.CREATIVE_REVIEW,
                severity=Severity.MEDIUM,
                confidence=Confidence.MEDIUM,
                title=f"Low win rate for creative #{creative_id}",
                description=(
                    f"Creative #{creative_id} has a {win_rate*100:.2f}% win rate "
                    f"({impressions:,} wins from {queries:,} queries). This may indicate "
                    f"bid strategy issues, poor floor price competitiveness, or creative quality problems."
                ),
                evidence=[
                    Evidence(
                        metric_name="win_rate",
                        metric_value=win_rate * 100,
                        threshold=LOW_WIN_RATE_THRESHOLD * 100,
                        comparison="below",
                        time_period_days=days,
                        sample_size=queries,
                    ),
                ],
                impact=Impact(
                    wasted_qps=daily_queries / SECONDS_PER_DAY * (1 - win_rate),
                    wasted_queries_daily=int(daily_queries * (1 - win_rate)),
                    wasted_spend_usd=0,
                    percent_of_total_waste=0,
                    potential_savings_monthly=0,
                ),
                actions=[
                    Action(
                        action_type="review",
                        target_type="creative",
                        target_id=str(creative_id),
                        target_name=f"Creative #{creative_id}",
                        api_example="Review bid strategy and floor prices for this creative",
                    ),
                ],
                affected_creatives=[str(creative_id)],
                expires_at=(datetime.utcnow() + timedelta(days=7)).isoformat(),
            )
            recommendations.append(rec)

        return recommendations

    async def _check_disapproved(self, days: int) -> list[Recommendation]:
        """Check for disapproved creatives still receiving traffic."""
        import asyncio

        recommendations: list[Recommendation] = []

        async with self.store._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute("""
                    SELECT
                        c.id,
                        c.format,
                        c.approval_status,
                        COALESCE(SUM(pm.reached_queries), 0) as queries
                    FROM creatives c
                    LEFT JOIN performance_metrics pm ON c.id = pm.creative_id
                        AND pm.metric_date >= date('now', ?)
                    WHERE c.approval_status IS NOT NULL
                        AND c.approval_status != 'APPROVED'
                    GROUP BY c.id
                    HAVING queries > 0
                """, (f"-{days} days",))

                return [dict(row) for row in cursor.fetchall()]

            results = await loop.run_in_executor(None, _query)

        for row in results:
            creative_id = row["id"]
            approval_status = row["approval_status"]
            queries = row["queries"]
            daily_queries = queries / days

            rec = Recommendation(
                id=f"disapproved-{creative_id}-{uuid.uuid4().hex[:8]}",
                type=RecommendationType.CREATIVE_PAUSE,
                severity=Severity.CRITICAL,
                confidence=Confidence.HIGH,
                title=f"Disapproved creative #{creative_id} receiving traffic",
                description=(
                    f"Creative #{creative_id} has status '{approval_status}' but is still "
                    f"receiving {queries:,} queries. These queries are wasted since the "
                    f"creative cannot win auctions. Pause immediately."
                ),
                evidence=[
                    Evidence(
                        metric_name="approval_status",
                        metric_value=0,  # Not applicable
                        threshold=1,
                        comparison="below",
                        time_period_days=days,
                        sample_size=1,
                    ),
                    Evidence(
                        metric_name="queries",
                        metric_value=queries,
                        threshold=0,
                        comparison="above",
                        time_period_days=days,
                        sample_size=queries,
                    ),
                ],
                impact=Impact(
                    wasted_qps=daily_queries / SECONDS_PER_DAY,
                    wasted_queries_daily=int(daily_queries),
                    wasted_spend_usd=0,
                    percent_of_total_waste=0,
                    potential_savings_monthly=daily_queries * 30 * 0.002 / 1000,
                ),
                actions=[
                    Action(
                        action_type="pause",
                        target_type="creative",
                        target_id=str(creative_id),
                        target_name=f"Creative #{creative_id}",
                        api_example=f"Pause creative {creative_id} immediately",
                    ),
                    Action(
                        action_type="review",
                        target_type="creative",
                        target_id=str(creative_id),
                        target_name=f"Creative #{creative_id}",
                        api_example="Fix disapproval reason and resubmit for approval",
                    ),
                ],
                affected_creatives=[str(creative_id)],
                expires_at=(datetime.utcnow() + timedelta(days=1)).isoformat(),
            )
            recommendations.append(rec)

        return recommendations
