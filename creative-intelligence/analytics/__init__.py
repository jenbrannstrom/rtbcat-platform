"""RTBcat Creative Intelligence - Analytics Module.

This module provides waste analysis capabilities for RTB traffic,
comparing bid requests against available creative inventory.

Example:
    >>> from analytics import WasteAnalyzer, generate_mock_traffic
    >>> from storage import SQLiteStore
    >>>
    >>> store = SQLiteStore()
    >>> await store.initialize()
    >>>
    >>> analyzer = WasteAnalyzer(store)
    >>> report = await analyzer.analyze_waste(buyer_id="456")
    >>> print(f"Waste: {report.waste_percentage}%")
"""

from analytics.waste_models import SizeGap, WasteReport, TrafficRecord, SizeCoverage
from analytics.mock_traffic import generate_mock_traffic, TRAFFIC_DISTRIBUTIONS
from analytics.waste_analyzer import WasteAnalyzer

__all__ = [
    # Models
    "SizeGap",
    "WasteReport",
    "TrafficRecord",
    "SizeCoverage",
    # Mock data
    "generate_mock_traffic",
    "TRAFFIC_DISTRIBUTIONS",
    # Analyzer
    "WasteAnalyzer",
]
