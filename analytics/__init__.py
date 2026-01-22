"""RTBcat Creative Intelligence - Analytics Module.

This module provides analysis capabilities for RTB optimization:
- Traffic waste analysis (comparing bid requests vs creative inventory)
- Size mismatch analysis (finding sizes with traffic but no creatives)
- Fraud signal detection
- Geographic performance analysis

Example:
    >>> from analytics import TrafficWasteAnalyzer, SizeAnalyzer
    >>> from storage import SQLiteStore
    >>>
    >>> store = SQLiteStore()
    >>> await store.initialize()
    >>>
    >>> # Traffic waste analysis
    >>> analyzer = TrafficWasteAnalyzer(store)
    >>> report = await analyzer.analyze_waste(buyer_id="456")
    >>>
    >>> # Size mismatch analysis
    >>> size_analyzer = SizeAnalyzer(store)
    >>> recommendations = await size_analyzer.analyze(days=7)
"""

from analytics.waste_models import SizeGap, WasteReport, TrafficRecord, SizeCoverage
from analytics.mock_traffic import generate_mock_traffic, TRAFFIC_DISTRIBUTIONS
from analytics.waste_analyzer import TrafficWasteAnalyzer
from analytics.size_analyzer import SizeAnalyzer
from analytics.fraud_analyzer import FraudAnalyzer
from analytics.recommendation_engine import (
    Recommendation,
    RecommendationType,
    Severity,
    Confidence,
    Evidence,
    Impact,
    Action,
)

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
    "SizeAnalyzer",
    "FraudAnalyzer",
    # Recommendation engine
    "Recommendation",
    "RecommendationType",
    "Severity",
    "Confidence",
    "Evidence",
    "Impact",
    "Action",
]
