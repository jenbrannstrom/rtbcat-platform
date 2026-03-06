# Changelog

All notable changes to Cat-Scan are documented in this file.

> Versioning note (March 5, 2026): canonical OSS release versions use `VERSION` + git tags (`vX.Y.Z`). Historical entries below with `10.x`-`17.x` were internal milestone labels and were not published semver release tags.

## [0.9.2] - 2026-03-05

### Release

- Establish canonical OSS release/version split:
  - Release version from `VERSION` and SemVer git tags (`vX.Y.Z`)
  - Build identity from immutable commit tags (`sha-<short_sha>`)
- CI now enforces release-tag consistency (`v$(cat VERSION)`) and always publishes `sha-*` image tags.
- Runtime health and UI now expose both release and build identity for traceability.
- Added release policy and preflight documentation for reproducible SemVer publishing.

### Operational Follow-Up (2026-03-06)

- Production incident: Authorized Buyers API calls failed with `invalid_grant: account not found` after the `catscan-api@catscan-prod-202601.iam.gserviceaccount.com` service account was disabled.
- Error window observed in logs: `2026-03-06 03:17:21 UTC` to `2026-03-06 04:18:01 UTC`.
- Remediation: re-enabled service account, verified token refresh success on both VMs, and verified AB endpoint listing resumed.
- Post-deploy (`sha-7ba3af4`) contract check `C-EPT-001` initially failed due to stale endpoint data created during the outage window; manual endpoint sync on both VMs restored freshness.

## [17.0.0] - 2026-01-13

### Phase 17: RTB Bidstream & UTC Standardization

Major data model improvements for accurate analytics and clearer naming.

### Breaking Changes

- **Table renamed**: `rtb_funnel` → `rtb_bidstream`
  - Better describes the bid pipeline data (bid_requests → bids → auctions_won → impressions)
  - All indexes and views updated accordingly
- **CSV naming convention changed**: All reports must now use UTC timezone
  - Format: `catscan-{type}-{account_id}-{period}-UTC`
  - Example: `catscan-rtb-pipeline-123456789-yesterday-UTC`

### Added

- **Migration 016**: Renames rtb_funnel → rtb_bidstream
  - Recreates all indexes with proper naming (idx_rtb_bidstream_*)
  - Updates views: v_publisher_waste, v_platform_efficiency, v_hourly_patterns
- **Migration 017**: Adds data_quality column
  - Marks all existing data as 'legacy' (pre-UTC timezone issues)
  - New imports default to 'production' quality
  - Adds production-only views: v_rtb_daily_production, v_rtb_bidstream_production
- **JOIN strategy for per-billing_id funnel metrics**
  - Joins catscan-bidsinauction (has bid metrics) with catscan-quality (has billing_id) on (date, creative_id)
  - Enables billing_id breakdown of bid pipeline metrics that Google's API doesn't allow directly
- **5 CSV report types now documented**:
  1. catscan-bidsinauction - Bid metrics by creative
  2. catscan-quality - Quality/billing data
  3. catscan-funnel-geo - Bidstream by region
  4. catscan-funnel-publishers - Bidstream by publisher
  5. catscan-bid-filtering - Bid filtering reasons

### Data Quality Values

| Value | Description |
|-------|-------------|
| `production` | UTC data (real analytics) - default for new imports |
| `legacy` | Pre-UTC data (wrong timezone) - marked by migration 017 |
| `sample` | Manually marked sample data |

### Migration Steps

```bash
# 1. Backup first
cp ~/.catscan/catscan.db ~/.catscan/catscan.db.backup_v16

# 2. Run migrations
sqlite3 ~/.catscan/catscan.db < migrations/016_rename_rtb_funnel_to_bidstream.sql
sqlite3 ~/.catscan/catscan.db < migrations/017_mark_legacy_timezone_data.sql

# 3. Verify
sqlite3 ~/.catscan/catscan.db "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'rtb%';"
# Should show: rtb_daily, rtb_bidstream, rtb_bid_filtering, rtb_quality
```

### Files Changed

| File | Change |
|------|--------|
| `migrations/016_rename_rtb_funnel_to_bidstream.sql` | New migration |
| `migrations/017_mark_legacy_timezone_data.sql` | New migration |
| `api/routers/analytics/rtb_bidstream.py` | Renamed from rtb_funnel.py, JOIN logic added |
| `analytics/rtb_bidstream_analyzer.py` | Renamed from rtb_funnel_analyzer.py |
| `importers/csv_report_types.py` | Updated naming convention, UTC requirement |
| `DATA_MODEL.md` | CSV Import Reference section, JOIN strategy docs |

---

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
