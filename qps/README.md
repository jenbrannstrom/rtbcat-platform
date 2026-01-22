# QPS Data Import Module

This module handles **data import** from BigQuery CSV exports and other RTB data sources.
Analysis of imported data happens in the `analytics/` module.

## Importers

Use the importer that matches your CSV format:

## Recommended entry points

- **Default for most CSVs:** `qps/unified_importer.py`
  - Auto-detects report type and column mapping.
  - Works across multiple CSV layouts.
- **Strict/validated performance detail imports:** `qps/importer.py`
  - Requires specific columns for full RTB analysis.

## Specialized importers

- `qps/funnel_importer.py`: RTB funnel pipeline reports (bid requests, bids, auctions won).
- `qps/quality_importer.py`: Quality signals (fraud/viewability metrics).
- `qps/bid_filtering_importer.py`: Bid filtering reason reports.
- `qps/smart_importer.py`: Detects report type and routes to the correct specialized importer.

## Supporting modules

- `qps/utils.py`: Shared parsing helpers and DB path.
- `qps/flexible_mapper.py`: Column mapping and report type detection logic used by the unified importer.
- `qps/models.py`: Data models for import results.
- `qps/constants.py`: Account IDs, config names, size mappings.

## Legacy Analyzers (to be consolidated)

These analyzers exist here for CLI compatibility but will be consolidated into `analytics/`:

| File | Consolidates With |
|------|-------------------|
| `size_analyzer.py` | `analytics/size_analyzer.py` |
| `fraud_detector.py` | `analytics/fraud_analyzer.py` |
| `config_tracker.py` | `analytics/config_analyzer.py` (new) |

For analysis, prefer using the `analytics/` module directly.
