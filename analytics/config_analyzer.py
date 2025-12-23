"""
Pretargeting Configuration Analyzer for QPS Optimization.

Identifies inefficiencies in pretargeting configuration that cause
unnecessary QPS usage.

Analyzes:
- Overly broad targeting (receiving irrelevant traffic)
- Missing exclusions (could filter out waste earlier)
- Format/size mismatches (targeting formats you don't have)
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
HIGH_WASTE_RATE_THRESHOLD = 0.80  # 80% queries not converting to impressions
SECONDS_PER_DAY = 86400
MIN_QUERIES_FOR_ANALYSIS = 10000


class ConfigAnalyzer:
    """
    Analyzes pretargeting configuration efficiency.

    Generates recommendations for:
    - Tightening overly broad targeting
    - Adding missing exclusions
    - Fixing format/size mismatches
    """

    def __init__(self, db_store: "SQLiteStore"):
        self.store = db_store

    async def analyze(self, days: int = 7) -> list[Recommendation]:
        """
        Run configuration efficiency analysis and generate recommendations.

        Args:
            days: Number of days of performance data to analyze

        Returns:
            List of Recommendation objects for config-related issues
        """
        recommendations: list[Recommendation] = []

        try:
            # Check overall waste rate
            overall_recs = await self._check_overall_waste_rate(days)
            recommendations.extend(overall_recs)

            # Check format coverage
            format_recs = await self._check_format_coverage(days)
            recommendations.extend(format_recs)

            # Check device type efficiency
            device_recs = await self._check_device_efficiency(days)
            recommendations.extend(device_recs)

            logger.info(f"Config analysis: {len(recommendations)} recommendations")

        except Exception as e:
            logger.error(f"Config analysis failed: {e}")

        return recommendations

    async def _check_overall_waste_rate(self, days: int) -> list[Recommendation]:
        """Check if overall query-to-impression rate is too low."""
        import asyncio

        recommendations: list[Recommendation] = []

        async with self.store._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute("""
                    SELECT
                        COALESCE(SUM(reached_queries), 0) as total_queries,
                        COALESCE(SUM(impressions), 0) as total_impressions,
                        COALESCE(SUM(spend_micros), 0) as total_spend_micros
                    FROM performance_metrics
                    WHERE metric_date >= date('now', ?)
                """, (f"-{days} days",))

                return dict(cursor.fetchone())

            result = await loop.run_in_executor(None, _query)

        total_queries = result.get("total_queries", 0) or 0
        total_impressions = result.get("total_impressions", 0) or 0

        if total_queries < MIN_QUERIES_FOR_ANALYSIS:
            return recommendations

        waste_rate = 1 - (total_impressions / total_queries) if total_queries > 0 else 0
        daily_queries = total_queries / days
        wasted_daily = daily_queries * waste_rate
        wasted_qps = wasted_daily / SECONDS_PER_DAY

        if waste_rate > HIGH_WASTE_RATE_THRESHOLD:
            rec = Recommendation(
                id=f"high-overall-waste-{uuid.uuid4().hex[:8]}",
                type=RecommendationType.CONFIG_INEFFICIENCY,
                severity=Severity.HIGH if waste_rate > 0.90 else Severity.MEDIUM,
                confidence=Confidence.HIGH,
                title=f"High overall waste rate: {waste_rate*100:.1f}%",
                description=(
                    f"Your pretargeting configuration is receiving {total_queries:,} queries "
                    f"but only winning {total_impressions:,} impressions ({waste_rate*100:.1f}% waste). "
                    f"This suggests overly broad targeting. Consider tightening geo, device, "
                    f"or publisher targeting to reduce wasted QPS."
                ),
                evidence=[
                    Evidence(
                        metric_name="waste_rate",
                        metric_value=waste_rate * 100,
                        threshold=HIGH_WASTE_RATE_THRESHOLD * 100,
                        comparison="above",
                        time_period_days=days,
                        sample_size=total_queries,
                    ),
                    Evidence(
                        metric_name="wasted_qps",
                        metric_value=wasted_qps,
                        threshold=1.0,
                        comparison="above",
                        time_period_days=days,
                        sample_size=total_queries,
                    ),
                ],
                impact=Impact(
                    wasted_qps=wasted_qps,
                    wasted_queries_daily=int(wasted_daily),
                    wasted_spend_usd=0,
                    percent_of_total_waste=100,
                    potential_savings_monthly=wasted_daily * 30 * 0.002 / 1000,
                ),
                actions=[
                    Action(
                        action_type="review",
                        target_type="config",
                        target_id="pretargeting",
                        target_name="Pretargeting Configuration",
                        pretargeting_field="all",
                        api_example="Review and tighten pretargeting config in Authorized Buyers",
                    ),
                ],
                affected_creatives=[],
                affected_campaigns=[],
                expires_at=(datetime.utcnow() + timedelta(days=7)).isoformat(),
            )
            recommendations.append(rec)

        return recommendations

    async def _check_format_coverage(self, days: int) -> list[Recommendation]:
        """Check for format mismatches between traffic and inventory."""
        import asyncio

        recommendations: list[Recommendation] = []

        async with self.store._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                # Get formats we have creatives for
                cursor = conn.execute("""
                    SELECT DISTINCT format
                    FROM creatives
                    WHERE format IS NOT NULL
                """)
                available_formats = {row["format"] for row in cursor.fetchall()}

                # Get traffic by format from performance data
                # Note: This assumes format data is available
                cursor = conn.execute("""
                    SELECT
                        c.format,
                        COALESCE(SUM(pm.reached_queries), 0) as queries,
                        COALESCE(SUM(pm.impressions), 0) as impressions,
                        COUNT(DISTINCT c.id) as creative_count
                    FROM creatives c
                    LEFT JOIN performance_metrics pm ON c.id = pm.creative_id
                        AND pm.metric_date >= date('now', ?)
                    WHERE c.format IS NOT NULL
                    GROUP BY c.format
                """, (f"-{days} days",))

                results = []
                for row in cursor.fetchall():
                    results.append({
                        "format": row["format"],
                        "queries": row["queries"] or 0,
                        "impressions": row["impressions"] or 0,
                        "creative_count": row["creative_count"] or 0,
                    })

                return results, available_formats

            results, available_formats = await loop.run_in_executor(None, _query)

        for row in results:
            fmt = row["format"]
            queries = row["queries"]
            impressions = row["impressions"]
            creative_count = row["creative_count"]

            if queries < MIN_QUERIES_FOR_ANALYSIS:
                continue

            win_rate = impressions / queries if queries > 0 else 0
            daily_queries = queries / days

            # Check for formats with very low win rates
            if win_rate < 0.05 and creative_count < 3:
                rec = Recommendation(
                    id=f"format-coverage-{fmt}-{uuid.uuid4().hex[:8]}",
                    type=RecommendationType.CONFIG_INEFFICIENCY,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.MEDIUM,
                    title=f"Low coverage for {fmt} format",
                    description=(
                        f"Format '{fmt}' has only {creative_count} creative(s) but receives "
                        f"{queries:,} queries ({win_rate*100:.1f}% win rate). "
                        f"Either add more {fmt} creatives or exclude this format from targeting."
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
                            metric_name="win_rate",
                            metric_value=win_rate * 100,
                            threshold=5,
                            comparison="below",
                            time_period_days=days,
                            sample_size=queries,
                        ),
                    ],
                    impact=Impact(
                        wasted_qps=daily_queries * (1 - win_rate) / SECONDS_PER_DAY,
                        wasted_queries_daily=int(daily_queries * (1 - win_rate)),
                        wasted_spend_usd=0,
                        percent_of_total_waste=0,
                        potential_savings_monthly=0,
                    ),
                    actions=[
                        Action(
                            action_type="add",
                            target_type="creative",
                            target_id=fmt,
                            target_name=f"{fmt} creatives",
                            api_example=f"Add more {fmt} format creatives",
                        ),
                        Action(
                            action_type="exclude",
                            target_type="config",
                            target_id=f"format-{fmt}",
                            target_name=f"Exclude {fmt} format",
                            pretargeting_field="excluded_creative_formats",
                            api_example=f"Exclude {fmt} from pretargeting if not needed",
                        ),
                    ],
                    affected_creatives=[],
                    affected_campaigns=[],
                    expires_at=(datetime.utcnow() + timedelta(days=14)).isoformat(),
                )
                recommendations.append(rec)

        return recommendations

    async def _check_device_efficiency(self, days: int) -> list[Recommendation]:
        """Check for device types with poor performance."""
        import asyncio

        recommendations: list[Recommendation] = []

        async with self.store._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute("""
                    SELECT
                        pm.device_type,
                        COALESCE(SUM(pm.reached_queries), 0) as queries,
                        COALESCE(SUM(pm.impressions), 0) as impressions,
                        COALESCE(SUM(pm.clicks), 0) as clicks,
                        COALESCE(SUM(pm.spend_micros), 0) as spend_micros
                    FROM performance_metrics pm
                    WHERE pm.metric_date >= date('now', ?)
                      AND pm.device_type IS NOT NULL
                      AND pm.device_type != ''
                    GROUP BY pm.device_type
                    HAVING queries > ?
                """, (f"-{days} days", MIN_QUERIES_FOR_ANALYSIS))

                return [dict(row) for row in cursor.fetchall()]

            results = await loop.run_in_executor(None, _query)

        for row in results:
            device = row["device_type"]
            queries = row["queries"]
            impressions = row["impressions"]
            clicks = row["clicks"]
            spend_micros = row["spend_micros"]
            spend_usd = spend_micros / 1_000_000

            win_rate = impressions / queries if queries > 0 else 0
            ctr = clicks / impressions if impressions > 0 else 0
            daily_queries = queries / days

            # Check for devices with very low win rate and low CTR
            if win_rate < 0.10 and ctr < 0.001 and spend_usd > 10:
                rec = Recommendation(
                    id=f"device-perf-{device}-{uuid.uuid4().hex[:8]}",
                    type=RecommendationType.CONFIG_INEFFICIENCY,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.MEDIUM,
                    title=f"Poor performance on {device}",
                    description=(
                        f"Device type '{device}' has a {win_rate*100:.1f}% win rate and "
                        f"{ctr*100:.3f}% CTR with ${spend_usd:.2f} spend. Consider excluding "
                        f"this device type or reviewing device-specific creative quality."
                    ),
                    evidence=[
                        Evidence(
                            metric_name="win_rate",
                            metric_value=win_rate * 100,
                            threshold=10,
                            comparison="below",
                            time_period_days=days,
                            sample_size=queries,
                        ),
                        Evidence(
                            metric_name="ctr",
                            metric_value=ctr * 100,
                            threshold=0.1,
                            comparison="below",
                            time_period_days=days,
                            sample_size=impressions,
                        ),
                    ],
                    impact=Impact(
                        wasted_qps=daily_queries * (1 - win_rate) / SECONDS_PER_DAY,
                        wasted_queries_daily=int(daily_queries * (1 - win_rate)),
                        wasted_spend_usd=spend_usd * 0.5,
                        percent_of_total_waste=0,
                        potential_savings_monthly=spend_usd * 0.5 * 30 / days,
                    ),
                    actions=[
                        Action(
                            action_type="exclude",
                            target_type="config",
                            target_id=f"device-{device}",
                            target_name=f"Device: {device}",
                            pretargeting_field="device_types",
                            api_example=f"Exclude {device} from device targeting",
                        ),
                    ],
                    affected_creatives=[],
                    affected_campaigns=[],
                    expires_at=(datetime.utcnow() + timedelta(days=7)).isoformat(),
                )
                recommendations.append(rec)

        return recommendations
