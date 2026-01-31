"""RTBcat Creative Intelligence - Storage Module.

This module provides storage backends for creative data,
supporting PostgreSQL and cloud S3 storage.

The storage layer is organized as follows:
- models.py: All dataclass definitions
- postgres_store.py: Main facade class (delegates to postgres_repositories)
- postgres_repositories/: Postgres-only repository classes
- postgres_database.py: Postgres connection and query utilities

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

# Models
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

__all__ = [
    # Storage backends
    "PostgresStore",
    "S3Writer",
    # Models (backward compatible)
    "Creative",
    "Campaign",
    "BuyerSeat",
    "PerformanceMetric",
    # New models
    "CreativeModel",
    "CampaignModel",
    "Cluster",
    "ServiceAccount",
    "BuyerSeatModel",
    "PerformanceMetricModel",
    "ThumbnailStatus",
    "ImportHistory",
    "DailyUploadSummary",
    # Adapters
    "creative_dict_to_storage",
    "creative_dicts_to_storage",
]
