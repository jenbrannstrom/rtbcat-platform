"""Analysis and evaluation components.

.. deprecated::
    This module is maintained for backwards compatibility. New code should use
    the ``analytics`` module instead, which provides:

    - ``analytics.recommendation_engine.RecommendationEngine`` - Modern async engine
    - ``analytics.SizeAnalyzer`` - Size mismatch analysis
    - ``analytics.FraudAnalyzer`` - Fraud detection
    - ``analytics.TrafficWasteAnalyzer`` - Traffic waste analysis

The EvaluationEngine in this module is a sync wrapper that will eventually be
replaced by the analytics module's components.
"""

from analysis.evaluation_engine import (
    EvaluationEngine,
    Recommendation,
    RecommendationType,
)

__all__ = [
    "EvaluationEngine",
    "Recommendation",
    "RecommendationType",
]
