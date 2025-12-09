# Phase 26: Upload Tracking & Database Features

This document summarizes the new database features implemented in Phase 26, including upload tracking, newly uploaded creatives detection, and pretargeting settings history.

## Overview

Three main features have been added:

1. **Upload Tracking Dashboard** - Monitor CSV import health with anomaly detection
2. **Newly Uploaded Creatives** - Track creatives first seen within a time period
3. **Pretargeting Settings History** - Audit trail for pretargeting configuration changes

---

## 1. Upload Tracking Dashboard

### Purpose
Provides visibility into CSV import health, allowing users to:
- See which days have data from CSV uploads
- Monitor upload success/failure status
- Track file sizes and row counts
- Detect anomalies (sudden drops or spikes in data volume)

### Database Schema

#### Table: `daily_upload_summary`
```sql
CREATE TABLE daily_upload_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    upload_date DATE NOT NULL UNIQUE,
    total_uploads INTEGER DEFAULT 0,
    successful_uploads INTEGER DEFAULT 0,
    failed_uploads INTEGER DEFAULT 0,
    total_rows_written INTEGER DEFAULT 0,
    total_file_size_bytes INTEGER DEFAULT 0,
    avg_rows_per_upload REAL DEFAULT 0,
    min_rows INTEGER,
    max_rows INTEGER,
    has_anomaly INTEGER DEFAULT 0,
    anomaly_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Enhanced: `import_history`
Added column: `file_size_bytes INTEGER DEFAULT 0`

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/uploads/tracking` | GET | Get daily upload summary with anomaly flags |
| `/uploads/history` | GET | Get detailed import history records |

### UI Location
- **Route:** `/uploads`
- **Features:**
  - Summary cards (days tracked, total uploads, total rows, anomalies count)
  - Daily upload table with status indicators
  - Anomaly warnings with trend indicators (spike vs drop)
  - Recent imports list with file details

### Anomaly Detection Logic
- Compares current day's row count to 7-day rolling average
- **Warning thresholds:**
  - Drop: Row count < 50% of average
  - Spike: Row count > 200% of average
- Yellow warning icon displayed when anomaly detected
- Reason text explains the deviation

### UI Design Suggestions

```
+------------------------------------------------------------------+
| Upload Tracking                                                    |
+------------------------------------------------------------------+
| [30] Days | [124] Uploads | [2.4M] Rows | [2] Anomalies          |
+------------------------------------------------------------------+
| Date        | Status | File Size | Rows Written | Alert          |
|-------------|--------|-----------|--------------|----------------|
| Sat Dec 7   |   ✓    |  45.2 MB  |    125,432   |      -         |
| Fri Dec 6   |   ✓    |  44.8 MB  |    122,156   |      -         |
| Thu Dec 5   |   ⚠    |  12.1 MB  |     31,245   |   ⚠ ↓ Drop    |
| Wed Dec 4   |   ✓    |  46.1 MB  |    128,901   |      -         |
+------------------------------------------------------------------+
```

---

## 2. Newly Uploaded Creatives

### Purpose
Identify creatives that were first seen in CSV imports within a selected time period. Useful for:
- Tracking new creative launches
- Identifying recently added inventory
- Filtering the creatives list by "freshness"

### Database Schema

#### Enhanced: `creatives`
```sql
ALTER TABLE creatives ADD COLUMN first_seen_at TIMESTAMP;
ALTER TABLE creatives ADD COLUMN first_import_batch_id TEXT;
CREATE INDEX idx_creatives_first_seen ON creatives(first_seen_at DESC);
```

### API Endpoint

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/creatives/newly-uploaded` | GET | Get creatives first seen within period |

**Parameters:**
- `days` (int): Lookback period (default: 7, max: 90)
- `limit` (int): Max results (default: 100, max: 1000)
- `format` (string): Filter by format (HTML, VIDEO, NATIVE)

**Response:**
```json
{
  "creatives": [...],
  "total_count": 42,
  "period_start": "2024-12-01",
  "period_end": "2024-12-08"
}
```

### UI Integration Suggestions

Add a "Newly Uploaded" filter/tab to the Creatives page:

```
+------------------------------------------------------------------+
| Creatives                                                          |
+------------------------------------------------------------------+
| [All] [Newly Uploaded (42)] [Video] [Display] [Native]            |
|                                                                    |
| Period: [Last 7 days ▼]                                           |
+------------------------------------------------------------------+
| ID        | Format | Size     | First Seen  | Spend    | Impr    |
|-----------|--------|----------|-------------|----------|---------|
| abc123    | VIDEO  | 1920x1080| Dec 7, 2024 | $1,234   | 45,678  |
| def456    | HTML   | 300x250  | Dec 6, 2024 | $567     | 23,456  |
+------------------------------------------------------------------+
```

---

## 3. Pretargeting Settings History

### Purpose
Track all changes made to pretargeting configurations, providing:
- Audit trail of who changed what and when
- Ability to review historical configurations
- Change source tracking (user vs API sync)

### Database Schema

#### Table: `pretargeting_history`
```sql
CREATE TABLE pretargeting_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_id TEXT NOT NULL,
    bidder_id TEXT NOT NULL,
    change_type TEXT NOT NULL,        -- 'create', 'update', 'delete'
    field_changed TEXT,               -- Which field was modified
    old_value TEXT,                   -- Previous value (JSON if complex)
    new_value TEXT,                   -- New value (JSON if complex)
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    changed_by TEXT,                  -- User identifier if available
    change_source TEXT DEFAULT 'api_sync',  -- 'user', 'api_sync', 'system'
    raw_config_snapshot TEXT,         -- Full config at time of change
    FOREIGN KEY (config_id) REFERENCES pretargeting_configs(config_id)
);
```

### API Endpoint

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/settings/pretargeting/history` | GET | Get pretargeting change history |

