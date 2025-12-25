"""
Recommendation Engine for QPS Optimization.

This is the brain of Cat-Scan. It analyzes performance data and generates
actionable recommendations with evidence, impact assessment, and confidence scores.

The engine answers: "What QPS is wasted, why, and what specific action should I take?"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from storage.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================

class RecommendationType(Enum):
    """Categories of optimization recommendations."""
    SIZE_MISMATCH = "size_mismatch"           # Block sizes you don't have creatives for
    CONFIG_INEFFICIENCY = "config_inefficiency"  # Tighten pretargeting config
    PUBLISHER_BLOCK = "publisher_block"        # Block fraudulent/wasteful publishers
    APP_BLOCK = "app_block"                    # Block fraudulent/wasteful apps
    GEO_EXCLUSION = "geo_exclusion"            # Exclude wasteful geographies
    CREATIVE_PAUSE = "creative_pause"          # Pause problematic creatives
    CREATIVE_REVIEW = "creative_review"        # Review creative quality (broken video, etc.)
    FRAUD_ALERT = "fraud_alert"                # Human review for suspected fraud


class Severity(Enum):
    """Recommendation severity/urgency."""
    CRITICAL = "critical"  # >10% of total waste, immediate action needed
    HIGH = "high"          # 5-10% of total waste
    MEDIUM = "medium"      # 1-5% of total waste
    LOW = "low"            # <1% of total waste, nice to fix


class Confidence(Enum):
    """How confident we are in the recommendation."""
    HIGH = "high"          # Clear pattern, multiple data points
    MEDIUM = "medium"      # Some evidence, may need verification
    LOW = "low"            # Single data point or edge case


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class Evidence:
    """Supporting data for a recommendation."""
    metric_name: str           # e.g., "waste_rate", "ctr", "vcr"
    metric_value: float        # The actual value
    threshold: float           # The threshold that was exceeded
    comparison: str            # "above", "below", "equals"
    time_period_days: int      # How many days of data
    sample_size: int           # Number of data points
    trend: Optional[str] = None  # "increasing", "decreasing", "stable"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Impact:
    """Quantified impact of the problem."""
    wasted_qps: float              # Queries per second being wasted
    wasted_queries_daily: int      # Absolute daily waste
    wasted_spend_usd: float        # Money wasted (estimated)
    percent_of_total_waste: float  # What % of all waste this represents
    potential_savings_monthly: float  # If fixed, save this much

    def to_dict(self) -> dict:
        return {
            "wasted_qps": round(self.wasted_qps, 2),
            "wasted_queries_daily": self.wasted_queries_daily,
            "wasted_spend_usd": round(self.wasted_spend_usd, 2),
            "percent_of_total_waste": round(self.percent_of_total_waste, 2),
            "potential_savings_monthly": round(self.potential_savings_monthly, 2),
        }


@dataclass
class Action:
    """Specific action to take."""
    action_type: str           # "block", "exclude", "pause", "review", "add"
    target_type: str           # "size", "publisher", "app", "geo", "creative", "config"
    target_id: str             # The specific ID to act on
    target_name: str           # Human-readable name
    pretargeting_field: Optional[str] = None  # Which pretargeting field to modify
    api_example: Optional[str] = None         # Example API call or config change

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Recommendation:
    """A complete optimization recommendation."""
    id: str                            # Unique identifier
    type: RecommendationType
    severity: Severity
    confidence: Confidence

    title: str                         # Short description
    description: str                   # Detailed explanation

    evidence: list[Evidence]           # Supporting data
    impact: Impact                     # Quantified impact
    actions: list[Action]              # What to do

    affected_creatives: list[str] = field(default_factory=list)  # Creative IDs involved
    affected_campaigns: list[str] = field(default_factory=list)  # Campaign IDs involved

    generated_at: str = ""             # ISO timestamp
    expires_at: Optional[str] = None   # When this becomes stale

    # For tracking
    status: str = "new"                # new, acknowledged, resolved, dismissed
    resolved_at: Optional[str] = None
    resolution_notes: Optional[str] = None

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.utcnow().isoformat()

    def to_dict(self) -> dict:
        """Convert recommendation to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "type": self.type.value,
            "severity": self.severity.value,
            "confidence": self.confidence.value,
            "title": self.title,
            "description": self.description,
            "evidence": [e.to_dict() for e in self.evidence],
            "impact": self.impact.to_dict(),
            "actions": [a.to_dict() for a in self.actions],
            "affected_creatives": self.affected_creatives,
            "affected_campaigns": self.affected_campaigns,
            "generated_at": self.generated_at,
            "expires_at": self.expires_at,
            "status": self.status,
            "resolved_at": self.resolved_at,
            "resolution_notes": self.resolution_notes,
        }


