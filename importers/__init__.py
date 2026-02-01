"""Importers Module for Cat-Scan.

This module handles importing and storing RTB performance data from various sources:

1. Authorized Buyers CSV reports (bidstream, quality, funnel reports)
2. Config performance tracking data
3. Size-based traffic aggregation

The primary purpose is DATA IMPORT. Analysis logic lives in the `analytics/` module.

Example:
    >>> from importers import import_report, get_data_summary
    >>>
    >>> # Import data
    >>> result = import_report("/path/to/export.csv")
    >>>
    >>> # Check what was imported
    >>> summary = get_data_summary()
"""

from importers.importer import (
    import_report,
    import_bigquery_csv,  # Deprecated alias
    import_csv,
    validate_csv,
    get_import_summary,
    get_data_summary,
    ValidationResult,
    ImportResult as ImportResultNew,
)
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

_ANALYZER_EXPORTS = {
    "QpsSizeCoverageAnalyzer": ("analytics.cli_size_analyzer", "QpsSizeCoverageAnalyzer"),
    "CoverageReport": ("analytics.cli_size_analyzer", "CoverageReport"),
    "ConfigPerformanceTracker": ("analytics.cli_config_tracker", "ConfigPerformanceTracker"),
    "ConfigReport": ("analytics.cli_config_tracker", "ConfigReport"),
    "FraudSignalDetector": ("analytics.cli_fraud_detector", "FraudSignalDetector"),
    "FraudReport": ("analytics.cli_fraud_detector", "FraudReport"),
}


def __getattr__(name: str):
    """Lazy re-exports for analytics analyzers to avoid circular imports."""
    if name in _ANALYZER_EXPORTS:
        module_name, attr_name = _ANALYZER_EXPORTS[name]
        module = __import__(module_name, fromlist=[attr_name])
        return getattr(module, attr_name)
    raise AttributeError(f"module 'importers' has no attribute {name!r}")

__all__ = [
    # Importer
    "import_report",
    "import_bigquery_csv",  # Deprecated
    "import_csv",
    "validate_csv",
    "get_import_summary",
    "get_data_summary",
    "ValidationResult",
    # Analyzers (from analytics/, re-exported for compatibility)
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
