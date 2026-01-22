# Importers Module

This module handles **data import** from Authorized Buyers CSV reports.
Analysis of imported data happens in the `analytics/` module.

## Importers

Use the importer that matches your CSV format.

### Recommended entry points

- **Default for most CSVs:** `importers/unified_importer.py`
  - Auto-detects report type and column mapping.
  - Works across multiple CSV layouts.
- **Strict/validated performance detail imports:** `importers/importer.py`
  - Requires specific columns for full RTB analysis.

### Specialized importers

- `importers/funnel_importer.py`: RTB funnel pipeline reports (bid requests, bids, auctions won).
- `importers/quality_importer.py`: Quality signals (fraud/viewability metrics).
- `importers/bid_filtering_importer.py`: Bid filtering reason reports.
- `importers/smart_importer.py`: Detects report type and routes to the correct specialized importer.

## Supporting modules

- `importers/utils.py`: Shared parsing helpers and DB path.
- `importers/flexible_mapper.py`: Column mapping and report type detection logic.
- `importers/models.py`: Data models for import results.
- `importers/constants.py`: Account IDs, config names, size mappings.
- `importers/account_mapper.py`: Maps billing account IDs to bidder/seat IDs.
- `importers/csv_report_types.py`: Defines CSV report type detection and schema validation.
