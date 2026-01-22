"""QPS Data Import Module for Cat-Scan.

This module handles importing and storing RTB performance data from various sources:

1. BigQuery CSV exports (bidstream, quality, funnel reports)
2. Config performance tracking data
3. Size-based traffic aggregation

The primary purpose is DATA IMPORT. Analysis logic lives in the `analytics/` module.

Note: QpsSizeCoverageAnalyzer and FraudSignalDetector are exported here for
backwards compatibility with the CLI, but will be consolidated into analytics/
in a future refactor.

Example:
    >>> from qps import import_bigquery_csv, get_data_summary
    >>>
    >>> # Import data
    >>> result = import_bigquery_csv("/path/to/export.csv")
    >>>
    >>> # Check what was imported
    >>> summary = get_data_summary()
"""

from qps.importer import (
    import_bigquery_csv,
    import_csv,
    validate_csv,
    get_import_summary,
    get_data_summary,
    ValidationResult,
    ImportResult as ImportResultNew,
)
from qps.size_analyzer import QpsSizeCoverageAnalyzer, CoverageReport
from qps.config_tracker import ConfigPerformanceTracker, ConfigReport
from qps.fraud_detector import FraudSignalDetector, FraudReport
from qps.models import (
    SizeMetric,
    CreativeSizeInfo,
    SizeCoverageResult,
    ConfigPerformance,
    FraudSignal,
    ImportResult,
)
from qps.constants import (
    GOOGLE_AVAILABLE_SIZES,
    PRETARGETING_CONFIGS,
    ENDPOINTS,
    TOTAL_ENDPOINT_QPS,
    ACCOUNT_ID,
    ACCOUNT_NAME,
)

__all__ = [
    # Importer
    "import_bigquery_csv",
    "import_csv",
    "validate_csv",
    "get_import_summary",
    "get_data_summary",
    "ValidationResult",
    # Analyzers
    "QpsSizeCoverageAnalyzer",
    "CoverageReport",
    "ConfigPerformanceTracker",
    "ConfigReport",
    "FraudSignalDetector",
    "FraudReport",
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
