"""
Fraud Detection Analyzer for QPS Optimization.

Identifies suspicious publisher and app patterns that indicate
potential fraud or low-quality inventory.

Detects:
- Publishers with abnormally high CTR (click fraud)
- Publishers with 100% viewability but zero engagement
- Apps/sites with high traffic but zero conversions
- Unusual traffic patterns (bots, data centers)
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

# Fraud detection thresholds
SUSPICIOUSLY_HIGH_CTR = 0.10  # 10% CTR is suspicious
SUSPICIOUSLY_LOW_CTR = 0.00001  # Effectively zero
MIN_IMPRESSIONS_FOR_ANALYSIS = 1000
HIGH_SPEND_ZERO_CONVERSIONS = 50  # $50+ with no conversions is suspicious
SECONDS_PER_DAY = 86400


class FraudAnalyzer:
    """
    Analyzes traffic patterns to detect potential fraud.

    Generates recommendations for:
    - Blocking suspicious publishers
    - Blocking suspicious apps/sites
    - Human review for edge cases
    """

    def __init__(self, db_store: "SQLiteStore"):
        self.store = db_store

    async def analyze(self, days: int = 7) -> list[Recommendation]:
        """
        Run fraud detection analysis and generate recommendations.

        Args:
            days: Number of days of performance data to analyze

        Returns:
            List of Recommendation objects for fraud-related issues
        """
        recommendations: list[Recommendation] = []

        try:
            # Check for click fraud patterns
            click_fraud_recs = await self._check_click_fraud(days)
            recommendations.extend(click_fraud_recs)

            # Check for high spend no conversion placements
            no_conv_recs = await self._check_high_spend_no_conversions(days)
            recommendations.extend(no_conv_recs)

            # Check for suspicious traffic patterns
            suspicious_recs = await self._check_suspicious_patterns(days)
            recommendations.extend(suspicious_recs)

            logger.info(f"Fraud analysis: {len(recommendations)} recommendations")

        except Exception as e:
            logger.error(f"Fraud analysis failed: {e}")

        return recommendations

    async def _check_click_fraud(self, days: int) -> list[Recommendation]:
        """Check for suspiciously high CTR indicating click fraud."""
        import asyncio

        recommendations: list[Recommendation] = []

        async with self.store._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                # Look for placements with abnormally high CTR
                cursor = conn.execute("""
                    SELECT
                        pm.placement as source,
                        COALESCE(SUM(pm.impressions), 0) as impressions,
                        COALESCE(SUM(pm.clicks), 0) as clicks,
                        COALESCE(SUM(pm.spend_micros), 0) as spend_micros,
                        COUNT(DISTINCT pm.creative_id) as creative_count
                    FROM performance_metrics pm
                    WHERE pm.metric_date >= date('now', ?)
                      AND pm.placement IS NOT NULL
                      AND pm.placement != ''
                    GROUP BY pm.placement
                    HAVING impressions > ?
                """, (f"-{days} days", MIN_IMPRESSIONS_FOR_ANALYSIS))

                return [dict(row) for row in cursor.fetchall()]

            results = await loop.run_in_executor(None, _query)

        for row in results:
            source = row["source"]
            impressions = row["impressions"]
            clicks = row["clicks"]
            spend_micros = row["spend_micros"]
            spend_usd = spend_micros / 1_000_000
            ctr = clicks / impressions if impressions > 0 else 0

            # Check for suspiciously high CTR
            if ctr > SUSPICIOUSLY_HIGH_CTR:
                rec = Recommendation(
                    id=f"click-fraud-{hash(source) % 100000}-{uuid.uuid4().hex[:8]}",
                    type=RecommendationType.FRAUD_ALERT,
                    severity=Severity.CRITICAL if spend_usd > 100 else Severity.HIGH,
                    confidence=Confidence.MEDIUM,
                    title=f"Suspicious click rate: {source[:50]}",
                    description=(
                        f"Placement '{source[:80]}' has an abnormally high CTR of {ctr*100:.1f}% "
                        f"({clicks:,} clicks from {impressions:,} impressions). This pattern "
                        f"is consistent with click fraud. Spent ${spend_usd:.2f}. Block immediately."
                    ),
                    evidence=[
                        Evidence(
                            metric_name="ctr",
                            metric_value=ctr * 100,
                            threshold=SUSPICIOUSLY_HIGH_CTR * 100,
                            comparison="above",
                            time_period_days=days,
                            sample_size=impressions,
                        ),
                        Evidence(
                            metric_name="spend_usd",
                            metric_value=spend_usd,
                            threshold=10,
                            comparison="above",
                            time_period_days=days,
                            sample_size=impressions,
                        ),
                    ],
                    impact=Impact(
                        wasted_qps=0,
                        wasted_queries_daily=0,
                        wasted_spend_usd=spend_usd,
                        percent_of_total_waste=0,
                        potential_savings_monthly=spend_usd * 30 / days,
                    ),
                    actions=[
                        Action(
                            action_type="block",
                            target_type="publisher",
                            target_id=source,
                            target_name=f"Publisher: {source[:50]}",
                            pretargeting_field="excluded_publisher_list",
                            api_example=f"Add to publisher exclusion list",
                        ),
                    ],
                    affected_creatives=[],
                    affected_campaigns=[],
                    expires_at=(datetime.utcnow() + timedelta(days=1)).isoformat(),
                )
                recommendations.append(rec)

        return recommendations

    async def _check_high_spend_no_conversions(self, days: int) -> list[Recommendation]:
        """Check for placements with high spend but zero meaningful engagement."""
        import asyncio

        recommendations: list[Recommendation] = []

        async with self.store._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute("""
                    SELECT
                        pm.placement as source,
                        COALESCE(SUM(pm.impressions), 0) as impressions,
                        COALESCE(SUM(pm.clicks), 0) as clicks,
                        COALESCE(SUM(pm.spend_micros), 0) as spend_micros
                    FROM performance_metrics pm
                    WHERE pm.metric_date >= date('now', ?)
                      AND pm.placement IS NOT NULL
                      AND pm.placement != ''
                    GROUP BY pm.placement
                    HAVING spend_micros > ? AND clicks = 0
                """, (f"-{days} days", HIGH_SPEND_ZERO_CONVERSIONS * 1_000_000))

                return [dict(row) for row in cursor.fetchall()]

            results = await loop.run_in_executor(None, _query)

        for row in results:
            source = row["source"]
            impressions = row["impressions"]
            spend_micros = row["spend_micros"]
            spend_usd = spend_micros / 1_000_000

            rec = Recommendation(
                id=f"no-conv-{hash(source) % 100000}-{uuid.uuid4().hex[:8]}",
                type=RecommendationType.PUBLISHER_BLOCK,
                severity=Severity.HIGH if spend_usd > 100 else Severity.MEDIUM,
                confidence=Confidence.HIGH,
                title=f"High spend, zero clicks: {source[:50]}",
                description=(
                    f"Placement '{source[:80]}' has spent ${spend_usd:.2f} on {impressions:,} "
                    f"impressions but received zero clicks. This indicates either bot traffic, "
                    f"non-viewable placements, or fraud. Block this source."
                ),
                evidence=[
                    Evidence(
                        metric_name="spend_usd",
                        metric_value=spend_usd,
                        threshold=HIGH_SPEND_ZERO_CONVERSIONS,
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
                ],
                impact=Impact(
                    wasted_qps=0,
                    wasted_queries_daily=0,
                    wasted_spend_usd=spend_usd,
                    percent_of_total_waste=0,
                    potential_savings_monthly=spend_usd * 30 / days,
                ),
                actions=[
                    Action(
                        action_type="block",
                        target_type="publisher",
                        target_id=source,
                        target_name=f"Publisher: {source[:50]}",
                        pretargeting_field="excluded_publisher_list",
                        api_example="Add to publisher exclusion list",
                    ),
                ],
                affected_creatives=[],
                affected_campaigns=[],
                expires_at=(datetime.utcnow() + timedelta(days=3)).isoformat(),
            )
            recommendations.append(rec)

        return recommendations

    async def _check_suspicious_patterns(self, days: int) -> list[Recommendation]:
        """Check for other suspicious traffic patterns."""
        import asyncio

        recommendations: list[Recommendation] = []

        async with self.store._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                # Look for placements with extremely low CTR (could be bots viewing)
                cursor = conn.execute("""
                    SELECT
                        pm.placement as source,
                        COALESCE(SUM(pm.impressions), 0) as impressions,
                        COALESCE(SUM(pm.clicks), 0) as clicks,
                        COALESCE(SUM(pm.spend_micros), 0) as spend_micros
                    FROM performance_metrics pm
                    WHERE pm.metric_date >= date('now', ?)
                      AND pm.placement IS NOT NULL
                      AND pm.placement != ''
                    GROUP BY pm.placement
                    HAVING impressions > 50000 AND spend_micros > ?
                """, (f"-{days} days", 20 * 1_000_000))  # $20+ spend

                return [dict(row) for row in cursor.fetchall()]

            results = await loop.run_in_executor(None, _query)

        for row in results:
            source = row["source"]
            impressions = row["impressions"]
            clicks = row["clicks"]
            spend_micros = row["spend_micros"]
            spend_usd = spend_micros / 1_000_000
            ctr = clicks / impressions if impressions > 0 else 0

            # Check for suspiciously low CTR with high volume
            if ctr < SUSPICIOUSLY_LOW_CTR:
                rec = Recommendation(
                    id=f"suspicious-{hash(source) % 100000}-{uuid.uuid4().hex[:8]}",
                    type=RecommendationType.FRAUD_ALERT,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.LOW,
                    title=f"Suspicious traffic pattern: {source[:50]}",
                    description=(
                        f"Placement '{source[:80]}' has {impressions:,} impressions with "
                        f"near-zero engagement ({ctr*100:.4f}% CTR). Spent ${spend_usd:.2f}. "
                        f"This could indicate bot traffic or non-viewable inventory. "
                        f"Recommend human review."
                    ),
                    evidence=[
                        Evidence(
                            metric_name="ctr",
                            metric_value=ctr * 100,
                            threshold=SUSPICIOUSLY_LOW_CTR * 100,
                            comparison="below",
                            time_period_days=days,
                            sample_size=impressions,
                        ),
                        Evidence(
                            metric_name="impressions",
                            metric_value=impressions,
                            threshold=50000,
                            comparison="above",
                            time_period_days=days,
                            sample_size=impressions,
                        ),
                    ],
                    impact=Impact(
                        wasted_qps=0,
                        wasted_queries_daily=0,
                        wasted_spend_usd=spend_usd * 0.8,  # Estimate 80% waste
                        percent_of_total_waste=0,
                        potential_savings_monthly=spend_usd * 0.8 * 30 / days,
                    ),
                    actions=[
                        Action(
                            action_type="review",
                            target_type="publisher",
                            target_id=source,
                            target_name=f"Publisher: {source[:50]}",
                            api_example="Human review recommended - check viewability data",
                        ),
                    ],
                    affected_creatives=[],
                    affected_campaigns=[],
                    expires_at=(datetime.utcnow() + timedelta(days=7)).isoformat(),
                )
                recommendations.append(rec)

        return recommendations
