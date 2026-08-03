"""
Fraud Detection Analyzer for QPS Optimization.

This is the canonical fraud analyzer for the analytics module. It outputs
structured Recommendation objects with evidence, impact, and actions.

Identifies suspicious publisher and app patterns that indicate
potential fraud or low-quality inventory:
- Publishers with abnormally high CTR (click fraud)
- Publishers with 100% viewability but zero engagement
- Apps/sites with high traffic but zero conversions
- Unusual traffic patterns (bots, data centers)

Related modules:
    - ``qps.fraud_detector.FraudSignalDetector``: CLI-focused detector
      that generates text reports. Maintained for backwards compatibility.

Usage:
    >>> from analytics.fraud_analyzer import FraudAnalyzer
    >>> analyzer = FraudAnalyzer()
    >>> recommendations = await analyzer.analyze(days=14)
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

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

logger = logging.getLogger(__name__)

# Fraud detection thresholds
DEFAULT_SUSPICIOUSLY_HIGH_CTR = 0.10  # 10% CTR default for banner/display
SUSPICIOUSLY_LOW_CTR = 0.00001  # Effectively zero
MIN_IMPRESSIONS_FOR_ANALYSIS = 1000
HIGH_SPEND_ZERO_CONVERSIONS = 50  # $50+ with no conversions is suspicious
SECONDS_PER_DAY = 86400

# Format-aware high-CTR thresholds reduce false positives across inventory types.
SUSPICIOUSLY_HIGH_CTR_BY_FORMAT = {
    "BANNER": 0.10,
    "NATIVE": 0.12,
    "VIDEO": 0.20,
}

FORMAT_ALIASES = {
    "DISPLAY": "BANNER",
    "HTML": "BANNER",
    "HTML5": "BANNER",
}


class FraudAnalyzer:
    """
    Analyzes traffic patterns to detect potential fraud.

    Generates recommendations for:
    - Blocking suspicious publishers
    - Blocking suspicious apps/sites
    - Human review for edge cases
    """

    def __init__(self, db_store: object | None = None):
        self._store = db_store

    async def analyze(self, *, buyer_id: str, days: int = 7) -> list[Recommendation]:
        """
        Run fraud detection analysis and generate recommendations.

        Args:
            days: Number of days of performance data to analyze

        Returns:
            List of Recommendation objects for fraud-related issues
        """
        recommendations: list[Recommendation] = []
        recommendations.extend(
            await self._check_click_fraud(buyer_id=buyer_id, days=days)
        )
        recommendations.extend(
            await self._check_high_spend_no_conversions(
                buyer_id=buyer_id,
                days=days,
            )
        )
        recommendations.extend(
            await self._check_suspicious_patterns(buyer_id=buyer_id, days=days)
        )
        logger.info(
            "Fraud analysis for buyer_id=%s: %d recommendations",
            buyer_id,
            len(recommendations),
        )

        return recommendations

    async def _check_click_fraud(
        self, *, buyer_id: str, days: int
    ) -> list[Recommendation]:
        """Check for suspiciously high CTR indicating click fraud."""
        recommendations: list[Recommendation] = []

        results = await db_query(
            """
            SELECT
                app_name AS source,
                COALESCE(creative_format, 'BANNER') AS creative_format,
                COALESCE(SUM(impressions), 0) AS impressions,
                COALESCE(SUM(clicks), 0) AS clicks,
                COALESCE(SUM(spend_micros), 0) AS spend_micros
            FROM rtb_app_size_daily
            WHERE buyer_account_id = ?
              AND metric_date >= date('now', ?)
              AND app_name != ''
            GROUP BY app_name, COALESCE(creative_format, 'BANNER')
            HAVING COALESCE(SUM(impressions), 0) > ?
        """,
            (buyer_id, f"-{days} days", MIN_IMPRESSIONS_FOR_ANALYSIS),
        )

        for row in results:
            source = row["source"]
            creative_format = self._normalize_creative_format(
                row.get("creative_format")
            )
            impressions = row["impressions"]
            clicks = row["clicks"]
            spend_micros = row["spend_micros"]
            spend_usd = spend_micros / 1_000_000
            ctr = clicks / impressions if impressions > 0 else 0
            high_ctr_threshold = self._high_ctr_threshold_for_format(creative_format)

            # Check for suspiciously high CTR
            if ctr > high_ctr_threshold:
                rec = Recommendation(
                    id=f"click-fraud-{hash(source) % 100000}-{uuid.uuid4().hex[:8]}",
                    type=RecommendationType.FRAUD_ALERT,
                    severity=Severity.CRITICAL if spend_usd > 100 else Severity.HIGH,
                    confidence=Confidence.MEDIUM,
                    title=f"Suspicious click rate ({creative_format}): {source[:50]}",
                    description=(
                        f"App/site '{source[:80]}' has an abnormally high CTR of {ctr * 100:.1f}% "
                        f"for {creative_format} traffic ({clicks:,} clicks from {impressions:,} impressions). "
                        f"This exceeds the {high_ctr_threshold * 100:.1f}% threshold and is consistent "
                        f"with click fraud. Spent ${spend_usd:.2f}. Block immediately."
                    ),
                    evidence=[
                        Evidence(
                            metric_name="ctr",
                            metric_value=ctr * 100,
                            threshold=high_ctr_threshold * 100,
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
                            target_type="app",
                            target_id=source,
                            target_name=f"App/site: {source[:50]}",
                            pretargeting_field="excluded_apps",
                            api_example="Add to app/site exclusion list",
                        ),
                    ],
                    affected_creatives=[],
                    affected_campaigns=[],
                    expires_at=(datetime.now(UTC) + timedelta(days=1)).isoformat(),
                )
                recommendations.append(rec)

        return recommendations

    @staticmethod
    def _normalize_creative_format(format_name: str | None) -> str:
        """Normalize raw creative format labels into threshold buckets."""
        fmt = (format_name or "BANNER").strip().upper()
        return FORMAT_ALIASES.get(fmt, fmt)

    @staticmethod
    def _high_ctr_threshold_for_format(format_name: str | None) -> float:
        """Return high-CTR threshold for the given creative format."""
        normalized = FraudAnalyzer._normalize_creative_format(format_name)
        return SUSPICIOUSLY_HIGH_CTR_BY_FORMAT.get(
            normalized, DEFAULT_SUSPICIOUSLY_HIGH_CTR
        )

    async def _check_high_spend_no_conversions(
        self, *, buyer_id: str, days: int
    ) -> list[Recommendation]:
        """Check for placements with high spend but zero meaningful engagement."""
        recommendations: list[Recommendation] = []

        results = await db_query(
            """
            SELECT
                app_name AS source,
                COALESCE(SUM(impressions), 0) AS impressions,
                COALESCE(SUM(clicks), 0) AS clicks,
                COALESCE(SUM(spend_micros), 0) AS spend_micros
            FROM rtb_app_daily
            WHERE buyer_account_id = ?
              AND metric_date >= date('now', ?)
              AND app_name != ''
            GROUP BY app_name
            HAVING COALESCE(SUM(spend_micros), 0) > ?
               AND COALESCE(SUM(clicks), 0) = 0
        """,
            (
                buyer_id,
                f"-{days} days",
                HIGH_SPEND_ZERO_CONVERSIONS * 1_000_000,
            ),
        )

        for row in results:
            source = row["source"]
            impressions = row["impressions"]
            spend_micros = row["spend_micros"]
            spend_usd = spend_micros / 1_000_000

            rec = Recommendation(
                id=f"no-conv-{hash(source) % 100000}-{uuid.uuid4().hex[:8]}",
                type=RecommendationType.APP_BLOCK,
                severity=Severity.HIGH if spend_usd > 100 else Severity.MEDIUM,
                confidence=Confidence.HIGH,
                title=f"High spend, zero clicks: {source[:50]}",
                description=(
                    f"App/site '{source[:80]}' has spent ${spend_usd:.2f} on {impressions:,} "
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
                        target_type="app",
                        target_id=source,
                        target_name=f"App/site: {source[:50]}",
                        pretargeting_field="excluded_apps",
                        api_example="Add to app/site exclusion list",
                    ),
                ],
                affected_creatives=[],
                affected_campaigns=[],
                expires_at=(datetime.now(UTC) + timedelta(days=3)).isoformat(),
            )
            recommendations.append(rec)

        return recommendations

    async def _check_suspicious_patterns(
        self, *, buyer_id: str, days: int
    ) -> list[Recommendation]:
        """Check for other suspicious traffic patterns."""
        recommendations: list[Recommendation] = []

        results = await db_query(
            """
            SELECT
                app_name AS source,
                COALESCE(SUM(impressions), 0) AS impressions,
                COALESCE(SUM(clicks), 0) AS clicks,
                COALESCE(SUM(spend_micros), 0) AS spend_micros
            FROM rtb_app_daily
            WHERE buyer_account_id = ?
              AND metric_date >= date('now', ?)
              AND app_name != ''
            GROUP BY app_name
            HAVING COALESCE(SUM(impressions), 0) > 50000
               AND COALESCE(SUM(spend_micros), 0) > ?
        """,
            (buyer_id, f"-{days} days", 20 * 1_000_000),
        )

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
                        f"App/site '{source[:80]}' has {impressions:,} impressions with "
                        f"near-zero engagement ({ctr * 100:.4f}% CTR). Spent ${spend_usd:.2f}. "
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
                            target_type="app",
                            target_id=source,
                            target_name=f"App/site: {source[:50]}",
                            api_example="Human review recommended - check viewability data",
                        ),
                    ],
                    affected_creatives=[],
                    affected_campaigns=[],
                    expires_at=(datetime.now(UTC) + timedelta(days=7)).isoformat(),
                )
                recommendations.append(rec)

        return recommendations
