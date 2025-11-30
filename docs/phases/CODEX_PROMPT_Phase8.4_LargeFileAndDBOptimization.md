# ChatGPT Codex CLI Prompt: Phase 8.4 - Large File Handling & Database Optimization

**Project:** RTB.cat Creative Intelligence Platform  
**Context:** Phase 8.3 CSV parsing is complete. Now we need to handle production-scale data.  
**Problem:** CSV files from Google Authorized Buyers can be 200MB+ with millions of rows  
**Goal:** Seamless, forgiving upload experience that handles any file size

---

## 🎯 Your Mission

You are taking over the RTB.cat project. The previous developer (Claude CLI) completed flexible CSV parsing:
- ✅ Column name normalization (`#Creative ID` → `creative_id`)
- ✅ Date format conversion (`MM/DD/YY` → `YYYY-MM-DD`)
- ✅ Currency symbol removal (`$10.50` → `10.50`)
- ✅ Hourly data aggregation to daily

**Your task:** Make this work with 200MB+ files without crashing the browser or server.

---

## 📋 Requirements

### 1. Frontend: Chunked Streaming Upload

**Problem:** Loading a 200MB file into browser memory causes:
- Browser tab crash
- UI freeze during parsing
- Memory exhaustion

**Solution:** Stream the file in chunks, never holding the whole file in memory.

**Implementation approach:**

```typescript
// dashboard/src/lib/chunked-uploader.ts

const CHUNK_SIZE = 1024 * 1024; // 1MB chunks

export async function* streamFile(file: File): AsyncGenerator<string> {
  const reader = file.stream().getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  
  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      if (buffer) yield buffer;
      break;
    }
    
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || ''; // Keep incomplete line in buffer
    
    for (const line of lines) {
      yield line;
    }
  }
}
```

**UI requirements:**
- Show "Processing row X of ~Y" (estimate Y from file size ÷ avg row size)
- Progress bar updates smoothly
- Cancel button that actually works (AbortController)
- Memory usage stays flat (no accumulation)

---

### 2. Web Worker for Parsing (Don't Block UI)

**Problem:** Parsing 2 million rows on main thread freezes the browser.

**Solution:** Offload parsing to a Web Worker.

```typescript
// dashboard/src/workers/csv-parser.worker.ts

import Papa from 'papaparse';

self.onmessage = async (e: MessageEvent) => {
  const { chunk, isHeader, mappings } = e.data;
  
  const parsed = Papa.parse(chunk, {
    header: isHeader,
    skipEmptyLines: true,
  });
  
  // Transform using existing normalization logic
  const transformed = parsed.data.map(row => normalizeRow(row, mappings));
  
  // Send batch to main thread
  self.postMessage({ 
    type: 'batch',
    rows: transformed,
    count: transformed.length 
  });
};
```

**Main thread:**
- Receives batches of ~10,000 rows
- Sends each batch to server API
- Updates progress UI
- Never holds more than current batch in memory

---

### 3. Backend: Streaming API Endpoint

**Problem:** Current `/api/performance/import` expects entire file in memory.

**Solution:** New streaming endpoint that accepts row batches.

```python
# api/performance.py - NEW streaming endpoint

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import json

router = APIRouter()

@router.post("/api/performance/import/stream")
async def import_stream(request: Request):
    """
    Accepts NDJSON stream of performance rows.
    Inserts in batches of 1000 for efficiency.
    Returns progress via Server-Sent Events.
    """
    batch = []
    total_imported = 0
    
    async for chunk in request.stream():
        lines = chunk.decode().strip().split('\n')
        for line in lines:
            if line:
                row = json.loads(line)
                batch.append(row)
                
                if len(batch) >= 1000:
                    await insert_batch(batch)
                    total_imported += len(batch)
                    batch = []
    
    # Insert remaining
    if batch:
        await insert_batch(batch)
        total_imported += len(batch)
    
    return {"imported": total_imported}
```

---

### 4. Database Optimization: Normalization

**Problem:** Storing repeated strings wastes space and slows queries.

Example of waste in current design:
```
Row 1: billing_id="123456789", country="United States", app_name="Candy Crush Saga"
Row 2: billing_id="123456789", country="United States", app_name="Candy Crush Saga"
... × 2 million rows
```

**Solution:** Normalize into lookup tables with integer foreign keys.

#### New Schema