**Parameters:**
- `config_id` (string): Filter by specific config
- `billing_id` (string): Filter by billing ID
- `days` (int): Lookback period (default: 30, max: 365)

### Automatic Tracking
Changes are automatically recorded when:
- User renames a pretargeting config via `/settings/pretargeting/{billing_id}/name`
- Config state changes during API sync (future enhancement)

### UI Integration Suggestions

Add a "History" tab to the RTB Settings page:

```
+------------------------------------------------------------------+
| RTB Settings > Pretargeting > History                              |
+------------------------------------------------------------------+
| Filter: [All Configs ▼] [Last 30 days ▼]                          |
+------------------------------------------------------------------+
| Date/Time          | Config      | Change        | Details        |
|--------------------|-------------|---------------|----------------|
| Dec 7, 3:45 PM     | 12345678    | Name Updated  | "Config A" →   |
|                    |             |               | "US Mobile"    |
| Dec 5, 10:22 AM    | 87654321    | State Changed | ACTIVE →       |
|                    |             |               | SUSPENDED      |
| Dec 3, 2:15 PM     | 12345678    | Geos Updated  | +US, +CA, -MX  |
+------------------------------------------------------------------+
```

---

## Implementation Summary

### Files Modified

#### Backend (creative-intelligence)
- `storage/sqlite_store.py` - Added new migrations for schema changes
- `qps/importer.py` - Enhanced import tracking with file size and anomaly detection
- `api/main.py` - Added new API endpoints

#### Frontend (dashboard)
- `src/lib/api.ts` - Added API client functions
- `src/app/uploads/page.tsx` - New upload tracking page (created)

### Database Migrations
All changes are implemented as SQLite migrations that run automatically on startup:
- `ALTER TABLE import_history ADD COLUMN file_size_bytes`
- `CREATE TABLE daily_upload_summary`
- `ALTER TABLE creatives ADD COLUMN first_seen_at`
- `ALTER TABLE creatives ADD COLUMN first_import_batch_id`
- `CREATE TABLE pretargeting_history`

---

## Future Enhancements

### Upload Tracking
1. **Email alerts** - Notify when anomalies detected
2. **Weekly digest** - Summary report of upload health
3. **Data gap detection** - Alert when expected dates are missing
4. **Trend visualization** - Chart showing row counts over time

### Newly Uploaded Creatives
1. **Creatives page integration** - Add filter toggle to main creatives view
2. **Performance comparison** - Compare new vs established creative performance
3. **Auto-categorization** - Suggest campaigns for new creatives based on similarity

### Pretargeting History
1. **Full config diff** - Show complete before/after comparison
2. **Rollback capability** - Restore previous configuration
3. **Sync change tracking** - Record changes from Google API syncs
4. **User attribution** - Track which user made changes (requires auth)

---

## API Reference

### GET /uploads/tracking
```bash
curl "http://localhost:8000/uploads/tracking?days=30"
```

### GET /uploads/history
```bash
curl "http://localhost:8000/uploads/history?limit=50&offset=0"
```

### GET /creatives/newly-uploaded
```bash
curl "http://localhost:8000/creatives/newly-uploaded?days=7&limit=100"
```

### GET /settings/pretargeting/history
```bash
curl "http://localhost:8000/settings/pretargeting/history?days=30"
```

---

## Testing

### Verify Schema Migrations
```bash
sqlite3 ~/.catscan/catscan.db ".schema daily_upload_summary"
sqlite3 ~/.catscan/catscan.db ".schema pretargeting_history"
sqlite3 ~/.catscan/catscan.db "PRAGMA table_info(creatives)" | grep first_seen
sqlite3 ~/.catscan/catscan.db "PRAGMA table_info(import_history)" | grep file_size
```

### Test API Endpoints
```bash
# Upload tracking
curl http://localhost:8000/uploads/tracking

# Import history
curl http://localhost:8000/uploads/history

# Newly uploaded creatives
curl http://localhost:8000/creatives/newly-uploaded

# Pretargeting history
curl http://localhost:8000/settings/pretargeting/history
```

### Test Upload Anomaly Detection
1. Import a CSV with normal row count
2. Import a CSV with significantly fewer rows
3. Check `/uploads/tracking` - should show anomaly warning
