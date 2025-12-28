# Changelog

All notable changes to Cat-Scan are documented in this file.

## [12.0.0] - 2025-12-03

### Phase 12: Schema Cleanup - Single Source of Truth

Eliminate table naming confusion by renaming to clear, distinct names.

### Breaking Changes

- **Table renamed**: `performance_data` → `rtb_daily`
  - THE fact table for all CSV imports
  - Short, clear, unambiguous
- **Table renamed**: `ai_campaigns` → `campaigns`
  - Removed "ai_" prefix - it's just campaigns now
- **Indexes renamed**: `idx_perf_*` → `idx_rtb_*`

### Added

- **Migration script**: `scripts/migrate_schema_v12.py`
  - Automatic backup before migration
  - Renames tables and indexes
  - Safe rollback on failure
- **Updated README.md**: Clear schema documentation with migration instructions

### Migration Steps

```bash
# 1. Backup first (automatic, but good practice)
cp ~/.catscan/catscan.db ~/.catscan/catscan.db.manual_backup

# 2. Run migration
cd creative-intelligence
python scripts/migrate_schema_v12.py

# 3. Verify
python -c "import sqlite3; conn = sqlite3.connect('~/.catscan/catscan.db'); print([t[0] for t in conn.execute('SELECT name FROM sqlite_master WHERE type=\"table\"').fetchall()])"
```

### Why `rtb_daily`?

| Old Name | Problem |
|----------|---------|
| `performance_data` | Confusingly similar to legacy `performance_metrics` |

| New Name | Benefit |
|----------|---------|
| `rtb_daily` | Clearly THE fact table, domain-specific (RTB), describes granularity (daily) |

---

## [11.0.0] - 2025-12-03

### Phase 11: Decision Intelligence

Transform Cat-Scan from a data viewer into a decision engine. Every screen now answers "What's wasting money and what should I do?"

### Added

#### Phase 11.1: Decision Context Foundation
- **Timeframe-aware endpoints**: All `/campaigns` and `/creatives` endpoints now accept `?days=N` parameter (default 7)
- **Campaign aggregation service**: Returns aggregated spend, impressions, clicks, and waste_score per campaign
- **Waste score calculation**: `(reached_queries - impressions) / reached_queries * 100`
- **Warning counts**: Each campaign shows broken_video_count, zero_engagement_count, disapproved_count
- **Active-only filtering**: `?active_only=true` hides creatives with zero activity in timeframe

#### Phase 11.2: Evidence-Based Waste Detection
- **waste_signals table**: New table storing waste signals with full evidence JSON
- **WasteAnalyzerService**: Generates evidence-based signals explaining WHY a creative is flagged
- **Signal types**: broken_video, zero_engagement, low_ctr, high_spend_low_performance, low_vcr, disapproved
- **API endpoints**:
  - `GET /analytics/waste-signals/{creative_id}` - Get signals for a creative
  - `POST /analytics/waste-signals/analyze` - Run analysis on all creatives
  - `POST /analytics/waste-signals/{id}/resolve` - Mark signal as resolved

#### Phase 11.3: Campaign Clustering UX Fix
- **Fixed DnD collision detection**: Changed from `closestCorners` to `pointerWithin` to prevent accidental unassignment on click

#### Phase 11.4: Scale Readiness
- **Pagination infrastructure**: New response models with metadata
- **Paginated endpoints**:
  - `GET /creatives/v2` - Returns `{ data: [...], meta: { total, returned, limit, offset, has_more } }`
  - `GET /campaigns/v2` - Same structure with pagination metadata
- **Page size limits**: Max 200 items per page (configurable)

### API Response Changes

#### Campaign Response (Enhanced)
```json
{
  "id": "campaign_123",
  "name": "Brand X Videos",
  "creative_count": 45,
  "timeframe_days": 7,
  "metrics": {
    "total_spend_micros": 125000000,
    "total_impressions": 450000,
    "total_clicks": 2250,
    "total_reached_queries": 580000,
    "avg_cpm": 277.78,
    "avg_ctr": 0.50,
    "waste_score": 22.41
  },
  "warnings": {
    "broken_video_count": 3,
    "zero_engagement_count": 12,
    "high_spend_low_performance": 2,
    "disapproved_count": 0
  }
}
```

#### Waste Signal Response
```json
{
  "id": 1,
  "creative_id": "cr-12345",
  "signal_type": "broken_video",
  "confidence": "high",
  "evidence": {
    "impressions": 45000,
    "spend_micros": 12500000,
    "thumbnail_status": "failed",
    "error_type": "media_timeout"
  },
  "observation": "Video thumbnail generation failed (media_timeout). 45,000 impressions served, $12.50 spent. Users likely can't play this video.",
  "recommendation": "Pause creative immediately and contact advertiser to fix video asset.",
  "detected_at": "2025-12-03T00:00:00Z",
  "resolved_at": null
}
```

### Database Changes
- Added `waste_signals` table for evidence-based signal storage
- Added indexes for timeframe queries on performance_data

### Migration Notes
- Run `scripts/reset_database.py` to add new tables (preserves existing data)
- Existing `/creatives` and `/campaigns` endpoints maintain backwards compatibility
- New `/v2` endpoints return pagination metadata

---

## [10.5.0] - 2025-12-02

### Status Audit
- Identified gaps in campaign timeframe filtering
- Documented DnD collision bug
- Established Phase 11 requirements

---

## [10.3.0] - 2025-11-30

### Added
- Multi-seat hierarchy support
- Campaign clustering with AI
- Thumbnail generation lifecycle

---

## [10.0.0] - 2025-11-28

### Initial Platform
- Google RTB API integration
- CSV performance data import
- Waste detection (boolean flags)
- Dashboard UI with creative grid