```sql
-- Lookup Tables (store each unique value ONCE)

CREATE TABLE IF NOT EXISTS billing_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    billing_id TEXT UNIQUE NOT NULL,
    name TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS geographies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    country_code TEXT,        -- 'US', 'GB', etc.
    country_name TEXT,        -- 'United States', 'United Kingdom'
    city_name TEXT,           -- nullable, for city-level data
    UNIQUE(country_code, city_name)
);
CREATE INDEX idx_geo_country ON geographies(country_code);

CREATE TABLE IF NOT EXISTS apps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    app_id TEXT UNIQUE,       -- Google's app ID
    app_name TEXT,
    platform TEXT,            -- 'iOS', 'Android', 'Web'
    store_url TEXT,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_apps_name ON apps(app_name);

CREATE TABLE IF NOT EXISTS publishers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    publisher_id TEXT UNIQUE,
    publisher_name TEXT,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### Updated performance_metrics Table

```sql
-- performance_metrics now uses INTEGER foreign keys (4 bytes each)
-- instead of TEXT strings (20-100 bytes each)

CREATE TABLE IF NOT EXISTS performance_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creative_id INTEGER NOT NULL,
    date DATE NOT NULL,
    
    -- Foreign keys (integers, not strings!)
    geo_id INTEGER REFERENCES geographies(id),
    app_id INTEGER REFERENCES apps(id),
    billing_account_id INTEGER REFERENCES billing_accounts(id),
    publisher_id INTEGER REFERENCES publishers(id),
    
    -- Metrics (unchanged)
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    spend REAL DEFAULT 0,
    
    -- Composite unique constraint for upsert
    UNIQUE(creative_id, date, geo_id, app_id)
);

-- Indexes for common queries
CREATE INDEX idx_perf_creative_date ON performance_metrics(creative_id, date);
CREATE INDEX idx_perf_date ON performance_metrics(date);
CREATE INDEX idx_perf_geo ON performance_metrics(geo_id);
CREATE INDEX idx_perf_spend ON performance_metrics(spend DESC);
```

#### Migration Script

```python
# storage/migrations/009_normalize_lookups.py

def upgrade(db):
    """
    1. Create lookup tables
    2. Migrate existing data (if any)
    3. Add foreign key columns to performance_metrics
    """
    
    # Create lookup tables
    db.execute("""
        CREATE TABLE IF NOT EXISTS billing_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            billing_id TEXT UNIQUE NOT NULL,
            name TEXT
        )
    """)
    
    db.execute("""
        CREATE TABLE IF NOT EXISTS geographies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            country_code TEXT,
            country_name TEXT,
            city_name TEXT,
            UNIQUE(country_code, city_name)
        )
    """)
    
    db.execute("""
        CREATE TABLE IF NOT EXISTS apps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            app_id TEXT UNIQUE,
            app_name TEXT,
            platform TEXT
        )
    """)
    
    db.execute("""
        CREATE TABLE IF NOT EXISTS publishers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            publisher_id TEXT UNIQUE,
            publisher_name TEXT
        )
    """)
    
    # Pre-populate common geographies for faster lookups
    common_countries = [
        ('US', 'United States'),
        ('GB', 'United Kingdom'),
        ('CA', 'Canada'),
        ('AU', 'Australia'),
        ('DE', 'Germany'),
        ('FR', 'France'),
        ('JP', 'Japan'),
        ('BR', 'Brazil'),
        ('IN', 'India'),
        ('MX', 'Mexico'),
    ]
    
    for code, name in common_countries:
        db.execute(
            "INSERT OR IGNORE INTO geographies (country_code, country_name) VALUES (?, ?)",
            (code, name)
        )
    
    db.commit()
```

---

### 5. Lookup-On-Insert Pattern

When inserting performance data, resolve strings to IDs:

```python
# storage/performance_repository.py

from functools import lru_cache

