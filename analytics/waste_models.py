"""Data models for RTB waste analysis.

This module defines dataclasses for representing waste analysis results,
including size gaps, coverage metrics, and waste reports.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Literal


@dataclass
class TrafficRecord:
    """A single RTB traffic data point.

    Attributes:
        canonical_size: Normalized size category (e.g., "300x250 (Medium Rectangle)").
        raw_size: Original requested size (e.g., "300x250" or "301x250").
        request_count: Number of bid requests for this size.
        date: Date of the traffic data.
        buyer_id: Optional buyer seat ID.
    """

    canonical_size: str
    raw_size: str
    request_count: int
    date: str
    buyer_id: Optional[str] = None


@dataclass
class SizeGap:
    """A size that is requested but has insufficient creative coverage.

    Attributes:
        canonical_size: Normalized size category.
        request_count: Total bid requests for this size.
        creative_count: Number of creatives available for this size.
        estimated_qps: Estimated queries per second (request_count / seconds_per_day).
        estimated_waste_pct: Percentage of total traffic this gap represents.
        recommendation: Actionable recommendation ("Block", "Add creative", etc.).
        recommendation_detail: Detailed explanation of the recommendation.
        potential_savings_usd: Estimated monthly savings if blocked (rough estimate).
        closest_iab_size: For non-standard sizes, the closest IAB standard.
    """

    canonical_size: str
    request_count: int
    creative_count: int
    estimated_qps: float
    estimated_waste_pct: float
    recommendation: Literal["Block", "Add Creative", "Use Flexible", "Monitor"]
    recommendation_detail: str
    potential_savings_usd: Optional[float] = None
    closest_iab_size: Optional[str] = None


@dataclass
class SizeCoverage:
    """Creative coverage metrics for a single size.

    Attributes:
        canonical_size: Normalized size category.
        creative_count: Number of creatives in inventory.
        request_count: Number of bid requests (0 if no traffic data).
        coverage_status: Coverage level ("good", "low", "none", "excess").
        formats: Breakdown by creative format (HTML, VIDEO, NATIVE).
    """

    canonical_size: str
    creative_count: int
    request_count: int
    coverage_status: Literal["good", "low", "none", "excess", "unknown"]
    formats: dict = field(default_factory=dict)


@dataclass
class WasteReport:
    """Complete waste analysis report for a buyer seat or account.

    Attributes:
        buyer_id: Buyer seat ID (None for all seats).
        total_requests: Total bid requests analyzed.
        total_waste_requests: Requests for sizes with zero creatives.
        waste_percentage: Percentage of requests that are wasted.
        size_gaps: List of size gaps sorted by impact.
        size_coverage: Coverage metrics for all sizes.
        potential_savings_qps: Total QPS that could be saved by blocking.
        potential_savings_usd: Estimated monthly cost savings.
        analysis_period_days: Number of days of traffic analyzed.
        generated_at: Timestamp when report was generated.
        recommendations_summary: High-level summary of recommendations.
    """

    buyer_id: Optional[str]
    total_requests: int
    total_waste_requests: int
    waste_percentage: float
    size_gaps: List[SizeGap]
    size_coverage: List[SizeCoverage]
    potential_savings_qps: float
    potential_savings_usd: Optional[float]
    analysis_period_days: int
    generated_at: str
    recommendations_summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert report to dictionary for JSON serialization."""
        return {
            "buyer_id": self.buyer_id,
            "total_requests": self.total_requests,
            "total_waste_requests": self.total_waste_requests,
            "waste_percentage": round(self.waste_percentage, 2),
            "size_gaps": [
                {
                    "canonical_size": g.canonical_size,
                    "request_count": g.request_count,
                    "creative_count": g.creative_count,
                    "estimated_qps": round(g.estimated_qps, 2),
                    "estimated_waste_pct": round(g.estimated_waste_pct, 2),
                    "recommendation": g.recommendation,
                    "recommendation_detail": g.recommendation_detail,
                    "potential_savings_usd": g.potential_savings_usd,
                    "closest_iab_size": g.closest_iab_size,
                }
                for g in self.size_gaps
            ],
            "size_coverage": [
                {
                    "canonical_size": c.canonical_size,
                    "creative_count": c.creative_count,
                    "request_count": c.request_count,
                    "coverage_status": c.coverage_status,
                    "formats": c.formats,
                }
                for c in self.size_coverage
            ],
            "potential_savings_qps": round(self.potential_savings_qps, 2),
            "potential_savings_usd": self.potential_savings_usd,
            "analysis_period_days": self.analysis_period_days,
            "generated_at": self.generated_at,
            "recommendations_summary": self.recommendations_summary,
        }


@dataclass
class ProblemFormat:
    """A creative with a problem that affects QPS efficiency.

    Phase 22: Problem format detection for identifying creatives that hurt
    campaign performance.

    Attributes:
        creative_id: The creative ID.
        problem_type: Type of problem detected.
        evidence: Supporting data for the problem.
        severity: Problem severity level.
        recommendation: Suggested action to fix.
    """

    creative_id: str
    problem_type: Literal[
        "zero_bids",      # Has reached_queries but no impressions
        "non_standard",   # Size doesn't match any IAB standard
        "low_bid_rate",   # impressions / reached_queries < 1%
        "disapproved",    # approval_status != 'APPROVED'
    ]
    evidence: dict = field(default_factory=dict)
    severity: Literal["high", "medium", "low"] = "medium"
    recommendation: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "creative_id": self.creative_id,
            "problem_type": self.problem_type,
            "evidence": self.evidence,
            "severity": self.severity,
            "recommendation": self.recommendation,
        }
