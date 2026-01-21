"""RTBcat Creative Intelligence - Analytics Module.

This module provides waste analysis capabilities,
comparing bid requests against available creative inventory.

Note: QPS optimization has been moved to the `qps` module.

Example:
    >>> from analytics import TrafficWasteAnalyzer
    >>> from storage import SQLiteStore
    >>>
    >>> store = SQLiteStore()
    >>> await store.initialize()
    >>>
    >>> # Traffic waste analysis
    >>> analyzer = TrafficWasteAnalyzer(store)
    >>> report = await analyzer.analyze_waste(buyer_id="456")
    >>> print(f"Waste: {report.waste_percentage}%")
"""

from analytics.waste_models import SizeGap, WasteReport, TrafficRecord, SizeCoverage
from analytics.mock_traffic import generate_mock_traffic, TRAFFIC_DISTRIBUTIONS
from analytics.waste_analyzer import TrafficWasteAnalyzer

# Backward compatibility alias
WasteAnalyzer = TrafficWasteAnalyzer

__all__ = [
    # Models
    "SizeGap",
    "WasteReport",
    "TrafficRecord",
    "SizeCoverage",
    # Mock data
    "generate_mock_traffic",
    "TRAFFIC_DISTRIBUTIONS",
    # Analyzers
    "TrafficWasteAnalyzer",
    "WasteAnalyzer",  # Deprecated alias for backward compatibility
]