# =============================================================================
# Severity Ranking Helper
# =============================================================================

SEVERITY_RANK = {
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}


def severity_rank(severity: Severity) -> int:
    """Get numeric rank for severity comparison."""
    return SEVERITY_RANK.get(severity, 0)


def severity_from_waste_rate(waste_rate: float, daily_queries: int) -> Severity:
    """Determine severity based on waste rate and volume."""
    # High volume + high waste = critical
    if waste_rate > 0.90 and daily_queries > 100000:
        return Severity.CRITICAL
    if waste_rate > 0.80 and daily_queries > 50000:
        return Severity.HIGH
    if waste_rate > 0.70 and daily_queries > 10000:
        return Severity.MEDIUM
    return Severity.LOW


def severity_from_spend(spend_usd: float) -> Severity:
    """Determine severity based on wasted spend."""
    if spend_usd > 1000:
        return Severity.CRITICAL
    if spend_usd > 100:
        return Severity.HIGH
    if spend_usd > 10:
        return Severity.MEDIUM
    return Severity.LOW


# =============================================================================
# Master Recommendation Engine
# =============================================================================

class RecommendationEngine:
    """
    Master orchestrator that runs all analyzers and aggregates recommendations.
    """

    def __init__(self, db_store: "SQLiteStore"):
        self.store = db_store
        self._analyzers = None  # Lazy loaded

    def _get_analyzers(self):
        """Lazy load analyzers to avoid circular imports."""
        if self._analyzers is None:
            from analytics.size_analyzer import SizeAnalyzer
            from analytics.creative_analyzer import CreativeAnalyzer
            from analytics.geo_analyzer import GeoAnalyzer
            from analytics.fraud_analyzer import FraudAnalyzer
            from analytics.config_analyzer import ConfigAnalyzer

            self._analyzers = [
                SizeAnalyzer(self.store),
                CreativeAnalyzer(self.store),
                GeoAnalyzer(self.store),
                FraudAnalyzer(self.store),
                ConfigAnalyzer(self.store),
            ]
        return self._analyzers

    async def generate_recommendations(
        self,
        days: int = 7,
        min_severity: Severity = Severity.LOW,
    ) -> list[Recommendation]:
        """
        Run all analyzers and return consolidated recommendations.

        Args:
            days: Analysis time window
            min_severity: Filter out recommendations below this severity

        Returns:
            List of recommendations sorted by impact
        """
        all_recommendations: list[Recommendation] = []

        for analyzer in self._get_analyzers():
            try:
                logger.info(f"Running analyzer: {analyzer.__class__.__name__}")
                recs = await analyzer.analyze(days)
                logger.info(f"  Found {len(recs)} recommendations")
                all_recommendations.extend(recs)
            except Exception as e:
                logger.error(f"Analyzer {analyzer.__class__.__name__} failed: {e}")

        # Filter by severity
        filtered = [
            r for r in all_recommendations
            if severity_rank(r.severity) >= severity_rank(min_severity)
        ]

        # Sort by impact (highest wasted QPS first)
        filtered.sort(key=lambda r: r.impact.wasted_qps, reverse=True)

        # Deduplicate - same target might appear in multiple recommendations
        # Keep highest severity version
        seen_targets: dict[tuple, Recommendation] = {}
        for r in filtered:
            key = (r.type, r.actions[0].target_id if r.actions else r.id)
            if key not in seen_targets or severity_rank(r.severity) > severity_rank(seen_targets[key].severity):
                seen_targets[key] = r

        return list(seen_targets.values())

    async def get_summary(self, days: int = 7) -> dict:
        """
        Get high-level waste summary.

        Returns:
            Summary dictionary with total waste metrics
        """
        # Get total queries and impressions from performance_metrics
        query = """
            SELECT
                COALESCE(SUM(reached_queries), 0) as total_queries,
                COALESCE(SUM(impressions), 0) as total_impressions,
                COALESCE(SUM(clicks), 0) as total_clicks,
                COALESCE(SUM(spend_micros), 0) as total_spend_micros
            FROM performance_metrics
            WHERE metric_date >= date('now', ?)
        """

        import asyncio
        async with self.store._connection() as conn:
            loop = asyncio.get_event_loop()

            def _query():
                cursor = conn.execute(query, (f"-{days} days",))
                return dict(cursor.fetchone())

            totals = await loop.run_in_executor(None, _query)

        total_queries = totals.get("total_queries", 0) or 0
        total_impressions = totals.get("total_impressions", 0) or 0
        total_spend_micros = totals.get("total_spend_micros", 0) or 0

        waste_queries = total_queries - total_impressions
        waste_rate = waste_queries / total_queries if total_queries > 0 else 0
        wasted_qps = waste_queries / (days * 86400) if days > 0 else 0

        # Get recommendation counts
        recommendations = await self.generate_recommendations(days=days)
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for r in recommendations:
            severity_counts[r.severity.value] += 1

        return {
            "analysis_period_days": days,
            "total_queries": total_queries,
            "total_impressions": total_impressions,
            "total_waste_queries": waste_queries,
            "total_waste_rate": round(waste_rate, 4),
            "total_wasted_qps": round(wasted_qps, 2),
            "total_spend_usd": round(total_spend_micros / 1_000_000, 2),
            "recommendation_count": severity_counts,
            "total_recommendations": len(recommendations),
            "generated_at": datetime.utcnow().isoformat(),
        }

    async def save_recommendation(self, rec: Recommendation) -> None:
        """Save a recommendation to the database for tracking."""
        import json

        query = """
            INSERT OR REPLACE INTO recommendations (
                id, type, severity, confidence, title, description,
                evidence_json, impact_json, actions_json,
                affected_creatives, affected_campaigns,
                status, generated_at, resolved_at, resolution_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        import asyncio
        async with self.store._connection() as conn:
            loop = asyncio.get_event_loop()

            def _save():
                conn.execute(query, (
                    rec.id,
                    rec.type.value,
                    rec.severity.value,
                    rec.confidence.value,
                    rec.title,
                    rec.description,
                    json.dumps([e.to_dict() for e in rec.evidence]),
                    json.dumps(rec.impact.to_dict()),
                    json.dumps([a.to_dict() for a in rec.actions]),
                    json.dumps(rec.affected_creatives),
                    json.dumps(rec.affected_campaigns),
                    rec.status,
                    rec.generated_at,
                    rec.resolved_at,
                    rec.resolution_notes,
                ))
                conn.commit()

            await loop.run_in_executor(None, _save)

    async def resolve_recommendation(
        self,
        rec_id: str,
        notes: Optional[str] = None
    ) -> bool:
        """Mark a recommendation as resolved."""
        query = """
            UPDATE recommendations
            SET status = 'resolved',
                resolved_at = ?,
                resolution_notes = ?
            WHERE id = ?
        """

        import asyncio
        async with self.store._connection() as conn:
            loop = asyncio.get_event_loop()

            def _resolve():
                cursor = conn.execute(query, (
                    datetime.utcnow().isoformat(),
                    notes,
                    rec_id,
                ))
                conn.commit()
                return cursor.rowcount > 0

            return await loop.run_in_executor(None, _resolve)