class PerformanceRepository:
    def __init__(self, db):
        self.db = db
        self._geo_cache = {}
        self._app_cache = {}
    
    def get_or_create_geo_id(self, country_name: str, city_name: str = None) -> int:
        """Get existing geo ID or create new entry. Cached."""
        cache_key = (country_name, city_name)
        
        if cache_key in self._geo_cache:
            return self._geo_cache[cache_key]
        
        # Try to find existing
        result = self.db.execute("""
            SELECT id FROM geographies 
            WHERE country_name = ? AND (city_name = ? OR (city_name IS NULL AND ? IS NULL))
        """, (country_name, city_name, city_name)).fetchone()
        
        if result:
            self._geo_cache[cache_key] = result[0]
            return result[0]
        
        # Create new
        cursor = self.db.execute("""
            INSERT INTO geographies (country_name, city_name, country_code)
            VALUES (?, ?, ?)
        """, (country_name, city_name, self._country_to_code(country_name)))
        
        geo_id = cursor.lastrowid
        self._geo_cache[cache_key] = geo_id
        return geo_id
    
    def get_or_create_app_id(self, app_id: str, app_name: str = None) -> int:
        """Get existing app ID or create new entry. Cached."""
        if app_id in self._app_cache:
            return self._app_cache[app_id]
        
        result = self.db.execute(
            "SELECT id FROM apps WHERE app_id = ?", (app_id,)
        ).fetchone()
        
        if result:
            self._app_cache[app_id] = result[0]
            return result[0]
        
        cursor = self.db.execute(
            "INSERT INTO apps (app_id, app_name) VALUES (?, ?)",
            (app_id, app_name)
        )
        
        internal_id = cursor.lastrowid
        self._app_cache[app_id] = internal_id
        return internal_id
    
    def insert_batch(self, rows: list[dict]) -> int:
        """Insert batch of performance rows, resolving lookups."""
        
        values = []
        for row in rows:
            geo_id = self.get_or_create_geo_id(
                row.get('country') or row.get('geography'),
                row.get('city')
            )
            app_id = self.get_or_create_app_id(
                row.get('app_id'),
                row.get('app_name')
            ) if row.get('app_id') else None
            
            values.append((
                row['creative_id'],
                row['date'],
                geo_id,
                app_id,
                row.get('impressions', 0),
                row.get('clicks', 0),
                row.get('spend', 0),
            ))
        
        self.db.executemany("""
            INSERT INTO performance_metrics 
            (creative_id, date, geo_id, app_id, impressions, clicks, spend)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(creative_id, date, geo_id, app_id) DO UPDATE SET
                impressions = impressions + excluded.impressions,
                clicks = clicks + excluded.clicks,
                spend = spend + excluded.spend
        """, values)
        
        self.db.commit()
        return len(values)
    
    @staticmethod
    def _country_to_code(name: str) -> str:
        """Convert country name to ISO code."""
        mapping = {
            'united states': 'US',
            'united kingdom': 'GB',
            'canada': 'CA',
            'australia': 'AU',
            'germany': 'DE',
            'france': 'FR',
            'japan': 'JP',
            'brazil': 'BR',
            'india': 'IN',
            'mexico': 'MX',
            # ... add more as needed
        }
        return mapping.get(name.lower(), name[:2].upper())
```

---

### 6. Storage Comparison

**Before normalization (current):**
```
2,000,000 rows × ~200 bytes/row = ~400 MB
(Each row stores full country name, app name, billing ID as strings)
```

**After normalization:**
```
2,000,000 rows × ~40 bytes/row = ~80 MB
+ ~10,000 unique geos × 100 bytes = ~1 MB
+ ~5,000 unique apps × 150 bytes = ~0.75 MB
+ ~100 billing accounts × 50 bytes = ~5 KB

Total: ~82 MB (5x smaller!)
```

**Query performance improvement:**
- Integer comparisons are 10-100x faster than string comparisons
- Indexes on integers are smaller and faster
- JOINs are cheap with proper indexing

---

### 7. Updated Import Flow

```
┌──────────────────────────────────────────────────────────────────┐
│                     LARGE FILE IMPORT FLOW                        │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  User drags 200MB CSV file                                        │
│           │                                                       │
│           ▼                                                       │
│  ┌─────────────────────┐                                         │
│  │ Browser reads first │   Only first 10KB to detect format      │
│  │ chunk for headers   │                                         │
│  └──────────┬──────────┘                                         │
│             │                                                     │
│             ▼                                                     │
│  ┌─────────────────────┐                                         │
│  │ Show preview (10    │   User confirms mapping looks right     │
│  │ rows) + column map  │   "Detected: #Creative ID → creative_id"│
│  └──────────┬──────────┘                                         │
│             │                                                     │
│             ▼                                                     │
│  ┌─────────────────────┐                                         │
│  │ User clicks Import  │                                         │
│  └──────────┬──────────┘                                         │
│             │                                                     │
│             ▼                                                     │
│  ┌─────────────────────┐      ┌─────────────────────┐           │
│  │ Web Worker streams  │ ───▶ │ Batches of 10K rows │           │
│  │ file in chunks      │      │ sent to server      │           │
│  └─────────────────────┘      └──────────┬──────────┘           │
│                                          │                       │
│                                          ▼                       │
│                               ┌─────────────────────┐           │
│                               │ Server resolves     │           │
│                               │ lookups, inserts    │           │
│                               │ with UPSERT         │           │
│                               └──────────┬──────────┘           │
│                                          │                       │
│                                          ▼                       │
│  ┌─────────────────────┐      ┌─────────────────────┐           │
│  │ Progress: 1.2M of   │ ◀─── │ Returns row count   │           │
│  │ ~2M rows (60%)      │      │ after each batch    │           │
│  └─────────────────────┘      └─────────────────────┘           │
│                                                                   │
│  Memory usage: Flat ~50MB (never grows beyond batch size)        │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

