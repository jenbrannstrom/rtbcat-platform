"""QPS Optimization Module for Cat-Scan.

This module provides tools for analyzing and optimizing QPS (Queries Per Second)
in RTB campaigns by:

1. Importing BigQuery CSV exports with size-based aggregation
2. Analyzing size coverage (what sizes you can serve vs. receive)
3. Tracking performance by pretargeting config
4. Detecting fraud signals for human review

Example:
    >>> from qps import import_bigquery_csv, SizeCoverageAnalyzer
    >>>
    >>> # Import data
    >>> result = import_bigquery_csv("/path/to/export.csv")
    >>>
    >>> # Analyze size coverage
    >>> analyzer = SizeCoverageAnalyzer()
    >>> print(analyzer.generate_report(days=7))
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
from qps.size_analyzer import SizeCoverageAnalyzer, CoverageReport
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
    "SizeCoverageAnalyzer",
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
