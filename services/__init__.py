"""Services package for business logic."""

from services.campaign_aggregation import (
    CampaignAggregationService,
    CampaignMetrics,
    CampaignWarnings,
    CampaignWithMetrics,
)
from services.waste_analyzer import (
    CreativeHealthService,
    WasteSignal,
    WasteEvidence,
    analyze_creative_health,
    analyze_waste,  # Backward compatibility
)

# Backward compatibility alias
CreativeWasteSignalService = CreativeHealthService

__all__ = [
    "CampaignAggregationService",
    "CampaignMetrics",
    "CampaignWarnings",
    "CampaignWithMetrics",
    "CreativeHealthService",
    "CreativeWasteSignalService",  # Deprecated alias
    "WasteSignal",
    "WasteEvidence",
    "analyze_creative_health",
    "analyze_waste",  # Deprecated alias
]