### 8. Files to Create/Modify

**New files:**
```
dashboard/src/workers/csv-parser.worker.ts     # Web Worker for parsing
dashboard/src/lib/chunked-uploader.ts          # Streaming upload logic
dashboard/src/lib/upload-manager.ts            # Coordinates worker + API
api/storage/migrations/009_normalize_lookups.py # DB migration
api/storage/performance_repository.py          # Lookup resolution
```

**Modified files:**
```
dashboard/src/app/import/page.tsx              # Use chunked uploader
api/performance.py                              # Add streaming endpoint
```

---

### 9. Testing Checklist

After implementation, verify:

- [ ] 200MB file uploads without browser crash
- [ ] Memory usage stays under 100MB during import
- [ ] Progress bar updates smoothly (not jerky)
- [ ] Cancel button works mid-import
- [ ] Lookup tables populated correctly
- [ ] Foreign keys resolve properly
- [ ] Query performance under 100ms for 2M rows
- [ ] Duplicate imports aggregate (not duplicate) data

---

### 10. Error Handling (Forgiving Experience)

Make every possible error recoverable:

```typescript
// Error recovery strategies

const ERROR_HANDLERS = {
  // Row-level errors: skip bad rows, continue import
  INVALID_ROW: (row, error) => {
    console.warn(`Skipping row: ${error.message}`);
    stats.skippedRows++;
    return null; // Skip this row
  },
  
  // Batch-level errors: retry with exponential backoff
  BATCH_FAILED: async (batch, error, attempt) => {
    if (attempt < 3) {
      await sleep(1000 * Math.pow(2, attempt));
      return 'retry';
    }
    return 'skip'; // Skip batch after 3 retries
  },
  
  // Network errors: pause and offer resume
  NETWORK_ERROR: () => {
    showToast('Connection lost. Click Resume when ready.');
    return 'pause';
  },
  
  // Unknown column: auto-map if possible
  UNKNOWN_COLUMN: (column) => {
    const guess = fuzzyMatch(column, KNOWN_COLUMNS);
    if (guess.confidence > 0.8) {
      return { map: guess.column };
    }
    return { ignore: true }; // Skip unknown columns
  }
};
```

---

## 📍 Location Reference

```
Project root: /home/jen/Documents/rtbcat-platform/

Frontend:
  dashboard/src/app/import/page.tsx
  dashboard/src/lib/csv-parser.ts
  dashboard/src/lib/csv-validator.ts

Backend:
  api/performance.py
  api/storage/migrations/
  
Database:
  ~/.rtbcat/rtbcat.db

Documentation:
  docs/phases/phase-8.3/
```

---

## 🚀 Start Here

1. **Read existing code:**
   ```bash
   cat dashboard/src/lib/csv-parser.ts
   cat dashboard/src/lib/csv-validator.ts
   cat api/performance.py
   ```

2. **Run migration:**
   ```bash
   cd /home/jen/Documents/rtbcat-platform
   python -m api.storage.migrations.009_normalize_lookups
   ```

3. **Implement chunked uploader** (start with `chunked-uploader.ts`)

4. **Test with sample file**, then scale up

5. **After code changes:**
   ```bash
   sudo systemctl restart rtbcat-api
   ```

---

## ⚠️ Important Notes

- **Never manage the server directly** - use `sudo systemctl restart rtbcat-api`
- **Database is SQLite** at `~/.rtbcat/rtbcat.db`
- **Frontend uses Next.js 14** with App Router
- **Backend uses FastAPI** with uvicorn

---

**Good luck! The goal is a seamless experience where users drop a 200MB file and it "just works." 🚀**
