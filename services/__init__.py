"""Services package for business logic."""

from services.campaign_aggregation import (
    CampaignAggregationService,
    CampaignMetrics,
    CampaignWarnings,
    CampaignWithMetrics,
)
from services.waste_analyzer import (
    CreativeWasteSignalService,
    WasteSignal,
    WasteEvidence,
    analyze_waste,
)

__all__ = [
    "CampaignAggregationService",
    "CampaignMetrics",
    "CampaignWarnings",
    "CampaignWithMetrics",
    "CreativeWasteSignalService",
    "WasteSignal",
    "WasteEvidence",
    "analyze_waste",
]
