"""Importers Module for Cat-Scan.

This module handles importing and storing RTB performance data from various sources:

1. Authorized Buyers CSV reports (bidstream, quality, funnel reports)
2. Config performance tracking data
3. Size-based traffic aggregation

The primary entry point is the unified_importer (Postgres-based).
Legacy SQLite importers have been archived to docs/archive/sqlite_legacy/.
"""

from importers.models import (
    SizeMetric,
    CreativeSizeInfo,
    SizeCoverageResult,
    ConfigPerformance,
    FraudSignal,
    ImportResult,
)
from importers.constants import (
    GOOGLE_AVAILABLE_SIZES,
    PRETARGETING_CONFIGS,
    ENDPOINTS,
    TOTAL_ENDPOINT_QPS,
    ACCOUNT_ID,
    ACCOUNT_NAME,
)

__all__ = [
    # Models
    "SizeMetric",
    "CreativeSizeInfo",
    "SizeCoverageResult",
    "ConfigPerformance",
    "FraudSignal",
    "ImportResult",
    # Constants
    "GOOGLE_AVAILABLE_SIZES",
    "PRETARGETING_CONFIGS",
    "ENDPOINTS",
    "TOTAL_ENDPOINT_QPS",
    "ACCOUNT_ID",
    "ACCOUNT_NAME",
]
