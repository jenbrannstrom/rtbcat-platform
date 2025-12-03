"""
Generate optimal pretargeting configuration recommendations.

Constraint: Only 10 pretargeting configs available per account.
Goal: Maximize QPS efficiency with minimal configs.
"""

from dataclasses import dataclass, field
import sqlite3
from typing import Optional

from .geo_waste_analyzer import COUNTRY_CODES


@dataclass
class PretargetingConfig:
    """A recommended pretargeting configuration."""
    name: str
    description: str
    priority: int  # 1 = highest

    # Size targeting
    included_sizes: list[str] = field(default_factory=list)
    excluded_sizes: list[str] = field(default_factory=list)

    # Geo targeting
    included_geos: list[str] = field(default_factory=list)
    excluded_geos: list[str] = field(default_factory=list)

    # Format targeting
    included_formats: list[str] = field(default_factory=list)

    # Estimated impact
    estimated_impressions: int = 0
    estimated_spend_usd: float = 0
    estimated_waste_reduction_pct: float = 0


@dataclass
class PretargetingRecommendation:
    """Overall pretargeting recommendation."""
    config_limit: int
    configs: list[PretargetingConfig]
    total_estimated_waste_reduction_pct: float
    summary: str


class PretargetingRecommender:
    """Generate optimal pretargeting configs."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def generate_recommendations(
        self,
        days: int = 7,
        max_configs: int = 10,
    ) -> PretargetingRecommendation:
        """
        Analyze traffic and generate optimal pretargeting configs.

        Strategy:
        1. Find all sizes you have approved creatives for
        2. Find all geos with reasonable performance
        3. Group by format (BANNER, VIDEO, NATIVE)
        4. Create configs that maximize coverage with minimal waste
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        configs = []
        priority = 1

        # Get approved creative stats by format
        format_data = {}
        cursor = conn.execute("""
            SELECT
                c.format,
                COUNT(*) as creative_count,
                GROUP_CONCAT(DISTINCT c.canonical_size) as sizes
            FROM creatives c
            WHERE c.approval_status = 'APPROVED'
            GROUP BY c.format
            ORDER BY creative_count DESC
        """)
        for row in cursor:
            format_data[row['format']] = {
                'count': row['creative_count'],
                'sizes': [s for s in (row['sizes'] or '').split(',') if s],
            }

        # Get traffic by format with geo breakdown
        format_traffic = {}
        cursor = conn.execute(f"""
            SELECT
                c.format,
                pm.geography,
                SUM(pm.impressions) as impressions,
                SUM(pm.spend_micros) / 1000000.0 as spend_usd,
                SUM(pm.clicks) as clicks
            FROM performance_metrics pm
            JOIN creatives c ON pm.creative_id = c.id
            WHERE pm.metric_date >= date('now', '-{days} days')
              AND pm.geography IS NOT NULL
            GROUP BY c.format, pm.geography
            ORDER BY impressions DESC
        """)

        for row in cursor:
            fmt = row['format']
            if fmt not in format_traffic:
                format_traffic[fmt] = {
                    'total_impressions': 0,
                    'total_spend': 0,
                    'geos': {},
                }
            format_traffic[fmt]['total_impressions'] += row['impressions']
            format_traffic[fmt]['total_spend'] += row['spend_usd'] or 0
            format_traffic[fmt]['geos'][row['geography']] = {
                'impressions': row['impressions'],
                'spend': row['spend_usd'] or 0,
                'clicks': row['clicks'],
            }

        # Calculate average CTR per format
        total_impressions = 0
        total_clicks = 0
        cursor = conn.execute(f"""
            SELECT SUM(impressions) as imps, SUM(clicks) as clicks
            FROM performance_metrics
            WHERE metric_date >= date('now', '-{days} days')
        """)
        row = cursor.fetchone()
        if row:
            total_impressions = row['imps'] or 0
            total_clicks = row['clicks'] or 0
        avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0

        conn.close()

        # Determine geos to include (good performance) and exclude (poor performance)
        good_geos = set()
        bad_geos = set()

        for fmt, traffic in format_traffic.items():
            for geo, stats in traffic['geos'].items():
                if stats['impressions'] < 100:
                    continue
                ctr = (stats['clicks'] / stats['impressions'] * 100) if stats['impressions'] > 0 else 0
                if ctr < avg_ctr * 0.5 and stats['spend'] > 10:
                    # Low CTR with significant spend
                    bad_geos.add(geo)
                elif ctr >= avg_ctr * 0.8:
                    # Good CTR
                    good_geos.add(geo)

        # Remove any geo that's in both (edge case)
        good_geos -= bad_geos

        # Generate configs by format
        for fmt in sorted(format_data.keys(), key=lambda f: format_data[f]['count'], reverse=True):
            if priority > max_configs:
                break

            traffic = format_traffic.get(fmt, {})
            sizes = format_data[fmt]['sizes']

            # Get country codes
            include_geo_codes = []
            for geo in good_geos:
                code = COUNTRY_CODES.get(geo, geo[:2] if geo else 'XX')
                include_geo_codes.append(code)

            exclude_geo_codes = []
            for geo in bad_geos:
                code = COUNTRY_CODES.get(geo, geo[:2] if geo else 'XX')
                exclude_geo_codes.append(code)

            configs.append(PretargetingConfig(
                name=f"{fmt.title()} - Primary Traffic",
                description=f"Target {fmt.lower()} traffic from high-performing geos. {format_data[fmt]['count']} approved creatives.",
                priority=priority,
                included_sizes=sizes[:20] if sizes else [],
                excluded_sizes=[],
                included_geos=sorted(include_geo_codes)[:20],
                excluded_geos=sorted(exclude_geo_codes),
                included_formats=[fmt],
                estimated_impressions=traffic.get('total_impressions', 0),
                estimated_spend_usd=traffic.get('total_spend', 0),
                estimated_waste_reduction_pct=len(bad_geos) / (len(good_geos) + len(bad_geos)) * 100 if (good_geos or bad_geos) else 0,
            ))
            priority += 1

        # Add catch-all config if room
        if priority <= max_configs and len(format_data) > 1:
            all_formats = list(format_data.keys())
            include_geo_codes = sorted([COUNTRY_CODES.get(g, g[:2]) for g in good_geos])[:20]

            configs.append(PretargetingConfig(
                name="Catch-All - All Formats",
                description=f"Catch remaining traffic across all {len(all_formats)} formats.",
                priority=priority,
                included_sizes=[],  # Accept all sizes
                included_geos=include_geo_codes,
                excluded_geos=sorted([COUNTRY_CODES.get(g, g[:2]) for g in bad_geos]),
                included_formats=all_formats,
                estimated_impressions=sum(t.get('total_impressions', 0) for t in format_traffic.values()),
                estimated_spend_usd=sum(t.get('total_spend', 0) for t in format_traffic.values()),
            ))

        # Calculate total waste reduction
        total_waste_reduction = 0
        if bad_geos and (good_geos or bad_geos):
            total_waste_reduction = len(bad_geos) / (len(good_geos) + len(bad_geos)) * 100

        # Generate summary
        summary_parts = []
        if configs:
            summary_parts.append(f"{len(configs)} pretargeting configs recommended")
        if bad_geos:
            summary_parts.append(f"Exclude {len(bad_geos)} underperforming geos")
        if good_geos:
            summary_parts.append(f"Target {len(good_geos)} high-performing geos")

        return PretargetingRecommendation(
            config_limit=max_configs,
            configs=configs,
            total_estimated_waste_reduction_pct=total_waste_reduction,
            summary=". ".join(summary_parts) + "." if summary_parts else "No recommendations available.",
        )

    def get_config_as_json(self, config: PretargetingConfig) -> dict:
        """Convert a config to JSON-serializable format for API response."""
        return {
            'name': config.name,
            'description': config.description,
            'priority': config.priority,
            'targeting': {
                'formats': config.included_formats,
                'sizes': {
                    'included': config.included_sizes[:10],  # First 10 for display
                    'total_count': len(config.included_sizes),
                },
                'geos': {
                    'included': config.included_geos[:10],
                    'excluded': config.excluded_geos,
                    'included_count': len(config.included_geos),
                },
            },
            'estimated_impact': {
                'impressions': config.estimated_impressions,
                'spend_usd': round(config.estimated_spend_usd, 2),
                'waste_reduction_pct': round(config.estimated_waste_reduction_pct, 1),
            },
        }
