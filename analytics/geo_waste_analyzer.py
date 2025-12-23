"""
Analyze geographic QPS waste.

Question: Are we receiving traffic from geos our advertisers don't want?
This helps identify geos that should be excluded from pretargeting.
"""

from dataclasses import dataclass
import sqlite3


@dataclass
class GeoStats:
    """Statistics for a single geography."""
    country_code: str
    country_name: str
    impressions: int
    clicks: int
    spend_usd: float
    ctr: float                   # clicks / impressions
    cpm: float                   # cost per thousand impressions
    creative_count: int          # number of creatives active in this geo
    recommendation: str          # "EXCLUDE", "MONITOR", "OK", "EXPAND"


@dataclass
class GeoWasteSummary:
    """Geographic waste analysis."""
    total_geos: int
    geos_with_traffic: int
    geos_to_exclude: int         # Low performance geos
    geos_to_monitor: int         # Borderline geos
    geos_performing_well: int    # Good geos
    estimated_waste_pct: float   # % of spend in low-performing geos
    total_spend_usd: float
    wasted_spend_usd: float
    geo_breakdown: list[GeoStats]


# Country code to name mapping
COUNTRY_CODES = {
    'UNITED STATES': 'US',
    'INDIA': 'IN',
    'INDONESIA': 'ID',
    'CANADA': 'CA',
    'PHILIPPINES': 'PH',
    'MALAYSIA': 'MY',
    'BRAZIL': 'BR',
    'VIETNAM': 'VN',
    'THAILAND': 'TH',
    'JAPAN': 'JP',
    'MEXICO': 'MX',
    'SOUTH KOREA': 'KR',
    'AUSTRALIA': 'AU',
    'SAUDI ARABIA': 'SA',
    'PERU': 'PE',
    'UNITED KINGDOM': 'GB',
    'GERMANY': 'DE',
    'FRANCE': 'FR',
    'SPAIN': 'ES',
    'ITALY': 'IT',
    'NETHERLANDS': 'NL',
    'SINGAPORE': 'SG',
    'HONG KONG': 'HK',
    'TAIWAN': 'TW',
    'CHINA': 'CN',
}


