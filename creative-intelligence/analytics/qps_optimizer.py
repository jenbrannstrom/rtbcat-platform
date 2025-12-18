"""QPS Optimizer - JOIN queries for full QPS optimization analysis.

This module provides the QPSOptimizer class that joins data across:
- rtb_funnel (bid pipeline metrics)
- rtb_daily (creative/app performance)
- rtb_bid_filtering (bid filtering reasons)
- rtb_quality (fraud/viewability signals)

These JOIN queries enable AI-driven QPS optimization recommendations.

Usage:
    from analytics.qps_optimizer import QPSOptimizer

    optimizer = QPSOptimizer()
    report = await optimizer.get_full_optimization_report(days=7)
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from storage.database import db_query, db_query_one

logger = logging.getLogger(__name__)


class QPSOptimizer:
    """
    QPS Optimization engine that JOINs funnel + daily + quality data
    to generate actionable QPS recommendations.
    """

    async def get_publisher_waste_ranking(
        self,
        days: int = 7,
        limit: int = 50,
        bidder_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        JOIN funnel + daily on date/country/publisher to rank publishers by waste.

        Returns publishers ranked by QPS waste (bid_requests - auctions_won).
        AI uses this to recommend pretargeting blocks.

        Args:
            days: Number of days to analyze
            limit: Max results to return
            bidder_id: Optional filter by bidder account

        Returns:
            List of publisher waste data with:
            - publisher_id, publisher_name
            - bid_requests, auctions_won, impressions, spend
            - waste_pct (% of bid requests that didn't convert)
        """
        bidder_filter = "AND f.bidder_id = ?" if bidder_id else ""
        params = [f'-{days} days']
        if bidder_id:
            params.append(bidder_id)

        rows = await db_query(f"""
            SELECT
                f.publisher_id,
                f.publisher_name,
                SUM(f.bid_requests) as bid_requests,
                SUM(f.bids) as bids,
                SUM(f.auctions_won) as auctions_won,
                COALESCE(SUM(d.impressions), 0) as impressions,
                COALESCE(SUM(d.spend_micros), 0) as spend_micros,
                CASE
                    WHEN SUM(f.bid_requests) > 0
                    THEN 100.0 * (SUM(f.bid_requests) - SUM(f.auctions_won)) / SUM(f.bid_requests)
                    ELSE 0
                END as waste_pct,
                CASE
                    WHEN SUM(f.bids) > 0
                    THEN 100.0 * SUM(f.auctions_won) / SUM(f.bids)
                    ELSE 0
                END as win_rate_pct
            FROM rtb_funnel f
            LEFT JOIN rtb_daily d ON f.metric_date = d.metric_date
                AND f.country = d.country
                AND f.publisher_id = d.publisher_id
            WHERE f.metric_date >= date('now', ?)
              AND f.publisher_id IS NOT NULL
              {bidder_filter}
            GROUP BY f.publisher_id, f.publisher_name
            ORDER BY waste_pct DESC, bid_requests DESC
            LIMIT ?
        """, (*params, limit))

        return [
            {
                "publisher_id": row["publisher_id"],
                "publisher_name": row["publisher_name"] or row["publisher_id"],
                "bid_requests": row["bid_requests"] or 0,
                "bids": row["bids"] or 0,
                "auctions_won": row["auctions_won"] or 0,
                "impressions": row["impressions"] or 0,
                "spend_usd": (row["spend_micros"] or 0) / 1_000_000,
                "waste_pct": round(row["waste_pct"] or 0, 1),
                "win_rate_pct": round(row["win_rate_pct"] or 0, 1),
            }
            for row in rows
        ]

    async def get_platform_efficiency(
        self,
        days: int = 7,
        bidder_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze efficiency by device platform (Desktop/Mobile/Tablet).

        Returns:
            Dict with platform breakdown:
            - platforms: list of platform stats
            - best_platform: highest win rate platform
            - worst_platform: lowest win rate platform
        """
        bidder_filter = "AND f.bidder_id = ?" if bidder_id else ""
        params = [f'-{days} days']
        if bidder_id:
            params.append(bidder_id)

        rows = await db_query(f"""
            SELECT
                COALESCE(f.platform, 'Unknown') as platform,
                SUM(f.bid_requests) as bid_requests,
                SUM(f.bids) as bids,
                SUM(f.auctions_won) as auctions_won,
                COALESCE(SUM(d.impressions), 0) as impressions,
                COALESCE(SUM(d.spend_micros), 0) as spend_micros,
                CASE
                    WHEN SUM(f.bids) > 0
                    THEN 100.0 * SUM(f.auctions_won) / SUM(f.bids)
                    ELSE 0
                END as win_rate_pct
            FROM rtb_funnel f
            LEFT JOIN rtb_daily d ON f.metric_date = d.metric_date
                AND f.country = d.country
                AND f.platform = d.platform
            WHERE f.metric_date >= date('now', ?)
              {bidder_filter}
            GROUP BY COALESCE(f.platform, 'Unknown')
            ORDER BY bid_requests DESC
        """, params)

        platforms = [
            {
                "platform": row["platform"],
                "bid_requests": row["bid_requests"] or 0,
                "bids": row["bids"] or 0,
                "auctions_won": row["auctions_won"] or 0,
                "impressions": row["impressions"] or 0,
                "spend_usd": (row["spend_micros"] or 0) / 1_000_000,
                "win_rate_pct": round(row["win_rate_pct"] or 0, 1),
            }
            for row in rows
        ]

        best = max(platforms, key=lambda x: x["win_rate_pct"]) if platforms else None
        worst = min(platforms, key=lambda x: x["win_rate_pct"]) if platforms else None

        return {
            "platforms": platforms,
            "best_platform": best["platform"] if best else None,
            "worst_platform": worst["platform"] if worst else None,
        }

    async def get_hourly_patterns(
        self,
        days: int = 7,
        bidder_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Analyze hourly patterns for QPS throttling recommendations.

        Returns:
            List of 24 hourly stats:
            - hour (0-23)
            - bid_requests, bids, auctions_won
            - bid_rate_pct, win_rate_pct
        """
        bidder_filter = "AND bidder_id = ?" if bidder_id else ""
        params = [f'-{days} days']
        if bidder_id:
            params.append(bidder_id)

        rows = await db_query(f"""
            SELECT
                hour,
                SUM(bid_requests) as bid_requests,
                SUM(bids) as bids,
                SUM(auctions_won) as auctions_won,
                SUM(impressions) as impressions,
                CASE
                    WHEN SUM(bid_requests) > 0
                    THEN 100.0 * SUM(bids) / SUM(bid_requests)
                    ELSE 0
                END as bid_rate_pct,
                CASE
                    WHEN SUM(bids) > 0
                    THEN 100.0 * SUM(auctions_won) / SUM(bids)
                    ELSE 0
                END as win_rate_pct
            FROM rtb_funnel
            WHERE metric_date >= date('now', ?)
              AND hour IS NOT NULL
              {bidder_filter}
            GROUP BY hour
            ORDER BY hour
        """, params)

        return [
            {
                "hour": row["hour"],
                "bid_requests": row["bid_requests"] or 0,
                "bids": row["bids"] or 0,
                "auctions_won": row["auctions_won"] or 0,
                "impressions": row["impressions"] or 0,
                "bid_rate_pct": round(row["bid_rate_pct"] or 0, 1),
                "win_rate_pct": round(row["win_rate_pct"] or 0, 1),
            }
            for row in rows
        ]

    async def get_size_coverage_gaps(
        self,
        days: int = 7,
        bidder_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find creative sizes with high demand but low wins.

        Returns:
            Sizes where reached_queries >> impressions (coverage gaps).
            AI uses this to recommend new creative sizes.
        """
        bidder_filter = "AND bidder_id = ?" if bidder_id else ""
        params = [f'-{days} days']
        if bidder_id:
            params.append(bidder_id)

        rows = await db_query(f"""
            SELECT
                creative_size,
                creative_format,
                SUM(reached_queries) as reached_queries,
                SUM(impressions) as impressions,
                SUM(spend_micros) as spend_micros,
                CASE
                    WHEN SUM(reached_queries) > 0
                    THEN 100.0 * SUM(impressions) / SUM(reached_queries)
                    ELSE 0
                END as win_rate_pct
            FROM rtb_daily
            WHERE metric_date >= date('now', ?)
              AND creative_size IS NOT NULL
              {bidder_filter}
            GROUP BY creative_size, creative_format
            HAVING reached_queries > impressions * 2  -- High demand, low wins
            ORDER BY (reached_queries - impressions) DESC
            LIMIT 20
        """, params)

        return [
            {
                "size": row["creative_size"],
                "format": row["creative_format"] or "BANNER",
                "reached_queries": row["reached_queries"] or 0,
                "impressions": row["impressions"] or 0,
                "spend_usd": (row["spend_micros"] or 0) / 1_000_000,
                "win_rate_pct": round(row["win_rate_pct"] or 0, 1),
                "gap_queries": (row["reached_queries"] or 0) - (row["impressions"] or 0),
            }
            for row in rows
        ]

    async def get_pretargeting_efficiency(
        self,
        days: int = 7,
        bidder_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Analyze pretargeting efficiency: inventory_matches vs bid_requests.

        Returns:
            Countries/publishers where pretargeting filters too much (or too little).
            AI uses this to tune pretargeting configs.
        """
        bidder_filter = "AND bidder_id = ?" if bidder_id else ""
        params = [f'-{days} days']
        if bidder_id:
            params.append(bidder_id)

        rows = await db_query(f"""
            SELECT
                country,
                SUM(bid_requests) as bid_requests,
                SUM(inventory_matches) as inventory_matches,
                SUM(reached_queries) as reached_queries,
                SUM(bids) as bids,
                SUM(auctions_won) as auctions_won,
                CASE
                    WHEN SUM(bid_requests) > 0
                    THEN 100.0 * SUM(inventory_matches) / SUM(bid_requests)
                    ELSE 0
                END as pretarget_match_pct,
                CASE
                    WHEN SUM(inventory_matches) > 0
                    THEN 100.0 * SUM(reached_queries) / SUM(inventory_matches)
                    ELSE 0
                END as reach_rate_pct
            FROM rtb_funnel
            WHERE metric_date >= date('now', ?)
              AND country IS NOT NULL
              {bidder_filter}
            GROUP BY country
            ORDER BY bid_requests DESC
            LIMIT 30
        """, params)

        return [
            {
                "country": row["country"],
                "bid_requests": row["bid_requests"] or 0,
                "inventory_matches": row["inventory_matches"] or 0,
                "reached_queries": row["reached_queries"] or 0,
                "bids": row["bids"] or 0,
                "auctions_won": row["auctions_won"] or 0,
                "pretarget_match_pct": round(row["pretarget_match_pct"] or 0, 1),
                "reach_rate_pct": round(row["reach_rate_pct"] or 0, 1),
            }
            for row in rows
        ]

    async def get_bid_filtering_analysis(
        self,
        days: int = 7,
        bidder_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Analyze bid filtering reasons from rtb_bid_filtering table.

        Returns:
            Reasons why bids are filtered, ranked by volume and opportunity cost.
            AI uses this to fix creative policies or publisher issues.
        """
        bidder_filter = "AND bidder_id = ?" if bidder_id else ""
        params = [f'-{days} days']
        if bidder_id:
            params.append(bidder_id)

        rows = await db_query(f"""
            SELECT
                filtering_reason,
                COUNT(DISTINCT country) as countries_affected,
                SUM(bids) as total_bids_filtered,
                SUM(bids_in_auction) as bids_in_auction,
                SUM(opportunity_cost_micros) as opportunity_cost_micros
            FROM rtb_bid_filtering
            WHERE metric_date >= date('now', ?)
              {bidder_filter}
            GROUP BY filtering_reason
            ORDER BY total_bids_filtered DESC
            LIMIT 20
        """, params)

        return [
            {
                "reason": row["filtering_reason"],
                "countries_affected": row["countries_affected"] or 0,
                "bids_filtered": row["total_bids_filtered"] or 0,
                "bids_in_auction": row["bids_in_auction"] or 0,
                "opportunity_cost_usd": (row["opportunity_cost_micros"] or 0) / 1_000_000,
            }
            for row in rows
        ]

    async def get_fraud_risk_publishers(
        self,
        days: int = 7,
        threshold_pct: float = 5.0,
        bidder_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find publishers with high IVT (Invalid Traffic) rates from rtb_quality.

        Returns:
            Publishers with IVT rate > threshold.
            AI uses this to recommend blocking fraudulent publishers.

        Args:
            days: Analysis period
            threshold_pct: IVT rate threshold (default 5%)
            bidder_id: Optional filter
        """
        bidder_filter = "AND bidder_id = ?" if bidder_id else ""
        params = [f'-{days} days', threshold_pct]
        if bidder_id:
            params.append(bidder_id)

        rows = await db_query(f"""
            SELECT
                publisher_id,
                publisher_name,
                SUM(impressions) as impressions,
                SUM(ivt_credited_impressions) as ivt_impressions,
                SUM(pre_filtered_impressions) as pre_filtered,
                CASE
                    WHEN SUM(impressions) > 0
                    THEN 100.0 * SUM(ivt_credited_impressions) / SUM(impressions)
                    ELSE 0
                END as ivt_rate_pct
            FROM rtb_quality
            WHERE metric_date >= date('now', ?)
              {bidder_filter}
            GROUP BY publisher_id, publisher_name
            HAVING ivt_rate_pct > ?
            ORDER BY ivt_rate_pct DESC
            LIMIT 30
        """, params)

        return [
            {
                "publisher_id": row["publisher_id"],
                "publisher_name": row["publisher_name"] or row["publisher_id"],
                "impressions": row["impressions"] or 0,
                "ivt_impressions": row["ivt_impressions"] or 0,
                "pre_filtered": row["pre_filtered"] or 0,
                "ivt_rate_pct": round(row["ivt_rate_pct"] or 0, 2),
                "risk_level": "high" if (row["ivt_rate_pct"] or 0) > 10 else "medium",
            }
            for row in rows
        ]

    async def get_viewability_waste(
        self,
        days: int = 7,
        threshold_pct: float = 50.0,
        bidder_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Find publishers with low viewability but high spend (JOIN quality + daily).

        Returns:
            Publishers with viewability < threshold but significant spend.
            AI uses this to recommend reducing bids on low-viewability inventory.

        Args:
            days: Analysis period
            threshold_pct: Viewability threshold (default 50%)
            bidder_id: Optional filter
        """
        bidder_filter = "AND q.bidder_id = ?" if bidder_id else ""
        params = [f'-{days} days', threshold_pct]
        if bidder_id:
            params.append(bidder_id)

        rows = await db_query(f"""
            SELECT
                q.publisher_id,
                q.publisher_name,
                SUM(q.measurable_impressions) as measurable,
                SUM(q.viewable_impressions) as viewable,
                COALESCE(SUM(d.spend_micros), 0) as spend_micros,
                CASE
                    WHEN SUM(q.measurable_impressions) > 0
                    THEN 100.0 * SUM(q.viewable_impressions) / SUM(q.measurable_impressions)
                    ELSE 0
                END as viewability_pct
            FROM rtb_quality q
            LEFT JOIN rtb_daily d ON q.metric_date = d.metric_date
                AND q.publisher_id = d.publisher_id
            WHERE q.metric_date >= date('now', ?)
              {bidder_filter}
            GROUP BY q.publisher_id, q.publisher_name
            HAVING viewability_pct < ? AND viewability_pct > 0
            ORDER BY spend_micros DESC
            LIMIT 30
        """, params)

        return [
            {
                "publisher_id": row["publisher_id"],
                "publisher_name": row["publisher_name"] or row["publisher_id"],
                "measurable_impressions": row["measurable"] or 0,
                "viewable_impressions": row["viewable"] or 0,
                "spend_usd": (row["spend_micros"] or 0) / 1_000_000,
                "viewability_pct": round(row["viewability_pct"] or 0, 1),
                "wasted_spend_estimate_usd": (row["spend_micros"] or 0) / 1_000_000 * (1 - (row["viewability_pct"] or 0) / 100),
            }
            for row in rows
        ]

    async def get_full_optimization_report(
        self,
        days: int = 7,
        bidder_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate complete QPS optimization report.

        Calls all analysis methods and generates actionable recommendations.

        Returns:
            {
                "summary": {...},
                "recommendations": [...],
                "publisher_waste": [...],
                "platform_efficiency": {...},
                "hourly_patterns": [...],
                "bid_filtering": [...],
                "fraud_risk": [...],
                "viewability_issues": [...]
            }
        """
        # Get all data in parallel (Python 3.11+ taskgroup would be ideal)
        publisher_waste = await self.get_publisher_waste_ranking(days, 30, bidder_id)
        platform_efficiency = await self.get_platform_efficiency(days, bidder_id)
        hourly_patterns = await self.get_hourly_patterns(days, bidder_id)
        size_gaps = await self.get_size_coverage_gaps(days, bidder_id)
        pretargeting = await self.get_pretargeting_efficiency(days, bidder_id)
        bid_filtering = await self.get_bid_filtering_analysis(days, bidder_id)
        fraud_risk = await self.get_fraud_risk_publishers(days, 5.0, bidder_id)
        viewability_issues = await self.get_viewability_waste(days, 50.0, bidder_id)

        # Calculate summary stats
        total_bid_requests = sum(p.get("bid_requests", 0) for p in pretargeting)
        total_auctions_won = sum(p.get("auctions_won", 0) for p in pretargeting)
        overall_efficiency = (total_auctions_won / total_bid_requests * 100) if total_bid_requests > 0 else 0

        # Estimate waste
        wasted_bid_requests = total_bid_requests - total_auctions_won
        estimated_waste_usd = sum(p.get("spend_usd", 0) * (p.get("waste_pct", 0) / 100) for p in publisher_waste[:10])

        # Generate recommendations
        recommendations = []

        # Recommend blocking high-waste publishers
        for pub in publisher_waste[:5]:
            if pub["waste_pct"] > 80 and pub["bid_requests"] > 10000:
                recommendations.append({
                    "type": "block_publisher",
                    "publisher_id": pub["publisher_id"],
                    "publisher_name": pub["publisher_name"],
                    "reason": f"Very high waste ({pub['waste_pct']:.0f}%) with {pub['bid_requests']:,} bid requests",
                    "impact_pct": round(pub["bid_requests"] / max(total_bid_requests, 1) * 100, 1),
                })

        # Recommend new creative sizes for gaps
        for gap in size_gaps[:3]:
            if gap["gap_queries"] > 50000:
                recommendations.append({
                    "type": "add_creative_size",
                    "size": gap["size"],
                    "format": gap["format"],
                    "reason": f"Missing {gap['gap_queries']:,} opportunities",
                    "opportunity_queries": gap["gap_queries"],
                })

        # Recommend blocking fraud publishers
        for fraud in fraud_risk[:3]:
            if fraud["ivt_rate_pct"] > 10:
                recommendations.append({
                    "type": "block_fraud_publisher",
                    "publisher_id": fraud["publisher_id"],
                    "publisher_name": fraud["publisher_name"],
                    "reason": f"High IVT rate ({fraud['ivt_rate_pct']:.1f}%)",
                    "ivt_rate_pct": fraud["ivt_rate_pct"],
                })

        # Recommend reducing bids on low-viewability
        for view in viewability_issues[:3]:
            if view["viewability_pct"] < 30 and view["spend_usd"] > 100:
                recommendations.append({
                    "type": "reduce_bids_viewability",
                    "publisher_id": view["publisher_id"],
                    "publisher_name": view["publisher_name"],
                    "reason": f"Low viewability ({view['viewability_pct']:.0f}%) but ${view['spend_usd']:.0f} spend",
                    "estimated_waste_usd": view["wasted_spend_estimate_usd"],
                })

        # Platform recommendations
        if platform_efficiency.get("best_platform") and platform_efficiency.get("worst_platform"):
            best = platform_efficiency["best_platform"]
            worst = platform_efficiency["worst_platform"]
            platforms = {p["platform"]: p for p in platform_efficiency.get("platforms", [])}
            if best in platforms and worst in platforms:
                best_rate = platforms[best]["win_rate_pct"]
                worst_rate = platforms[worst]["win_rate_pct"]
                if best_rate > worst_rate * 1.5:  # 50% better
                    recommendations.append({
                        "type": "adjust_platform_bids",
                        "best_platform": best,
                        "worst_platform": worst,
                        "reason": f"{best} has {best_rate:.0f}% win rate vs {worst} at {worst_rate:.0f}%",
                        "recommendation": f"Increase bids on {best}, reduce on {worst}",
                    })

        return {
            "generated_at": datetime.now().isoformat(),
            "period_days": days,
            "summary": {
                "total_bid_requests": total_bid_requests,
                "total_auctions_won": total_auctions_won,
                "overall_efficiency_pct": round(overall_efficiency, 1),
                "wasted_bid_requests": wasted_bid_requests,
                "estimated_waste_usd": round(estimated_waste_usd, 2),
            },
            "recommendations": recommendations,
            "publisher_waste": publisher_waste,
            "platform_efficiency": platform_efficiency,
            "hourly_patterns": hourly_patterns,
            "size_gaps": size_gaps,
            "pretargeting_efficiency": pretargeting,
            "bid_filtering": bid_filtering,
            "fraud_risk": fraud_risk,
            "viewability_issues": viewability_issues,
        }
