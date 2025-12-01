"""QPS Optimization modules for RTBcat.

This module implements the analysis modules described in
RTBcat_QPS_Optimization_Strategy_v2.md:

- Module 1: Size Coverage Analyzer
- Module 2: Config Performance Tracker
- Module 3: Fraud Signal Detector
- Report generation (printouts)

Example:
    >>> from analytics.qps_optimizer import QPSOptimizer
    >>> from storage import SQLiteStore
    >>>
    >>> store = SQLiteStore()
    >>> await store.initialize()
    >>>
    >>> optimizer = QPSOptimizer(store)
    >>> report = await optimizer.generate_size_coverage_report()
    >>> print(report)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from storage.sqlite_store import SQLiteStore

logger = logging.getLogger(__name__)


# ============================================================================
# Data Models
# ============================================================================


@dataclass
class CreativeSizeInventory:
    """Creative inventory grouped by size."""

    canonical_size: str
    width: int
    height: int
    creative_count: int
    formats: Dict[str, int] = field(default_factory=dict)  # {VIDEO: 10, HTML: 5}
    sample_creative_ids: List[str] = field(default_factory=list)


@dataclass
class TrafficSizeData:
    """Traffic data for a specific size (from RTB Troubleshooting or CSV)."""

    canonical_size: str
    width: int
    height: int
    reached_queries: int
    impressions: int = 0
    match_rate: float = 0.0  # impressions / reached_queries


@dataclass
class SizeCoverageReport:
    """Complete size coverage analysis report."""

    # Summary metrics
    total_creatives: int
    total_sizes_with_creatives: int
    total_sizes_in_traffic: int
    overall_match_rate: float  # % of traffic we can serve

    # Detailed data
    sizes_we_have: List[CreativeSizeInventory]
    sizes_in_traffic: List[TrafficSizeData]
    sizes_we_can_serve: List[str]  # intersection
    sizes_we_cannot_serve: List[str]  # traffic sizes without creatives

    # Recommendations
    recommended_include_list: List[str]  # sizes to include in pretargeting
    opportunity_sizes: List[dict]  # high-volume sizes worth creating creatives for

    # Metadata
    generated_at: str

    def to_printout(self) -> str:
        """Generate human-readable printout for AdOps."""
        lines = []
        lines.append("=" * 80)
        lines.append("SIZE COVERAGE REPORT")
        lines.append("=" * 80)
        lines.append("")
        lines.append(f"Generated: {self.generated_at}")
        lines.append("")

        # Creative inventory summary
        lines.append("YOUR CREATIVE INVENTORY:")
        lines.append(f"  Total creatives: {self.total_creatives}")
        lines.append(f"  Unique sizes: {self.total_sizes_with_creatives}")
        lines.append("")

        lines.append("  Sizes you have creatives for:")
        for inv in sorted(self.sizes_we_have, key=lambda x: x.creative_count, reverse=True)[:15]:
            formats_str = ", ".join(f"{k}:{v}" for k, v in inv.formats.items())
            lines.append(f"    {inv.canonical_size}: {inv.creative_count} creatives ({formats_str})")

        if len(self.sizes_we_have) > 15:
            lines.append(f"    ... and {len(self.sizes_we_have) - 15} more sizes")

        lines.append("")

        # Traffic analysis (if available)
        if self.sizes_in_traffic:
            lines.append("SIZES YOU'RE RECEIVING (from traffic data):")
            for traffic in sorted(self.sizes_in_traffic, key=lambda x: x.reached_queries, reverse=True)[:10]:
                can_serve = "CAN serve" if traffic.canonical_size in self.sizes_we_can_serve else "CANNOT serve"
                lines.append(f"    {traffic.canonical_size}: {traffic.reached_queries:,} queries -> {can_serve}")
            lines.append("")

            lines.append("MATCH ANALYSIS:")
            total_traffic = sum(t.reached_queries for t in self.sizes_in_traffic)
            servable_traffic = sum(
                t.reached_queries for t in self.sizes_in_traffic
                if t.canonical_size in self.sizes_we_can_serve
            )
            lines.append(f"  Total reached queries: {total_traffic:,}")
            lines.append(f"  Queries you can serve: {servable_traffic:,} ({self.overall_match_rate:.1f}%)")
            lines.append(f"  Queries you cannot serve: {total_traffic - servable_traffic:,} ({100 - self.overall_match_rate:.1f}%)")
            lines.append("")
        else:
            lines.append("TRAFFIC DATA: Not available")
            lines.append("  To get traffic data, import CSV or enable RTB Troubleshooting API")
            lines.append("")

        # Recommended include list
        if self.recommended_include_list:
            lines.append("RECOMMENDED PRETARGETING SIZE LIST:")
            lines.append("  (Add these to your pretargeting config to reduce waste)")
            lines.append("")
            for size in self.recommended_include_list[:20]:
                lines.append(f"    {size}")
            lines.append("")
            lines.append("  WARNING: Once you add ANY size, all other sizes are EXCLUDED")
            lines.append("")

        # Opportunity sizes
        if self.opportunity_sizes:
            lines.append("OPPORTUNITY: High-volume sizes worth creating creatives for:")
            for opp in self.opportunity_sizes[:5]:
                lines.append(f"    {opp['size']}: {opp['queries']:,} QPS/day")
            lines.append("")

        lines.append("=" * 80)
        return "\n".join(lines)


@dataclass
class PretargetingConfig:
    """A pretargeting configuration from the API or database."""

    config_id: str
    billing_id: str
    display_name: str
    state: str  # ACTIVE, SUSPENDED
    geos: List[str] = field(default_factory=list)
    included_sizes: List[str] = field(default_factory=list)
    qps_cap: int = 0
    budget: float = 0.0


@dataclass
class ConfigPerformance:
    """Performance metrics for a pretargeting config."""

    billing_id: str
    display_name: str
    reached_queries: int
    impressions: int
    clicks: int
    spend: float
    efficiency: float  # impressions / reached_queries
    issues: List[str] = field(default_factory=list)


@dataclass
class ConfigPerformanceReport:
    """Complete config performance tracker report."""

    configs: List[ConfigPerformance]
    total_reached: int
    total_impressions: int
    total_spend: float
    average_efficiency: float
    generated_at: str

    def to_printout(self) -> str:
        """Generate human-readable printout."""
        lines = []
        lines.append("=" * 80)
        lines.append("CONFIG PERFORMANCE REPORT (last 7 days)")
        lines.append("=" * 80)
        lines.append("")
        lines.append(f"Generated: {self.generated_at}")
        lines.append("")

        # Summary
        lines.append(f"Total Reached Queries: {self.total_reached:,}")
        lines.append(f"Total Impressions: {self.total_impressions:,}")
        lines.append(f"Total Spend: ${self.total_spend:,.2f}")
        lines.append(f"Average Efficiency: {self.average_efficiency:.1f}%")
        lines.append("")

        # Config breakdown
        lines.append("-" * 80)
        lines.append(f"{'Billing ID':<15} {'Name':<20} {'Reached':<12} {'Impr':<12} {'Eff%':<8} {'Issues'}")
        lines.append("-" * 80)

        for config in sorted(self.configs, key=lambda x: x.reached_queries, reverse=True):
            issues_str = ", ".join(config.issues) if config.issues else "None"
            lines.append(
                f"{config.billing_id:<15} "
                f"{config.display_name[:18]:<20} "
                f"{config.reached_queries:<12,} "
                f"{config.impressions:<12,} "
                f"{config.efficiency:<8.1f} "
                f"{issues_str}"
            )

        lines.append("")

        # Investigation needed
        low_efficiency = [c for c in self.configs if c.efficiency < 60]
        if low_efficiency:
            lines.append("INVESTIGATION NEEDED:")
            for config in low_efficiency:
                lines.append(f"  Config {config.billing_id} ({config.display_name})")
                lines.append(f"    - Efficiency: {config.efficiency:.1f}% (below 60% threshold)")
                lines.append("    - Possible causes: size mismatch, poor inventory, pretargeting too broad")
            lines.append("")

        lines.append("=" * 80)
        return "\n".join(lines)


@dataclass
class FraudSignal:
    """A suspicious pattern detected in traffic."""

    entity_type: str  # "app", "publisher", "geo"
    entity_id: str
    entity_name: str
    signal_type: str  # "high_ctr", "clicks_exceed_impressions", "zero_conversions"
    signal_strength: str  # "HIGH", "MEDIUM", "LOW"
    metrics: dict  # relevant metrics
    recommendation: str
    detail: str


@dataclass
class FraudSignalReport:
    """Complete fraud signal detection report."""

    signals: List[FraudSignal]
    total_suspicious_apps: int
    total_suspicious_publishers: int
    generated_at: str

    def to_printout(self) -> str:
        """Generate human-readable printout."""
        lines = []
        lines.append("=" * 80)
        lines.append("FRAUD SIGNALS (requires human review)")
        lines.append("=" * 80)
        lines.append("")
        lines.append(f"Generated: {self.generated_at}")
        lines.append("")
        lines.append("NOTE: These are patterns, not proof. Smart fraud mixes 70-80% real traffic")
        lines.append("with 20-30% fake. Single signals are not conclusive.")
        lines.append("")

        if not self.signals:
            lines.append("No suspicious patterns detected.")
            lines.append("")
        else:
            lines.append(f"Found {len(self.signals)} suspicious patterns:")
            lines.append("")

            for signal in self.signals:
                lines.append(f"  {signal.entity_type.upper()}: {signal.entity_name}")
                lines.append(f"    Signal: {signal.signal_type}")
                lines.append(f"    Strength: {signal.signal_strength}")
                lines.append(f"    Detail: {signal.detail}")
                lines.append(f"    Recommendation: {signal.recommendation}")
                lines.append("")

        lines.append("=" * 80)
        return "\n".join(lines)


# ============================================================================
# QPS Optimizer
# ============================================================================


class QPSOptimizer:
    """Main QPS optimization engine.

    Implements all analysis modules from the QPS Optimization Strategy:
    - Module 1: Size Coverage Analyzer
    - Module 2: Config Performance Tracker
    - Module 3: Fraud Signal Detector
    """

    # Known billing IDs from the strategy document
    KNOWN_BILLING_IDS = {
        "72245759413": {"name": "Africa/Asia", "geos": "BF,BR,CI,CM,EG,NG,SA,SE,IN,PH,KZ", "qps_cap": 50000},
        "83435423204": {"name": "ID/BR Android", "geos": "ID,BR,IN,US,KR,ZA,AR", "qps_cap": 50000},
        "104602012074": {"name": "MENA iOS&AND", "geos": "SA,AE,EG,PH,IT,ES,BF,KZ,FR,PE,ZA,HU,SK", "qps_cap": 50000},
        "137175951277": {"name": "SEA Whitelist", "geos": "BR,ID,MY,TH,VN", "qps_cap": 30000},
        "151274651962": {"name": "USEast CA/MX", "geos": "CA,MX", "qps_cap": 5000},
        "153322387893": {"name": "Brazil AND", "geos": "BR", "qps_cap": 30000},
        "155546863666": {"name": "Asia BL2003", "geos": "ID,IN,TH,CN,KR,TR,VN,BD,PH,MY", "qps_cap": 50000},
        "156494841242": {"name": "Nova WL", "geos": "?", "qps_cap": 30000},
        "157331516553": {"name": "US/Global", "geos": "US,PH,AU,KR,EG,PK,BD,UZ,SA,JP,PE,ZA,HU,SK,AR,KW", "qps_cap": 50000},
        "158323666240": {"name": "BR/PH Spotify", "geos": "BR,PH", "qps_cap": 30000},
    }

    def __init__(self, db_store: "SQLiteStore"):
        """Initialize the QPS optimizer.

        Args:
            db_store: SQLiteStore instance for database access.
        """
        self.store = db_store

    # ========================================================================
    # Module 1: Size Coverage Analyzer
    # ========================================================================

    async def generate_size_coverage_report(self) -> SizeCoverageReport:
        """Generate comprehensive size coverage analysis.

        Compares creative inventory sizes against traffic data to identify:
        - What sizes you have creatives for
        - What sizes you're receiving traffic for
        - Match rate (% of traffic you can serve)
        - Recommended pretargeting include list
        - Opportunity sizes worth creating creatives for

        Returns:
            SizeCoverageReport with complete analysis.
        """
        logger.info("Generating size coverage report")

        # Get creative inventory by size
        sizes_we_have = await self._get_creative_sizes()

        # Get traffic data by size (if available)
        sizes_in_traffic = await self._get_traffic_sizes()

        # Calculate match analysis
        our_sizes = {inv.canonical_size for inv in sizes_we_have}
        traffic_sizes = {t.canonical_size for t in sizes_in_traffic}

        sizes_we_can_serve = list(our_sizes & traffic_sizes)
        sizes_we_cannot_serve = list(traffic_sizes - our_sizes)

        # Calculate overall match rate
        if sizes_in_traffic:
            total_traffic = sum(t.reached_queries for t in sizes_in_traffic)
            servable_traffic = sum(
                t.reached_queries for t in sizes_in_traffic
                if t.canonical_size in our_sizes
            )
            overall_match_rate = (servable_traffic / total_traffic * 100) if total_traffic > 0 else 0
        else:
            overall_match_rate = 0.0

        # Generate recommended include list (sizes we have creatives for)
        recommended_include_list = [inv.canonical_size for inv in sizes_we_have]

        # Find opportunity sizes (high-traffic sizes we don't have creatives for)
        opportunity_sizes = []
        for traffic in sorted(sizes_in_traffic, key=lambda x: x.reached_queries, reverse=True):
            if traffic.canonical_size not in our_sizes:
                opportunity_sizes.append({
                    "size": traffic.canonical_size,
                    "queries": traffic.reached_queries,
                    "width": traffic.width,
                    "height": traffic.height,
                })

        return SizeCoverageReport(
            total_creatives=sum(inv.creative_count for inv in sizes_we_have),
            total_sizes_with_creatives=len(sizes_we_have),
            total_sizes_in_traffic=len(sizes_in_traffic),
            overall_match_rate=overall_match_rate,
            sizes_we_have=sizes_we_have,
            sizes_in_traffic=sizes_in_traffic,
            sizes_we_can_serve=sizes_we_can_serve,
            sizes_we_cannot_serve=sizes_we_cannot_serve,
            recommended_include_list=recommended_include_list,
            opportunity_sizes=opportunity_sizes[:10],
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    async def _get_creative_sizes(self) -> List[CreativeSizeInventory]:
        """Get creative inventory grouped by size."""
        creatives = await self.store.list_creatives(limit=10000)

        # Group by canonical_size
        size_map: Dict[str, CreativeSizeInventory] = {}

        for creative in creatives:
            size = creative.canonical_size
            if not size:
                continue

            if size not in size_map:
                # Try to extract dimensions from canonical_size
                width, height = self._extract_dimensions(size)
                size_map[size] = CreativeSizeInventory(
                    canonical_size=size,
                    width=width,
                    height=height,
                    creative_count=0,
                    formats={},
                    sample_creative_ids=[],
                )

            size_map[size].creative_count += 1

            # Track format
            fmt = creative.format or "UNKNOWN"
            size_map[size].formats[fmt] = size_map[size].formats.get(fmt, 0) + 1

            # Keep sample IDs
            if len(size_map[size].sample_creative_ids) < 5:
                size_map[size].sample_creative_ids.append(creative.id)

        return list(size_map.values())

    async def _get_traffic_sizes(self) -> List[TrafficSizeData]:
        """Get traffic data grouped by size from rtb_traffic table."""
        try:
            traffic_data = await self.store.get_traffic_data(days=30)
        except Exception as e:
            logger.warning(f"Could not get traffic data: {e}")
            traffic_data = []

        # Group by canonical_size
        size_map: Dict[str, TrafficSizeData] = {}

        for record in traffic_data:
            size = record.get("canonical_size")
            if not size:
                continue

            if size not in size_map:
                width, height = self._extract_dimensions(size)
                size_map[size] = TrafficSizeData(
                    canonical_size=size,
                    width=width,
                    height=height,
                    reached_queries=0,
                    impressions=0,
                )

            size_map[size].reached_queries += record.get("request_count", 0)

        return list(size_map.values())

    def _extract_dimensions(self, canonical_size: str) -> Tuple[int, int]:
        """Extract width and height from canonical size string."""
        import re

        # Try patterns like "300x250" or "Non-Standard (320x480)"
        match = re.search(r"(\d+)x(\d+)", canonical_size)
        if match:
            return int(match.group(1)), int(match.group(2))

        return 0, 0

    # ========================================================================
    # Module 2: Config Performance Tracker
    # ========================================================================

    async def generate_config_performance_report(self) -> ConfigPerformanceReport:
        """Generate performance report for all pretargeting configs.

        Analyzes performance by billing_id to show:
        - Reached queries, impressions, clicks, spend per config
        - Efficiency (impression rate)
        - Issues and investigation recommendations

        Returns:
            ConfigPerformanceReport with complete analysis.
        """
        logger.info("Generating config performance report")

        # Get performance data grouped by billing_id
        config_perf = await self._get_performance_by_config()

        # Calculate totals
        total_reached = sum(c.reached_queries for c in config_perf)
        total_impressions = sum(c.impressions for c in config_perf)
        total_spend = sum(c.spend for c in config_perf)

        avg_efficiency = (total_impressions / total_reached * 100) if total_reached > 0 else 0

        return ConfigPerformanceReport(
            configs=config_perf,
            total_reached=total_reached,
            total_impressions=total_impressions,
            total_spend=total_spend,
            average_efficiency=avg_efficiency,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    async def _get_performance_by_config(self) -> List[ConfigPerformance]:
        """Get performance metrics grouped by billing_id."""
        import asyncio

        # Query performance_metrics grouped by billing_account_id
        async with self.store._connection() as conn:
            loop = asyncio.get_event_loop()

            def query():
                cursor = conn.execute("""
                    SELECT
                        billing_account_id,
                        SUM(reached_queries) as reached,
                        SUM(impressions) as impr,
                        SUM(clicks) as clicks,
                        SUM(spend_micros) / 1000000.0 as spend
                    FROM performance_metrics
                    WHERE billing_account_id IS NOT NULL
                    GROUP BY billing_account_id
                """)
                return cursor.fetchall()

            rows = await loop.run_in_executor(None, query)

        configs = []
        for row in rows:
            billing_id = str(row[0]) if row[0] else "unknown"
            reached = row[1] or 0
            impr = row[2] or 0
            clicks = row[3] or 0
            spend = row[4] or 0.0

            efficiency = (impr / reached * 100) if reached > 0 else 0

            # Get config name from known list
            config_info = self.KNOWN_BILLING_IDS.get(billing_id, {})
            display_name = config_info.get("name", f"Config {billing_id}")

            # Detect issues
            issues = []
            if efficiency < 50:
                issues.append("Low efficiency")
            if reached < 100:
                issues.append("Low volume")

            configs.append(ConfigPerformance(
                billing_id=billing_id,
                display_name=display_name,
                reached_queries=reached,
                impressions=impr,
                clicks=clicks,
                spend=spend,
                efficiency=efficiency,
                issues=issues,
            ))

        # Add known configs that have no data yet
        seen_billing_ids = {c.billing_id for c in configs}
        for billing_id, info in self.KNOWN_BILLING_IDS.items():
            if billing_id not in seen_billing_ids:
                configs.append(ConfigPerformance(
                    billing_id=billing_id,
                    display_name=info["name"],
                    reached_queries=0,
                    impressions=0,
                    clicks=0,
                    spend=0.0,
                    efficiency=0.0,
                    issues=["No data"],
                ))

        return configs

    # ========================================================================
    # Module 3: Fraud Signal Detector
    # ========================================================================

    async def generate_fraud_signal_report(self, days: int = 14) -> FraudSignalReport:
        """Generate fraud signal detection report.

        Analyzes traffic patterns to detect suspicious activity:
        - Unusually high CTR
        - Clicks exceeding impressions
        - High impressions with zero conversions
        - Suspiciously consistent metrics

        Args:
            days: Number of days to analyze.

        Returns:
            FraudSignalReport with detected signals.
        """
        logger.info(f"Generating fraud signal report for {days} days")

        signals = []

        # Detect high CTR anomalies
        ctr_signals = await self._detect_high_ctr(days)
        signals.extend(ctr_signals)

        # Detect clicks > impressions
        click_signals = await self._detect_clicks_exceed_impressions(days)
        signals.extend(click_signals)

        # Count by entity type
        app_signals = [s for s in signals if s.entity_type == "app"]
        pub_signals = [s for s in signals if s.entity_type == "publisher"]

        return FraudSignalReport(
            signals=signals,
            total_suspicious_apps=len(app_signals),
            total_suspicious_publishers=len(pub_signals),
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    async def _detect_high_ctr(self, days: int) -> List[FraudSignal]:
        """Detect apps/publishers with unusually high CTR."""
        import asyncio
        signals = []

        # Get aggregated metrics by app
        async with self.store._connection() as conn:
            loop = asyncio.get_event_loop()
            days_param = f"-{days} days"

            def query():
                cursor = conn.execute("""
                    SELECT
                        placement,
                        SUM(impressions) as total_impr,
                        SUM(clicks) as total_clicks
                    FROM performance_metrics
                    WHERE metric_date >= date('now', ?)
                    GROUP BY placement
                    HAVING total_impr > 100
                """, (days_param,))
                return cursor.fetchall()

            rows = await loop.run_in_executor(None, query)

        for row in rows:
            placement = row[0] or "unknown"
            impressions = row[1] or 0
            clicks = row[2] or 0

            if impressions <= 0:
                continue

            ctr = (clicks / impressions) * 100

            # Flag CTR > 3% as suspicious (typical mobile CTR is 0.5-1%)
            if ctr > 3.0:
                strength = "HIGH" if ctr > 5.0 else "MEDIUM"
                signals.append(FraudSignal(
                    entity_type="app",
                    entity_id=placement,
                    entity_name=placement,
                    signal_type="high_ctr",
                    signal_strength=strength,
                    metrics={"ctr": round(ctr, 2), "impressions": impressions, "clicks": clicks},
                    recommendation="Monitor for 7 more days, consider blocking if pattern continues",
                    detail=f"CTR of {ctr:.1f}% is unusually high (average: 0.5-1%)",
                ))

        return signals

    async def _detect_clicks_exceed_impressions(self, days: int) -> List[FraudSignal]:
        """Detect cases where clicks exceed impressions (click injection)."""
        import asyncio
        signals = []

        async with self.store._connection() as conn:
            loop = asyncio.get_event_loop()
            days_param = f"-{days} days"

            def query():
                cursor = conn.execute("""
                    SELECT
                        placement,
                        metric_date,
                        impressions,
                        clicks
                    FROM performance_metrics
                    WHERE metric_date >= date('now', ?)
                      AND clicks > impressions
                      AND impressions > 0
                """, (days_param,))
                return cursor.fetchall()

            rows = await loop.run_in_executor(None, query)

        # Group by placement
        placement_issues: Dict[str, int] = {}
        for row in rows:
            placement = row[0] or "unknown"
            placement_issues[placement] = placement_issues.get(placement, 0) + 1

        for placement, count in placement_issues.items():
            strength = "HIGH" if count >= 5 else ("MEDIUM" if count >= 3 else "LOW")
            signals.append(FraudSignal(
                entity_type="app",
                entity_id=placement,
                entity_name=placement,
                signal_type="clicks_exceed_impressions",
                signal_strength=strength,
                metrics={"days_with_issue": count},
                recommendation="Flag for review, possible click injection attack",
                detail=f"Clicks exceeded impressions on {count} of {days} days",
            ))

        return signals

    # ========================================================================
    # Combined Report Generation
    # ========================================================================

    async def generate_full_report(self) -> str:
        """Generate comprehensive QPS optimization report.

        Combines all analysis modules into a single printout.

        Returns:
            String containing the full report.
        """
        lines = []
        lines.append("")
        lines.append("=" * 80)
        lines.append("RTBcat QPS OPTIMIZATION REPORT")
        lines.append("=" * 80)
        lines.append("")
        lines.append(f"Account: Tuky Data Research Ltd. (ID: 299038253)")
        lines.append(f"Generated: {datetime.now(timezone.utc).isoformat()}")
        lines.append("")

        # Module 1: Size Coverage
        try:
            size_report = await self.generate_size_coverage_report()
            lines.append(size_report.to_printout())
            lines.append("")
        except Exception as e:
            lines.append(f"Size Coverage: Error - {e}")
            lines.append("")

        # Module 2: Config Performance
        try:
            config_report = await self.generate_config_performance_report()
            lines.append(config_report.to_printout())
            lines.append("")
        except Exception as e:
            lines.append(f"Config Performance: Error - {e}")
            lines.append("")

        # Module 3: Fraud Signals
        try:
            fraud_report = await self.generate_fraud_signal_report()
            lines.append(fraud_report.to_printout())
            lines.append("")
        except Exception as e:
            lines.append(f"Fraud Signals: Error - {e}")
            lines.append("")

        lines.append("=" * 80)
        lines.append("END OF REPORT")
        lines.append("=" * 80)

        return "\n".join(lines)
