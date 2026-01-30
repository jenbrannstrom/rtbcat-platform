# Services Module

Business logic services for campaign management and creative health analysis.

## Layering Rules (Postgres-only)

- Routers parse input and call services; no SQL or multi-step logic in routers.
- Services hold business rules and workflows; no SQL in services.
- Repositories hold SQL + row mapping only.
- `PostgresStore` is a temporary shim and should shrink over time.

## Services

| Class | File | Purpose |
|-------|------|---------|
| `CreativeHealthService` | waste_analyzer.py | Evidence-based health signals for creatives (broken videos, low CTR, fraud, etc.) |
| `CampaignAggregationService` | campaign_aggregation.py | Aggregates campaign performance with timeframe context |

## Planned Services

These services are expected as we unmix business logic from data access:

- `PretargetingService` (pretargeting workflows + validation)
- `EndpointsService` (RTB endpoints workflows)
- `SnapshotsService` (snapshot create/list/rollback)
- `ChangesService` (pending changes lifecycle)


## CreativeHealthService

Detects creative health issues and generates actionable insights with evidence.

### Signal Types

- `broken_video` - Video creative that can't play (thumbnail failed)
- `zero_engagement` - High impressions but no clicks over time
- `low_ctr` - CTR in bottom percentile of account
- `high_spend_low_performance` - Spending money on underperforming creative
- `click_fraud` - Suspicious click patterns
- `low_vcr` - Video completion rate below threshold
- `disapproved` - Creative is disapproved but still receiving traffic

### Usage

```python
from services import CreativeHealthService

service = CreativeHealthService()
signals = service.analyze_all_creatives(days=7)

for signal in signals:
    print(f"{signal.creative_id}: {signal.signal_type}")
    print(f"  Observation: {signal.observation}")
    print(f"  Recommendation: {signal.recommendation}")
```

## Related Modules

- `analytics/` - Traffic and QPS analysis (see `TrafficWasteAnalyzer`)
- `importers/` - QPS-specific utilities and fraud detection
