"""RTBcat Creative Intelligence - Storage Module.

This module provides storage backends for creative data,
supporting both local SQLite and cloud S3 storage.

Example:
    >>> from collectors import CreativesClient
    >>> from storage import SQLiteStore, creative_dict_to_storage
    >>>
    >>> # Fetch from API
    >>> client = CreativesClient(credentials_path="...", account_id="123")
    >>> api_creatives = await client.fetch_all_creatives()
    >>>
    >>> # Convert and store
    >>> storage_creatives = [creative_dict_to_storage(c) for c in api_creatives]
    >>> store = SQLiteStore()
    >>> await store.initialize()
    >>> await store.save_creatives(storage_creatives)
"""

from .adapters import creative_dict_to_storage, creative_dicts_to_storage
from .s3_writer import S3Writer
from .sqlite_store import BuyerSeat, Campaign, Creative, PerformanceMetric, SQLiteStore
from .performance_repository import PerformanceRepository
from .seat_repository import Seat, SeatRepository
from .retention_manager import RetentionManager
from .campaign_repository import AICampaign, CampaignRepository

__all__ = [
    # Storage backends
    "SQLiteStore",
    "S3Writer",
    "PerformanceRepository",
    "SeatRepository",
    "RetentionManager",
    "CampaignRepository",
    # Models
    "Creative",
    "Campaign",
    "AICampaign",
    "BuyerSeat",
    "PerformanceMetric",
    "Seat",
    # Adapters
    "creative_dict_to_storage",
    "creative_dicts_to_storage",
]
