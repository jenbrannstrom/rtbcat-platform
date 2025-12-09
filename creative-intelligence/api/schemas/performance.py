"""Performance metrics schema models."""

from typing import Optional
from pydantic import BaseModel


class PerformanceMetricInput(BaseModel):
    """Input model for importing a single performance metric."""
    creative_id: str
    metric_date: str
    impressions: int = 0
    clicks: int = 0
    spend_micros: int = 0
    campaign_id: Optional[str] = None
    geography: Optional[str] = None
    device_type: Optional[str] = None
    placement: Optional[str] = None


class PerformanceMetricResponse(BaseModel):
    """Response model for a performance metric record."""
    id: Optional[int] = None
    creative_id: str
    campaign_id: Optional[str] = None
    metric_date: str
    impressions: int
    clicks: int
    spend_micros: int
    cpm_micros: Optional[int] = None
    cpc_micros: Optional[int] = None
    geography: Optional[str] = None
    device_type: Optional[str] = None
    placement: Optional[str] = None


class PerformanceSummaryResponse(BaseModel):
    """Response model for aggregated performance summary."""
    total_impressions: Optional[int] = None
    total_clicks: Optional[int] = None
    total_spend_micros: Optional[int] = None
    avg_cpm_micros: Optional[int] = None
    avg_cpc_micros: Optional[int] = None
    ctr_percent: Optional[float] = None
    days_with_data: Optional[int] = None
    earliest_date: Optional[str] = None
    latest_date: Optional[str] = None


class ImportPerformanceRequest(BaseModel):
    """Request model for bulk performance import."""
    metrics: list[PerformanceMetricInput]


class ImportPerformanceResponse(BaseModel):
    """Response model for performance import operation."""
    status: str
    records_imported: int
    message: str


class BatchPerformanceRequest(BaseModel):
    """Request model for batch performance lookup."""
    creative_ids: list[str]
    period: str = "7d"


class CreativePerformanceSummary(BaseModel):
    """Performance summary for a single creative."""
    creative_id: str
    total_impressions: int = 0
    total_clicks: int = 0
    total_spend_micros: int = 0
    avg_cpm_micros: Optional[int] = None
    avg_cpc_micros: Optional[int] = None
    ctr_percent: Optional[float] = None
    days_with_data: int = 0
    has_data: bool = False


class BatchPerformanceResponse(BaseModel):
    """Response model for batch performance lookup."""
    performance: dict[str, CreativePerformanceSummary]
    period: str
    count: int


class CSVImportResult(BaseModel):
    """Result of CSV import operation."""
    success: bool
    batch_id: Optional[str] = None
    rows_read: Optional[int] = None
    rows_imported: Optional[int] = None
    rows_duplicate: Optional[int] = None
    rows_skipped: Optional[int] = None
    date_range: Optional[dict] = None
    unique_creatives: Optional[int] = None
    unique_sizes: Optional[int] = None
    unique_countries: Optional[int] = None
    billing_ids: Optional[list[str]] = None
    total_reached: Optional[int] = None
    total_impressions: Optional[int] = None
    total_spend_usd: Optional[float] = None
    columns_imported: Optional[list[str]] = None
    error: Optional[str] = None
    fix_instructions: Optional[str] = None
    columns_found: Optional[list[str]] = None
    columns_mapped: Optional[dict] = None
    required_missing: Optional[list[str]] = None
    errors: Optional[list[str]] = None


class StreamingImportProgress(BaseModel):
    """Progress update for streaming import."""
    status: str
    rows_processed: int
    rows_imported: int
    rows_skipped: int
    current_batch: int
    errors: list[dict] = []


class StreamingImportResult(BaseModel):
    """Final result of streaming import."""
    status: str
    total_rows: int
    imported: int
    skipped: int
    batches: int
    errors: list[str] = []
    date_range: Optional[dict] = None
    total_spend: Optional[float] = None
