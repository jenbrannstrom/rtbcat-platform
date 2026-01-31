"""Postgres-only repositories (SQL + row mapping only)."""

from .endpoints_repo import EndpointsRepository
from .snapshots_repo import SnapshotsRepository
from .changes_repo import ChangesRepository
from .pretargeting_repo import PretargetingRepository
from .comparisons_repo import ComparisonsRepository
from .performance_repo import PerformanceRepository
from .retention_repo import RetentionRepository
from .evaluation_repo import EvaluationRepository
from .campaign_repo import CampaignRepository
from .creatives_repo import CreativesRepository
from .thumbnails_repo import ThumbnailsRepository
from .seats_repo import SeatsRepository
from .uploads_repo import UploadsRepository
from .creative_performance_repo import CreativePerformanceRepository
from .rtb_bidstream_repo import RtbBidstreamRepository
from .analytics_repo import AnalyticsRepository
from .precompute_repo import PrecomputeRepository

__all__ = [
    "EndpointsRepository",
    "SnapshotsRepository",
    "ChangesRepository",
    "PretargetingRepository",
    "ComparisonsRepository",
    "PerformanceRepository",
    "RetentionRepository",
    "EvaluationRepository",
    "CampaignRepository",
    "CreativesRepository",
    "ThumbnailsRepository",
    "SeatsRepository",
    "UploadsRepository",
    "CreativePerformanceRepository",
    "RtbBidstreamRepository",
    "AnalyticsRepository",
    "PrecomputeRepository",
]
