"""RTBcat Creative Intelligence - Storage Module.

This module provides storage backends for creative data,
supporting PostgreSQL and cloud S3 storage.

The storage layer is organized as follows:
- models.py: All dataclass definitions
- schema.py: Database schema and migrations
- repositories/: Specialized repository classes for each entity type
- postgres_store.py: Main facade class (delegates to repositories)

Example:
    >>> from collectors import CreativesClient
    >>> from storage import PostgresStore, creative_dict_to_storage
    >>>
    >>> # Fetch from API
    >>> client = CreativesClient(credentials_path="...", account_id="123")
    >>> api_creatives = await client.fetch_all_creatives()
    >>>
    >>> # Convert and store
    >>> storage_creatives = [creative_dict_to_storage(c) for c in api_creatives]
    >>> store = PostgresStore()
    >>> await store.initialize()
    >>> await store.save_creatives(storage_creatives)
"""

from .adapters import creative_dict_to_storage, creative_dicts_to_storage
from .s3_writer import S3Writer
from .postgres_store import BuyerSeat, Campaign, Creative, PerformanceMetric, PostgresStore
from .repositories.performance_repository import PerformanceRepository
from .repositories.seat_repository import Seat, SeatRepository
from .retention_manager import RetentionManager
from .repositories.campaign_repository import AICampaign, CampaignRepository

# New modular imports
from .models import (
    Creative as CreativeModel,
    Campaign as CampaignModel,
    Cluster,
    ServiceAccount,
    BuyerSeat as BuyerSeatModel,
    PerformanceMetric as PerformanceMetricModel,
    ThumbnailStatus,
    ImportHistory,
    DailyUploadSummary,
)
from .schema import SCHEMA, MIGRATIONS
from .repositories import (
    BaseRepository,
    CreativeRepository,
    AccountRepository,
    TrafficRepository,
    ThumbnailRepository,
)

__all__ = [
    # Storage backends
    "PostgresStore",
    "S3Writer",
    "PerformanceRepository",
    "SeatRepository",
    "RetentionManager",
    "CampaignRepository",
    # Models (backward compatible)
    "Creative",
    "Campaign",
    "AICampaign",
    "BuyerSeat",
    "PerformanceMetric",
    "Seat",
    # New models
    "Cluster",
    "ServiceAccount",
    "ThumbnailStatus",
    "ImportHistory",
    "DailyUploadSummary",
    # Schema
    "SCHEMA",
    "MIGRATIONS",
    # New repositories
    "BaseRepository",
    "CreativeRepository",
    "AccountRepository",
    "TrafficRepository",
    "ThumbnailRepository",
    # Adapters
    "creative_dict_to_storage",
    "creative_dicts_to_storage",
]
