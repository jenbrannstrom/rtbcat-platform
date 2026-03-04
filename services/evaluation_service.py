"""Evaluation Service - Business logic only, no SQL.

.. deprecated::
    This module is maintained for the /api/evaluation endpoint. For new code,
    use ``analytics.recommendation_engine`` which provides structured
    Recommendation objects with Evidence, Impact, and Action dataclasses.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from storage.postgres_repositories.evaluation_repo import EvaluationRepository

logger = logging.getLogger(__name__)


class RecommendationType(Enum):
    PRETARGETING = "pretargeting"
    ADOPS_ADVICE = "adops_advice"
    OPPORTUNITY = "opportunity"
    CREATIVE_TEAM = "creative_team"


@dataclass
class Recommendation:
    """A single actionable recommendation."""
    type: RecommendationType
    priority: int
    title: str
    description: str
    impact_estimate: str
    config_field: Optional[str] = None
    suggested_value: Optional[str] = None
    current_value: Optional[str] = None
    evidence: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "type": self.type.value,
            "priority": self.priority,
            "title": self.title,
            "description": self.description,
            "impact_estimate": self.impact_estimate,
            "config_field": self.config_field,
            "suggested_value": self.suggested_value,
            "current_value": self.current_value,
            "evidence": self.evidence,
        }


class EvaluationService:
    """Business logic for evaluation - calls repo for data, applies rules."""

    def __init__(self, repo: Optional[EvaluationRepository] = None):
        self.repo = repo or EvaluationRepository()

    def _log_fallback(self, stage: str, days: Optional[int] = None) -> None:
        logger.warning(
            "Evaluation service fallback triggered at %s",
            stage,
            extra={"stage": stage, "days": days},
            exc_info=True,
        )

    async def run_full_evaluation(self, days: int = 7) -> Dict[str, Any]:
        """Run complete evaluation and generate recommendations."""
        results = {
            "recommendations": [],
            "summary": {},
            "data_quality": await self._check_data_quality(days),
            "generated_at": datetime.utcnow().isoformat(),
        }

        if results["data_quality"]["score"] < 0.3:
            results["recommendations"].append(Recommendation(
                type=RecommendationType.ADOPS_ADVICE,
                priority=1,
                title="Insufficient Data",
                description="Need more data to generate accurate recommendations. "
                           f"Missing: {', '.join(results['data_quality']['missing'])}",
                impact_estimate="N/A"
            ))
            results["summary"] = self._generate_summary(results["recommendations"])
            return results

        results["recommendations"].extend(await self._analyze_filtered_bids(days))
        results["recommendations"].extend(await self._analyze_size_coverage(days))
        results["recommendations"].extend(await self._analyze_geo_waste(days))
        results["recommendations"].extend(await self._analyze_publisher_performance(days))
        results["recommendations"].extend(await self._identify_opportunities(days))

        results["recommendations"].sort(key=lambda r: r.priority)
        results["summary"] = self._generate_summary(results["recommendations"])

        return results

    async def _check_data_quality(self, days: int) -> Dict:
        """Check what data sources are available and fresh."""
        quality = {"score": 0, "missing": [], "available": []}

        try:
            perf_count = await self.repo.get_rtb_daily_count(days)
            if perf_count > 0:
                quality["available"].append(f"rtb_daily ({perf_count:,} rows)")
                quality["score"] += 0.4
            else:
                quality["missing"].append("rtb_daily (import CSV)")
        except Exception:
            self._log_fallback("check_data_quality.rtb_daily", days)
            quality["missing"].append("rtb_daily (table missing)")

        try:
            bf_count = await self.repo.get_bid_filtering_count(days)
            if bf_count > 0:
                quality["available"].append(f"rtb_bid_filtering ({bf_count:,} rows)")
                quality["score"] += 0.3
            else:
                quality["missing"].append("rtb_bid_filtering (import CSV)")
        except Exception:
            self._log_fallback("check_data_quality.rtb_bid_filtering", days)
            quality["missing"].append("rtb_bid_filtering (table missing)")

        try:
            creative_count = await self.repo.get_creatives_count()
            if creative_count > 0:
                quality["available"].append(f"creatives ({creative_count:,})")
                quality["score"] += 0.3
            else:
                quality["missing"].append("creatives (run: catscan sync)")
        except Exception:
            self._log_fallback("check_data_quality.creatives")
            quality["missing"].append("creatives (run: catscan sync)")

        return quality

    async def _analyze_filtered_bids(self, days: int) -> List[Recommendation]:
        """Analyze WHY bids are being filtered."""
        recommendations = []

        try:
            filtered = await self.repo.get_filtered_bids_summary(days)
        except Exception:
            self._log_fallback("analyze_filtered_bids", days)
            return recommendations

        for row in filtered:
            reason = row.get("filtering_reason", "UNKNOWN")
            pct = row.get("pct_of_filtered", 0) or 0
            bids = row.get("total_bids", 0) or 0

            # Analyze different filtering reasons
            reason_lower = reason.lower() if reason else ""

            if "manually" in reason_lower and pct > 10:
                recommendations.append(Recommendation(
                    type=RecommendationType.PRETARGETING,
                    priority=2,
                    title=f"Publisher Manual Filter ({pct:.1f}%)",
                    description=f"{bids:,} bids filtered manually by publishers. "
                               "Review which publishers are filtering and consider exclusions.",
                    impact_estimate=f"~{pct:.1f}% QPS affected",
                    evidence={"reason": reason, "bids": bids, "pct": pct}
                ))
            elif "disapproved" in reason_lower or "not approved" in reason_lower:
                if pct > 5:
                    recommendations.append(Recommendation(
                        type=RecommendationType.CREATIVE_TEAM,
                        priority=2,
                        title=f"Creative Approval Issue ({pct:.1f}%)",
                        description=f"{bids:,} bids filtered due to creative approval status. "
                                   "Review pending/disapproved creatives.",
                        impact_estimate=f"~{pct:.1f}% QPS could be recovered",
                        evidence={"reason": reason, "bids": bids, "pct": pct}
                    ))
            elif "vendor" in reason_lower and pct > 5:
                recommendations.append(Recommendation(
                    type=RecommendationType.CREATIVE_TEAM,
                    priority=2,
                    title=f"Unidentifiable Vendor ({pct:.1f}%)",
                    description=f"{bids:,} bids filtered due to unidentifiable vendor. "
                               "Ensure all ad tech vendors are properly declared.",
                    impact_estimate=f"~{pct:.1f}% QPS affected",
                    evidence={"reason": reason, "bids": bids, "pct": pct}
                ))
            elif "category" in reason_lower and pct > 5:
                recommendations.append(Recommendation(
                    type=RecommendationType.ADOPS_ADVICE,
                    priority=3,
                    title=f"Category Exclusion ({pct:.1f}%)",
                    description=f"{bids:,} bids filtered due to product category. "
                               "Review advertiser categories and publisher restrictions.",
                    impact_estimate=f"~{pct:.1f}% QPS affected by category rules",
                    evidence={"reason": reason, "bids": bids, "pct": pct}
                ))

        return recommendations

    async def _analyze_size_coverage(self, days: int) -> List[Recommendation]:
        """Check for size mismatches between traffic and creative inventory."""
        recommendations = []

        try:
            traffic_rows = await self.repo.get_size_traffic(days)
            traffic_sizes = {row["creative_size"]: row for row in traffic_rows}
            creative_sizes = await self.repo.get_creative_sizes()
        except Exception:
            self._log_fallback("analyze_size_coverage", days)
            return recommendations

        for size, data in traffic_sizes.items():
            queries = data.get("reached_queries", 0)
            impressions = data.get("impressions", 0)

            if size not in creative_sizes:
                waste_pct = 100 * (queries - impressions) / queries if queries > 0 else 0
                if queries > 10000 and waste_pct > 90:
                    recommendations.append(Recommendation(
                        type=RecommendationType.PRETARGETING,
                        priority=2,
                        title=f"No Creatives for Size: {size}",
                        description=f"Receiving {queries:,} queries/day for {size} "
                                   f"but you have no creatives. {waste_pct:.0f}% waste.",
                        impact_estimate=f"~{queries:,} QPS could be excluded",
                        config_field="includedCreativeDimensions",
                        suggested_value=f"Ensure {size} is NOT in the include list (or add creatives)",
                        evidence={"size": size, "queries": queries, "waste_pct": waste_pct}
                    ))
            elif size in creative_sizes and queries > 50000:
                win_rate = 100 * impressions / queries if queries > 0 else 0
                if win_rate < 2:
                    recommendations.append(Recommendation(
                        type=RecommendationType.ADOPS_ADVICE,
                        priority=3,
                        title=f"Low Win Rate on {size}",
                        description=f"You have creatives for {size} but only {win_rate:.1f}% win rate. "
                                   f"({queries:,} queries, {impressions:,} wins). "
                                   "Check bid pricing or creative quality for this size.",
                        impact_estimate="Potential improvement with bid/creative optimization",
                        evidence={"size": size, "queries": queries, "win_rate": win_rate}
                    ))

        return recommendations

    async def _analyze_geo_waste(self, days: int) -> List[Recommendation]:
        """Identify geographic regions with high waste."""
        recommendations = []

        try:
            geo_stats = await self.repo.get_geo_waste(days)
        except Exception:
            self._log_fallback("analyze_geo_waste", days)
            return recommendations

        for row in geo_stats:
            country = row.get("country", "Unknown")
            queries = row.get("reached_queries", 0)
            impressions = row.get("impressions", 0)
            waste_pct = row.get("waste_pct", 0) or 0

            if queries > 100000 and waste_pct > 95:
                recommendations.append(Recommendation(
                    type=RecommendationType.PRETARGETING,
                    priority=2,
                    title=f"High Waste from {country} ({waste_pct:.0f}%)",
                    description=f"{queries:,} queries from {country} with only {impressions:,} wins. "
                               f"Consider excluding this geo.",
                    impact_estimate=f"~{queries:,} QPS could be excluded",
                    config_field="geoTargeting.excludedIds",
                    suggested_value=f"Add geo ID for {country}",
                    evidence=row
                ))
            elif queries > 50000 and waste_pct > 80:
                recommendations.append(Recommendation(
                    type=RecommendationType.ADOPS_ADVICE,
                    priority=3,
                    title=f"Review Performance in {country}",
                    description=f"{waste_pct:.0f}% waste in {country} ({queries:,} queries). "
                               "May benefit from geo exclusion or bid adjustment.",
                    impact_estimate="Potential QPS reduction with geo exclusion",
                    evidence=row
                ))

        return recommendations

    async def _analyze_publisher_performance(self, days: int) -> List[Recommendation]:
        """Identify problematic publishers/apps."""
        recommendations = []

        try:
            fraud_signals = await self.repo.get_suspicious_publishers(days)
        except Exception:
            self._log_fallback("analyze_publisher_performance", days)
            return recommendations

        for row in fraud_signals:
            pub_name = row.get("publisher_name") or row.get("publisher_id")
            recommendations.append(Recommendation(
                type=RecommendationType.ADOPS_ADVICE,
                priority=2,
                title=f"Suspicious Publisher: {pub_name}",
                description=f"{row.get('impressions', 0):,} impressions, {row.get('clicks', 0)} clicks "
                           f"({row.get('signal_type')}). Review for potential fraud.",
                impact_estimate="Review and potentially block",
                evidence=row
            ))

        return recommendations

    async def _identify_opportunities(self, days: int) -> List[Recommendation]:
        """Identify opportunities for growth."""
        recommendations = []

        try:
            size_opps = await self.repo.get_high_win_rate_sizes(days)
        except Exception:
            self._log_fallback("identify_opportunities", days)
            return recommendations

        for row in size_opps:
            win_rate = row.get("win_rate", 0) or 0
            queries = row.get("queries", 0)
            size = row.get("creative_size", "Unknown")

            if win_rate > 20 and queries < 50000:
                recommendations.append(Recommendation(
                    type=RecommendationType.OPPORTUNITY,
                    priority=4,
                    title=f"High-Performing Size: {size}",
                    description=f"{win_rate:.0f}% win rate on {size} "
                               f"but only {queries:,} queries. "
                               "Consider increasing QPS allocation for this size.",
                    impact_estimate="Potential revenue growth",
                    evidence=row
                ))

        return recommendations

    def _generate_summary(self, recommendations: List[Recommendation]) -> Dict:
        """Generate executive summary from recommendations."""
        return {
            "total_recommendations": len(recommendations),
            "by_priority": {
                "critical": len([r for r in recommendations if r.priority == 1]),
                "high": len([r for r in recommendations if r.priority == 2]),
                "medium": len([r for r in recommendations if r.priority == 3]),
                "low": len([r for r in recommendations if r.priority in (4, 5)]),
            },
            "by_type": {
                "pretargeting": len([r for r in recommendations if r.type == RecommendationType.PRETARGETING]),
                "adops_advice": len([r for r in recommendations if r.type == RecommendationType.ADOPS_ADVICE]),
                "opportunity": len([r for r in recommendations if r.type == RecommendationType.OPPORTUNITY]),
                "creative_team": len([r for r in recommendations if r.type == RecommendationType.CREATIVE_TEAM]),
            }
        }

    async def get_filtered_bids_summary(self, days: int = 7) -> List[Dict]:
        """Get summary of why bids were filtered."""
        try:
            return await self.repo.get_filtered_bids_summary(days)
        except Exception:
            self._log_fallback("get_filtered_bids_summary", days)
            return []

    async def get_bid_funnel(self, days: int = 7) -> Dict:
        """Get bid funnel from rtb_funnel_daily aggregates."""
        try:
            data = await self.repo.get_bid_funnel_metrics(days)
            totals = {
                "bid_requests": data.get("bid_requests", 0),
                "successful_responses": data.get("successful_responses", 0),
                "bids": data.get("bids", 0),
                "reached_queries": data.get("reached_queries", 0),
                "auctions_won": data.get("auctions_won", 0),
                "impressions": data.get("impressions", 0),
            }

            # Calculate rates
            if totals["bid_requests"] > 0:
                totals["response_rate"] = round(
                    100 * totals["successful_responses"] / totals["bid_requests"], 2
                )
            if totals["bids"] > 0:
                totals["win_rate"] = round(
                    100 * totals["auctions_won"] / totals["bids"], 2
                )
            if totals["reached_queries"] > 0:
                totals["impression_rate"] = round(
                    100 * totals["impressions"] / totals["reached_queries"], 2
                )

            return totals
        except Exception:
            self._log_fallback("get_bid_funnel", days)
            return {
                "bid_requests": 0,
                "successful_responses": 0,
                "bids": 0,
                "reached_queries": 0,
                "auctions_won": 0,
                "impressions": 0,
            }
