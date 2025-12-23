"""Data models for QPS Optimization."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class SizeMetric:
    """Daily metrics for a specific size/billing_id combination."""

    metric_date: str
    billing_id: str
    creative_size: str
    country: Optional[str] = None
    platform: Optional[str] = None
    environment: Optional[str] = None
    app_id: Optional[str] = None
    app_name: Optional[str] = None
    reached_queries: int = 0
    impressions: int = 0
    clicks: int = 0
    spend_micros: int = 0
    video_starts: int = 0
    video_completions: int = 0
    vast_errors: int = 0


@dataclass
class CreativeSizeInfo:
    """Information about a creative size in your inventory."""

    size: str  # e.g., "300x250"
    creative_count: int
    formats: Dict[str, int] = field(default_factory=dict)  # {VIDEO: 10, HTML: 5}
    creative_ids: List[str] = field(default_factory=list)


@dataclass
class SizeCoverageResult:
    """Result of size coverage analysis."""

    size: str
    reached_queries: int
    impressions: int
    you_can_serve: bool
    creative_count: int
    in_google_list: bool
    efficiency_pct: float
    recommendation: str  # 'INCLUDE', 'CREATE_CREATIVE', 'IGNORE'


@dataclass
class ConfigPerformance:
    """Performance metrics for a pretargeting config."""

    billing_id: str
    name: str
    reached_queries: int = 0
    impressions: int = 0
    clicks: int = 0
    spend_usd: float = 0.0
    efficiency_pct: float = 0.0
    issues: List[str] = field(default_factory=list)


@dataclass
class FraudSignal:
    """A suspicious pattern flagged for human review."""

    entity_type: str  # 'app', 'publisher', 'size'
    entity_id: str
    entity_name: str
    signal_type: str  # 'high_ctr', 'clicks_exceed_impressions'
    signal_strength: str  # 'LOW', 'MEDIUM', 'HIGH'
    evidence: Dict
    days_observed: int
    recommendation: str


@dataclass
class ImportResult:
    """Result of a CSV import operation."""

    rows_read: int = 0
    rows_imported: int = 0
    rows_skipped: int = 0
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    sizes_found: List[str] = field(default_factory=list)
    billing_ids_found: List[str] = field(default_factory=list)
    total_reached_queries: int = 0
    total_spend_usd: float = 0.0
    errors: List[str] = field(default_factory=list)
