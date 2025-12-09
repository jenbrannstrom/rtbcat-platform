"""API Schema models for Cat-Scan Creative Intelligence."""

from .common import (
    PaginationMeta,
    VideoPreview,
    HtmlPreview,
    ImagePreview,
    NativePreview,
    ThumbnailStatusResponse,
    WasteFlagsResponse,
)

from .creatives import (
    CreativeResponse,
    ClusterAssignment,
    PaginatedCreativesResponse,
    NewlyUploadedCreativesResponse,
)

from .campaigns import (
    CampaignMetricsResponse,
    CampaignWarningsResponse,
    CampaignResponse,
    PaginatedCampaignsResponse,
    AutoClusterResponse,
)

from .performance import (
    PerformanceMetricInput,
    PerformanceMetricResponse,
    PerformanceSummaryResponse,
    ImportPerformanceRequest,
    ImportPerformanceResponse,
    BatchPerformanceRequest,
    CreativePerformanceSummary,
    BatchPerformanceResponse,
    CSVImportResult,
    StreamingImportProgress,
    StreamingImportResult,
)

from .qps import (
    QPSImportResult,
    QPSSummaryResponse,
    QPSReportResponse,
)

from .system import (
    HealthResponse,
    StatsResponse,
    SizesResponse,
    SystemStatusResponse,
    CollectRequest,
    CollectResponse,
)

from .seats import (
    BuyerSeatResponse,
    DiscoverSeatsRequest,
    DiscoverSeatsResponse,
    SyncSeatResponse,
)

from .analytics import (
    SizeGapResponse,
    SizeCoverageResponse,
    WasteReportResponse,
    ImportTrafficResponse,
    WasteSignalResponse,
    ProblemFormatResponse,
)

from .recommendations import (
    EvidenceResponse,
    ImpactResponse,
    ActionResponse,
    RecommendationResponse,
    RecommendationSummaryResponse,
)

__all__ = [
    # Common
    "PaginationMeta",
    "VideoPreview",
    "HtmlPreview",
    "ImagePreview",
    "NativePreview",
    "ThumbnailStatusResponse",
    "WasteFlagsResponse",
    # Creatives
    "CreativeResponse",
    "ClusterAssignment",
    "PaginatedCreativesResponse",
    "NewlyUploadedCreativesResponse",
    # Campaigns
    "CampaignMetricsResponse",
    "CampaignWarningsResponse",
    "CampaignResponse",
    "PaginatedCampaignsResponse",
    "AutoClusterResponse",
    # Performance
    "PerformanceMetricInput",
    "PerformanceMetricResponse",
    "PerformanceSummaryResponse",
    "ImportPerformanceRequest",
    "ImportPerformanceResponse",
    "BatchPerformanceRequest",
    "CreativePerformanceSummary",
    "BatchPerformanceResponse",
    "CSVImportResult",
    "StreamingImportProgress",
    "StreamingImportResult",
    # QPS
    "QPSImportResult",
    "QPSSummaryResponse",
    "QPSReportResponse",
    # System
    "HealthResponse",
    "StatsResponse",
    "SizesResponse",
    "SystemStatusResponse",
    "CollectRequest",
    "CollectResponse",
    # Seats
    "BuyerSeatResponse",
    "DiscoverSeatsRequest",
    "DiscoverSeatsResponse",
    "SyncSeatResponse",
    # Analytics
    "SizeGapResponse",
    "SizeCoverageResponse",
    "WasteReportResponse",
    "ImportTrafficResponse",
    "WasteSignalResponse",
    "ProblemFormatResponse",
    # Recommendations
    "EvidenceResponse",
    "ImpactResponse",
    "ActionResponse",
    "RecommendationResponse",
    "RecommendationSummaryResponse",
]
