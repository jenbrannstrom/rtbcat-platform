"""
Evaluation Engine

Combines:
- Performance data (CSV imports)
- Troubleshooting metrics (API)
- Creative inventory (API)

Produces:
- Pretargeting recommendations
- AdOps advice
- Opportunity identification

This is the BRAIN of Cat-Scan - where data becomes decisions.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime
import sqlite3
from pathlib import Path
import json
import logging

from collectors.troubleshooting import CREATIVE_STATUS_CODES, CALLOUT_STATUS_CODES

logger = logging.getLogger(__name__)


class RecommendationType(Enum):
    PRETARGETING = "pretargeting"     # Actionable config change
    ADOPS_ADVICE = "adops_advice"      # Needs human review
    OPPORTUNITY = "opportunity"        # Potential improvement
    CREATIVE_TEAM = "creative_team"    # Needs creative changes


@dataclass
class Recommendation:
    """A single actionable recommendation."""
    type: RecommendationType
    priority: int                      # 1 (critical) to 5 (nice-to-have)
    title: str
    description: str
    impact_estimate: str               # e.g., "~15% QPS reduction"

    # For pretargeting changes
    config_field: Optional[str] = None
    suggested_value: Optional[str] = None
    current_value: Optional[str] = None

    # Supporting data
    evidence: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
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


class EvaluationEngine:
    """
    Combines all data sources to generate actionable insights.

    Philosophy: Intelligence without assumptions. Facts that drive action.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path.home() / ".catscan" / "catscan.db"

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def run_full_evaluation(self, days: int = 7) -> Dict[str, Any]:
        """
        Run complete evaluation and generate recommendations.

        Returns:
            {
                "summary": {...},
                "recommendations": [...],
                "data_quality": {...},
                "generated_at": "..."
            }
        """
        results = {
            "recommendations": [],
            "summary": {},
            "data_quality": self._check_data_quality(days),
            "generated_at": datetime.utcnow().isoformat(),
        }

        # Only proceed if we have sufficient data
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

        # Run each analysis module
        results["recommendations"].extend(self._analyze_filtered_bids(days))
        results["recommendations"].extend(self._analyze_size_coverage(days))
        results["recommendations"].extend(self._analyze_geo_waste(days))
        results["recommendations"].extend(self._analyze_publisher_performance(days))
        results["recommendations"].extend(self._identify_opportunities(days))

        # Sort by priority
        results["recommendations"].sort(key=lambda r: r.priority)

        # Generate summary
        results["summary"] = self._generate_summary(results["recommendations"])

        return results

    def _check_data_quality(self, days: int) -> Dict:
        """Check what data sources are available and fresh."""
        quality = {
            "score": 0,
            "missing": [],
            "available": [],
        }

        conn = self._get_connection()
        cursor = conn.cursor()

        # Check performance data
        try:
            cursor.execute(f"""
                SELECT COUNT(*) FROM rtb_daily
                WHERE metric_date >= date('now', '-{days} days')
            """)
            perf_count = cursor.fetchone()[0]
            if perf_count > 0:
                quality["available"].append(f"rtb_daily ({perf_count:,} rows)")
                quality["score"] += 0.4
            else:
                quality["missing"].append("rtb_daily (import CSV)")
        except:
            quality["missing"].append("rtb_daily (table missing)")

        # Check troubleshooting data
        try:
            cursor.execute(f"""
                SELECT COUNT(*) FROM troubleshooting_data
                WHERE collection_date >= date('now', '-{days} days')
            """)
            ts_count = cursor.fetchone()[0]
            if ts_count > 0:
                quality["available"].append(f"troubleshooting_data ({ts_count:,} rows)")
                quality["score"] += 0.3
            else:
                quality["missing"].append("troubleshooting_data (run: catscan troubleshoot collect)")
        except:
            quality["missing"].append("troubleshooting_data (run: catscan troubleshoot collect)")

        # Check creative inventory
        try:
            cursor.execute("SELECT COUNT(*) FROM creatives")
            creative_count = cursor.fetchone()[0]
            if creative_count > 0:
                quality["available"].append(f"creatives ({creative_count:,})")
                quality["score"] += 0.3
            else:
                quality["missing"].append("creatives (run: catscan sync)")
        except:
            quality["missing"].append("creatives (run: catscan sync)")

        conn.close()
        return quality

    def _analyze_filtered_bids(self, days: int) -> List[Recommendation]:
        """
        Analyze WHY bids are being filtered.

        This is the most valuable analysis from Troubleshooting API.
        """
        recommendations = []

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(f"""
                SELECT
                    status_name,
                    SUM(bid_count) as total_bids,
                    SUM(impression_count) as total_impressions,
                    ROUND(100.0 * SUM(bid_count) /
                        (SELECT SUM(bid_count) FROM troubleshooting_data
                         WHERE metric_type = 'filtered_bids'
                         AND collection_date >= date('now', '-{days} days')), 2) as pct_of_filtered
                FROM troubleshooting_data
                WHERE metric_type = 'filtered_bids'
                  AND collection_date >= date('now', '-{days} days')
                GROUP BY status_name
                ORDER BY total_bids DESC
            """)
            filtered = [dict(row) for row in cursor.fetchall()]
        except:
            filtered = []

        conn.close()

        if not filtered:
            return recommendations

        for row in filtered:
            status = row.get("status_name", "UNKNOWN")
            pct = row.get("pct_of_filtered", 0) or 0
            bids = row.get("total_bids", 0) or 0

            # Creative not approved - high priority
            if status == "CREATIVE_NOT_APPROVED" and pct > 10:
                recommendations.append(Recommendation(
                    type=RecommendationType.ADOPS_ADVICE,
                    priority=1,
                    title=f"Creative Approval Issue ({pct}% of filtered)",
                    description=f"{bids:,} bids filtered because creatives not approved. "
                               "Review pending creative approvals in Authorized Buyers UI.",
                    impact_estimate=f"~{pct}% QPS could be recovered",
                    evidence={"status": status, "bids": bids, "pct": pct}
                ))

            # Creative disapproved - needs creative team
            elif status == "CREATIVE_DISAPPROVED" and pct > 5:
                recommendations.append(Recommendation(
                    type=RecommendationType.CREATIVE_TEAM,
                    priority=2,
                    title=f"Disapproved Creatives ({pct}% of filtered)",
                    description=f"{bids:,} bids filtered due to disapproved creatives. "
                               "Review disapproval reasons and update creative content.",
                    impact_estimate=f"~{pct}% QPS could be recovered with fixes",
                    evidence={"status": status, "bids": bids, "pct": pct}
                ))

            # Bid below floor - pricing issue
            elif "FLOOR" in status.upper() and pct > 15:
                recommendations.append(Recommendation(
                    type=RecommendationType.ADOPS_ADVICE,
                    priority=2,
                    title=f"Bids Below Floor Price ({pct}% of filtered)",
                    description=f"{bids:,} bids rejected for being below floor. "
                               "Consider increasing bid prices or excluding high-floor inventory.",
                    impact_estimate=f"Bidder adjustment could win {pct}% more",
                    evidence={"status": status, "bids": bids, "pct": pct}
                ))

        return recommendations

    def _analyze_size_coverage(self, days: int) -> List[Recommendation]:
        """
        Check for size mismatches between traffic and creative inventory.
        """
        recommendations = []

        conn = self._get_connection()
        cursor = conn.cursor()

        # Get sizes we receive traffic for
        try:
            cursor.execute(f"""
                SELECT creative_size,
                       SUM(reached_queries) as reached_queries,
                       SUM(impressions) as impressions
                FROM rtb_daily
                WHERE metric_date >= date('now', '-{days} days')
                  AND creative_size IS NOT NULL
                GROUP BY creative_size
                HAVING reached_queries > 1000
                ORDER BY reached_queries DESC
            """)
            traffic_sizes = {row["creative_size"]: dict(row) for row in cursor.fetchall()}
        except:
            traffic_sizes = {}

        # Get sizes we have creatives for
        try:
            cursor.execute("SELECT DISTINCT canonical_size FROM creatives WHERE canonical_size IS NOT NULL")
            creative_sizes = set(row["canonical_size"] for row in cursor.fetchall())
        except:
            creative_sizes = set()

        conn.close()

        # Find mismatches
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

            # Find underutilized sizes (opportunity)
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

    def _analyze_geo_waste(self, days: int) -> List[Recommendation]:
        """
        Identify geographic regions with high waste.
        """
        recommendations = []

        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(f"""
                SELECT country,
                       SUM(reached_queries) as reached_queries,
                       SUM(impressions) as impressions,
                       ROUND(100.0 * (SUM(reached_queries) - SUM(impressions)) /
                             NULLIF(SUM(reached_queries), 0), 2) as waste_pct
                FROM rtb_daily
                WHERE metric_date >= date('now', '-{days} days')
                  AND country IS NOT NULL
                GROUP BY country
                HAVING reached_queries > 10000
                ORDER BY waste_pct DESC
            """)
            geo_stats = [dict(row) for row in cursor.fetchall()]
        except:
            geo_stats = []

        conn.close()

        for row in geo_stats:
            country = row.get("country", "Unknown")
            queries = row.get("reached_queries", 0)
            impressions = row.get("impressions", 0)
            waste_pct = row.get("waste_pct", 0) or 0

            # High-volume countries with extreme waste
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

            # Medium waste - flag for review
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

    def _analyze_publisher_performance(self, days: int) -> List[Recommendation]:
        """
        Identify problematic publishers/apps.
        """
        recommendations = []

        conn = self._get_connection()
        cursor = conn.cursor()

        # High traffic, zero engagement (potential fraud)
        try:
            cursor.execute(f"""
                SELECT publisher_id, publisher_name,
                       SUM(impressions) as impressions,
                       SUM(clicks) as clicks,
                       'high_traffic_zero_clicks' as signal_type
                FROM rtb_daily
                WHERE metric_date >= date('now', '-{days} days')
                  AND publisher_id IS NOT NULL
                GROUP BY publisher_id
                HAVING impressions > 10000 AND clicks = 0
                ORDER BY impressions DESC
                LIMIT 10
            """)
            fraud_signals = [dict(row) for row in cursor.fetchall()]
        except:
            fraud_signals = []

        conn.close()

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

    def _identify_opportunities(self, days: int) -> List[Recommendation]:
        """
        Identify opportunities for growth, not just waste reduction.
        """
        recommendations = []

        conn = self._get_connection()
        cursor = conn.cursor()

        # Find sizes with high win rate but low volume (could increase allocation)
        try:
            cursor.execute(f"""
                SELECT creative_size,
                       SUM(reached_queries) as queries,
                       SUM(impressions) as impressions,
                       ROUND(100.0 * SUM(impressions) / NULLIF(SUM(reached_queries), 0), 2) as win_rate
                FROM rtb_daily
                WHERE metric_date >= date('now', '-{days} days')
                  AND creative_size IS NOT NULL
                GROUP BY creative_size
                HAVING queries > 1000 AND win_rate > 20
                ORDER BY win_rate DESC
                LIMIT 5
            """)
            size_opps = [dict(row) for row in cursor.fetchall()]
        except:
            size_opps = []

        conn.close()

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

    def get_filtered_bids_summary(self, days: int = 7) -> List[Dict]:
        """Get summary of why bids were filtered."""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(f"""
                SELECT
                    status_name,
                    SUM(bid_count) as total_bids,
                    SUM(impression_count) as total_impressions,
                    ROUND(100.0 * SUM(bid_count) /
                        (SELECT SUM(bid_count) FROM troubleshooting_data
                         WHERE metric_type = 'filtered_bids'
                         AND collection_date >= date('now', '-{days} days')), 2) as pct_of_filtered
                FROM troubleshooting_data
                WHERE metric_type = 'filtered_bids'
                  AND collection_date >= date('now', '-{days} days')
                GROUP BY status_name
                ORDER BY total_bids DESC
            """)
            result = [dict(row) for row in cursor.fetchall()]
        except:
            result = []

        conn.close()
        return result

    def get_bid_funnel(self, days: int = 7) -> Dict:
        """Get bid funnel by parsing raw_data from bid_metrics rows."""
        conn = self._get_connection()
        cursor = conn.cursor()

        totals = {
            "bids_submitted": 0,
            "bids_in_auction": 0,
            "impressions_won": 0,
            "billed_impressions": 0,
            "viewable_impressions": 0
        }

        try:
            cursor.execute(f"""
                SELECT raw_data
                FROM troubleshooting_data
                WHERE metric_type = 'bid_metrics'
                  AND collection_date >= date('now', '-{days} days')
            """)

            for row in cursor.fetchall():
                try:
                    data = json.loads(row["raw_data"])
                    totals["bids_submitted"] += int(data.get("bids", {}).get("value", 0))
                    totals["bids_in_auction"] += int(data.get("bidsInAuction", {}).get("value", 0))
                    totals["impressions_won"] += int(data.get("impressionsWon", {}).get("value", 0))
                    totals["billed_impressions"] += int(data.get("billedImpressions", {}).get("value", 0))
                    totals["viewable_impressions"] += int(data.get("viewableImpressions", {}).get("value", 0))
                except:
                    pass
        except:
            pass

        conn.close()

        # Derived rates
        if totals["bids_submitted"]:
            totals["to_auction_rate"] = round(100 * totals["bids_in_auction"] / totals["bids_submitted"], 2)
        if totals["bids_in_auction"]:
            totals["win_rate"] = round(100 * totals["impressions_won"] / totals["bids_in_auction"], 2)

        return totals
