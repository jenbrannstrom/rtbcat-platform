# Analytics Module

This module provides analysis capabilities for RTB traffic, creative performance, and QPS optimization.

## Analyzers

| Class | File | Purpose |
|-------|------|---------|
| `TrafficWasteAnalyzer` | waste_analyzer.py | Compares bid requests vs creative inventory to identify size gaps |
| `GeoAnalyzer` | geo_analyzer.py | Analyzes geographic performance and identifies wasteful regions |
| `GeoWasteAnalyzer` | geo_waste_analyzer.py | Geographic QPS waste analysis (CTR below average, high query/low impression) |
| `FraudAnalyzer` | fraud_analyzer.py | Detects suspicious publisher and app patterns |
| `CreativeAnalyzer` | creative_analyzer.py | Creative health: low CTR, zero engagement, broken videos |
| `SizeCoverageAnalyzer` | size_coverage_analyzer.py | Size-based QPS waste comparing traffic vs inventory |
| `SizeAnalyzer` | size_analyzer.py | Size mismatch recommendations (block or add creatives) |
| `RTBFunnelAnalyzer` | rtb_bidstream_analyzer.py | Parses RTB funnel data from Authorized Buyers CSVs |
| `ConfigAnalyzer` | config_analyzer.py | Pretargeting configuration efficiency |

## Services

| Class | File | Purpose |
|-------|------|---------|
| `RecommendationEngine` | recommendation_engine.py | Orchestrates all analyzers and aggregates recommendations |
| `PretargetingRecommender` | pretargeting_recommender.py | Generates optimal pretargeting config recommendations |
| `QPSOptimizer` | qps_optimizer.py | QPS optimization joining funnel, daily, and quality data |

## Usage

```python
from analytics import TrafficWasteAnalyzer
from storage import SQLiteStore

store = SQLiteStore()
await store.initialize()

# Traffic waste analysis
analyzer = TrafficWasteAnalyzer(store)
report = await analyzer.analyze_waste(buyer_id="456", days=7)
print(f"Waste: {report.waste_percentage}%")
```

## Related Modules

- `services/` - Business logic services including `CreativeHealthService` for creative-level health analysis
- `importers/` - QPS-specific analyzers and the `FraudSignalDetector`