class GeoWasteAnalyzer:
    """Analyze geographic QPS waste."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def analyze(
        self,
        days: int = 7,
        min_impressions: int = 100,
        low_ctr_threshold: float = 0.5,  # Fraction of average CTR
        low_cpm_threshold: float = 0.3,  # Fraction of average CPM
    ) -> GeoWasteSummary:
        """
        Analyze geographic performance and identify waste.

        Strategy:
        - Geos with CTR significantly below average = potential waste
        - Geos with very low CPM = low value traffic
        - Geos with high spend but low performance = priority to exclude

        Args:
            days: Number of days to analyze
            min_impressions: Minimum impressions to include a geo
            low_ctr_threshold: Geos with CTR below this fraction of average are flagged
            low_cpm_threshold: Geos with CPM below this fraction of average are flagged
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        # Get geo performance
        cursor = conn.execute(f"""
            SELECT
                pm.geography as country,
                SUM(pm.impressions) as impressions,
                SUM(pm.clicks) as clicks,
                SUM(pm.spend_micros) / 1000000.0 as spend_usd,
                COUNT(DISTINCT pm.creative_id) as creative_count
            FROM performance_metrics pm
            WHERE pm.metric_date >= date('now', '-{days} days')
              AND pm.geography IS NOT NULL
              AND pm.geography != ''
            GROUP BY pm.geography
            HAVING SUM(pm.impressions) >= {min_impressions}
            ORDER BY SUM(pm.impressions) DESC
        """)

        geo_data = []
        for row in cursor:
            geo_data.append({
                'country': row['country'],
                'impressions': row['impressions'],
                'clicks': row['clicks'],
                'spend_usd': row['spend_usd'] or 0,
                'creative_count': row['creative_count'],
            })

        conn.close()

        if not geo_data:
            return GeoWasteSummary(
                total_geos=0,
                geos_with_traffic=0,
                geos_to_exclude=0,
                geos_to_monitor=0,
                geos_performing_well=0,
                estimated_waste_pct=0,
                total_spend_usd=0,
                wasted_spend_usd=0,
                geo_breakdown=[],
            )

        # Calculate averages
        total_impressions = sum(g['impressions'] for g in geo_data)
        total_clicks = sum(g['clicks'] for g in geo_data)
        total_spend = sum(g['spend_usd'] for g in geo_data)

        avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        avg_cpm = (total_spend / total_impressions * 1000) if total_impressions > 0 else 0

        # Analyze each geo
        geo_stats = []
        geos_to_exclude = 0
        geos_to_monitor = 0
        geos_performing_well = 0
        wasted_spend = 0

        for geo in geo_data:
            ctr = (geo['clicks'] / geo['impressions'] * 100) if geo['impressions'] > 0 else 0
            cpm = (geo['spend_usd'] / geo['impressions'] * 1000) if geo['impressions'] > 0 else 0

            # Determine recommendation
            ctr_ratio = ctr / avg_ctr if avg_ctr > 0 else 0
            cpm_ratio = cpm / avg_cpm if avg_cpm > 0 else 0

            if ctr_ratio < low_ctr_threshold and geo['spend_usd'] > 10:
                # Low CTR with significant spend - exclude
                recommendation = "EXCLUDE"
                geos_to_exclude += 1
                wasted_spend += geo['spend_usd']
            elif ctr_ratio < low_ctr_threshold or cpm_ratio < low_cpm_threshold:
                # Borderline - monitor
                recommendation = "MONITOR"
                geos_to_monitor += 1
            elif ctr_ratio > 1.5:
                # High performer - could expand
                recommendation = "EXPAND"
                geos_performing_well += 1
            else:
                recommendation = "OK"
                geos_performing_well += 1

            country_code = COUNTRY_CODES.get(geo['country'], geo['country'][:2] if geo['country'] else 'XX')

            geo_stats.append(GeoStats(
                country_code=country_code,
                country_name=geo['country'] or 'Unknown',
                impressions=geo['impressions'],
                clicks=geo['clicks'],
                spend_usd=geo['spend_usd'],
                ctr=ctr,
                cpm=cpm,
                creative_count=geo['creative_count'],
                recommendation=recommendation,
            ))

        # Sort by spend descending (highest impact first)
        geo_stats.sort(key=lambda g: g.spend_usd, reverse=True)

        waste_pct = (wasted_spend / total_spend * 100) if total_spend > 0 else 0

        return GeoWasteSummary(
            total_geos=len(geo_stats),
            geos_with_traffic=len([g for g in geo_stats if g.impressions > 0]),
            geos_to_exclude=geos_to_exclude,
            geos_to_monitor=geos_to_monitor,
            geos_performing_well=geos_performing_well,
            estimated_waste_pct=waste_pct,
            total_spend_usd=total_spend,
            wasted_spend_usd=wasted_spend,
            geo_breakdown=geo_stats,
        )


    def get_pretargeting_geo_config(self, days: int = 7) -> dict:
        """
        Generate recommended geo configuration for pretargeting.

        Returns:
            Dict with 'include' and 'exclude' geo lists.
        """
        summary = self.analyze(days)

        include_geos = []
        exclude_geos = []

        for geo in summary.geo_breakdown:
            if geo.recommendation == "EXCLUDE":
                exclude_geos.append({
                    'code': geo.country_code,
                    'name': geo.country_name,
                    'reason': f"Low CTR ({geo.ctr:.2f}%), wasted ${geo.spend_usd:.2f}",
                })
            elif geo.recommendation in ["OK", "EXPAND"]:
                include_geos.append({
                    'code': geo.country_code,
                    'name': geo.country_name,
                    'impressions': geo.impressions,
                    'ctr': geo.ctr,
                })

        return {
            'include': include_geos,
            'exclude': exclude_geos,
            'estimated_savings_usd': summary.wasted_spend_usd,
        }
