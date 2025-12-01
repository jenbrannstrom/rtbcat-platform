"""RTBcat Creative Intelligence - Analytics Module.

This module provides waste analysis and QPS optimization capabilities,
comparing bid requests against available creative inventory.

Example:
    >>> from analytics import WasteAnalyzer, QPSOptimizer
    >>> from storage import SQLiteStore
    >>>
    >>> store = SQLiteStore()
    >>> await store.initialize()
    >>>
    >>> # Waste analysis
    >>> analyzer = WasteAnalyzer(store)
    >>> report = await analyzer.analyze_waste(buyer_id="456")
    >>> print(f"Waste: {report.waste_percentage}%")
    >>>
    >>> # QPS optimization report
    >>> optimizer = QPSOptimizer(store)
    >>> full_report = await optimizer.generate_full_report()
    >>> print(full_report)
"""

from analytics.waste_models import SizeGap, WasteReport, TrafficRecord, SizeCoverage
from analytics.mock_traffic import generate_mock_traffic, TRAFFIC_DISTRIBUTIONS
from analytics.waste_analyzer import WasteAnalyzer
from analytics.qps_optimizer import (
    QPSOptimizer,
    SizeCoverageReport,
    ConfigPerformanceReport,
    FraudSignalReport,
    CreativeSizeInventory,
    ConfigPerformance,
    FraudSignal,
)

__all__ = [
    # Models
    "SizeGap",
    "WasteReport",
    "TrafficRecord",
    "SizeCoverage",
    # QPS Optimizer Models
    "SizeCoverageReport",
    "ConfigPerformanceReport",
    "FraudSignalReport",
    "CreativeSizeInventory",
    "ConfigPerformance",
    "FraudSignal",
    # Mock data
    "generate_mock_traffic",
    "TRAFFIC_DISTRIBUTIONS",
    # Analyzers
    "WasteAnalyzer",
    "QPSOptimizer",
]
