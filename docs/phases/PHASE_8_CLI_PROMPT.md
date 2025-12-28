# Claude CLI Prompt: Phase 8.1 - Performance Data Foundation

## 🎯 Objective

Build the database schema and data import system for performance tracking (spend, clicks, impressions, CPM, CPC) in RTBcat Creative Intelligence platform.

This is the **critical foundation** for:
- Sorting creatives by spend
- AI opportunity detection
- Geographic performance insights
- Campaign performance analysis

---

## 📋 Context

**Current State:**
- Platform has 652 creatives from Google Authorized Buyers API
- Database: SQLite at ~/.rtbcat/rtbcat.db
- Tables: creatives, campaigns, buyer_seats, rtb_traffic
- No performance data (spend, clicks, impressions)

**Goal:**
Add performance tracking so we can:
1. Sort creatives by spend (yesterday, 7d, 30d, all-time)
2. Show performance badges on creative cards
3. Enable opportunity detection (Phase 10)
4. Support geographic performance analysis

---

## 🗄️ Part 1: Database Schema Extension

### **New Table: performance_metrics**

Create a table to store granular performance data:

```sql
CREATE TABLE performance_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- SQLite
    -- id SERIAL PRIMARY KEY,  -- PostgreSQL
    
    -- Foreign key
    creative_id INTEGER NOT NULL REFERENCES creatives(id) ON DELETE CASCADE,
    
    -- Time dimension
    date DATE NOT NULL,
    hour INTEGER CHECK (hour >= 0 AND hour <= 23),  -- Optional hourly granularity
    
    -- Performance metrics
    impressions BIGINT DEFAULT 0 CHECK (impressions >= 0),
    clicks BIGINT DEFAULT 0 CHECK (clicks >= 0 AND clicks <= impressions),
    spend DECIMAL(12,2) DEFAULT 0 CHECK (spend >= 0),
    
    -- Calculated or imported
    cpm DECIMAL(8,4),  -- Cost per mille (spend / impressions * 1000)
    cpc DECIMAL(8,4),  -- Cost per click (spend / clicks)
    
    -- Dimensions
    geography VARCHAR(2),  -- ISO country code: BR, IE, US, etc.
    device_type VARCHAR(20),  -- mobile, desktop, tablet
    placement VARCHAR(100),  -- Optional: site/app placement
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Prevent duplicates
    UNIQUE(creative_id, date, hour, geography, device_type)
);

-- Indexes for fast querying
CREATE INDEX idx_perf_creative_date ON performance_metrics(creative_id, date DESC);
CREATE INDEX idx_perf_geo_date ON performance_metrics(geography, date DESC);
CREATE INDEX idx_perf_spend ON performance_metrics(spend DESC);
CREATE INDEX idx_perf_cpc ON performance_metrics(cpc ASC);
CREATE INDEX idx_perf_date ON performance_metrics(date DESC);
```

**Important Notes:**
- Support BOTH SQLite and PostgreSQL (check which DB is being used)
- Hour column is optional (NULL for daily aggregates)
- Unique constraint prevents duplicate imports
- Indexes created AFTER initial data load (for performance)

---

### **Update Table: campaigns**

Add performance aggregation columns (cached for speed):

```sql
ALTER TABLE campaigns ADD COLUMN total_spend_7d DECIMAL(12,2) DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN total_spend_30d DECIMAL(12,2) DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN total_spend_all_time DECIMAL(12,2) DEFAULT 0;
ALTER TABLE campaigns ADD COLUMN avg_cpc_7d DECIMAL(8,4);
ALTER TABLE campaigns ADD COLUMN avg_cpm_7d DECIMAL(8,4);
ALTER TABLE campaigns ADD COLUMN top_geography VARCHAR(2);
ALTER TABLE campaigns ADD COLUMN top_device_type VARCHAR(20);
ALTER TABLE campaigns ADD COLUMN last_performance_update TIMESTAMP;
```

**Why Cache These?**
- Calculating campaign totals from millions of rows is slow
- Update these nightly or after performance import
- Fast reads for dashboard display

---

### **Migration Script**

Create: `storage/migrations/008_add_performance_metrics.py`

```python
"""
Migration 008: Add performance metrics tracking
"""

def upgrade(db_connection):
    """
    Add performance_metrics table and update campaigns table
    """
    cursor = db_connection.cursor()
    
    # Detect database type
    is_sqlite = 'sqlite' in str(type(db_connection))
    
    if is_sqlite:
        # SQLite version
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creative_id INTEGER NOT NULL,
                date DATE NOT NULL,
                hour INTEGER CHECK (hour >= 0 AND hour <= 23),
                impressions BIGINT DEFAULT 0,
                clicks BIGINT DEFAULT 0,
                spend DECIMAL(12,2) DEFAULT 0,
                cpm DECIMAL(8,4),
                cpc DECIMAL(8,4),
                geography VARCHAR(2),
                device_type VARCHAR(20),
                placement VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (creative_id) REFERENCES creatives(id) ON DELETE CASCADE,
                UNIQUE(creative_id, date, hour, geography, device_type)
            )
        """)
    else:
        # PostgreSQL version
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id SERIAL PRIMARY KEY,
                creative_id INTEGER NOT NULL REFERENCES creatives(id) ON DELETE CASCADE,
                date DATE NOT NULL,
                hour INTEGER CHECK (hour >= 0 AND hour <= 23),
                impressions BIGINT DEFAULT 0 CHECK (impressions >= 0),
                clicks BIGINT DEFAULT 0 CHECK (clicks >= 0),
                spend DECIMAL(12,2) DEFAULT 0 CHECK (spend >= 0),
                cpm DECIMAL(8,4),
                cpc DECIMAL(8,4),
                geography VARCHAR(2),
                device_type VARCHAR(20),
                placement VARCHAR(100),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(creative_id, date, hour, geography, device_type)
            )
        """)
    
    # Add check constraint for clicks <= impressions (PostgreSQL only)
    if not is_sqlite:
        cursor.execute("""
            ALTER TABLE performance_metrics 
            ADD CONSTRAINT chk_clicks_lte_impressions 
            CHECK (clicks <= impressions)
        """)
    
    # Create indexes (after table creation for performance)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_perf_creative_date ON performance_metrics(creative_id, date DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_perf_geo_date ON performance_metrics(geography, date DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_perf_spend ON performance_metrics(spend DESC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_perf_cpc ON performance_metrics(cpc ASC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_perf_date ON performance_metrics(date DESC)")
    
    # Update campaigns table
    alter_statements = [
        "ALTER TABLE campaigns ADD COLUMN total_spend_7d DECIMAL(12,2) DEFAULT 0",
        "ALTER TABLE campaigns ADD COLUMN total_spend_30d DECIMAL(12,2) DEFAULT 0",
        "ALTER TABLE campaigns ADD COLUMN total_spend_all_time DECIMAL(12,2) DEFAULT 0",
        "ALTER TABLE campaigns ADD COLUMN avg_cpc_7d DECIMAL(8,4)",
        "ALTER TABLE campaigns ADD COLUMN avg_cpm_7d DECIMAL(8,4)",
        "ALTER TABLE campaigns ADD COLUMN top_geography VARCHAR(2)",
        "ALTER TABLE campaigns ADD COLUMN top_device_type VARCHAR(20)",
        "ALTER TABLE campaigns ADD COLUMN last_performance_update TIMESTAMP"
    ]
    
    for stmt in alter_statements:
        try:
            cursor.execute(stmt)
        except Exception as e:
            # Column might already exist (idempotent migration)
            if "already exists" not in str(e).lower():
                raise
    
    db_connection.commit()
    print("✓ Migration 008: Performance metrics table created")

def downgrade(db_connection):
    """
    Rollback migration (for testing)
    """
    cursor = db_connection.cursor()
    cursor.execute("DROP TABLE IF EXISTS performance_metrics")
    
    # Remove columns from campaigns (careful - might lose data)
    # Note: SQLite doesn't support DROP COLUMN easily, so skip for SQLite
    is_sqlite = 'sqlite' in str(type(db_connection))
    if not is_sqlite:
        cursor.execute("ALTER TABLE campaigns DROP COLUMN IF EXISTS total_spend_7d")
        cursor.execute("ALTER TABLE campaigns DROP COLUMN IF EXISTS total_spend_30d")
        # ... etc
    
    db_connection.commit()
    print("✓ Migration 008 rolled back")
```

**Run migration:**
```bash
python -m storage.migrations.run
```

---

## 📥 Part 2: Data Import System

### **API Endpoint: CSV Import**

Create: `api/performance.py`

```python
from fastapi import APIRouter, UploadFile, File, HTTPException
from datetime import datetime, date
import csv
import io
from typing import List, Dict, Any
from pydantic import BaseModel, validator

router = APIRouter(prefix="/api/performance", tags=["performance"])

class PerformanceRecord(BaseModel):
    """Single performance record"""
    creative_id: int
    date: date
    hour: int | None = None
    impressions: int = 0
    clicks: int = 0
    spend: float = 0
    geography: str | None = None
    device_type: str | None = None
    placement: str | None = None
    
    @validator('clicks')
    def clicks_lte_impressions(cls, v, values):
        if 'impressions' in values and v > values['impressions']:
            raise ValueError(f"Clicks ({v}) cannot exceed impressions ({values['impressions']})")
        return v
    
    @validator('spend', 'impressions', 'clicks')
    def non_negative(cls, v):
        if v < 0:
            raise ValueError("Value must be non-negative")
        return v
    
    @validator('date')
    def date_not_future(cls, v):
        if v > date.today():
            raise ValueError("Date cannot be in the future")
        return v
    
    @validator('hour')
    def hour_valid(cls, v):
        if v is not None and (v < 0 or v > 23):
            raise ValueError("Hour must be between 0 and 23")
        return v

class ImportResult(BaseModel):
    """Result of import operation"""
    imported: int
    skipped: int
    errors: List[Dict[str, Any]]

@router.post("/import", response_model=ImportResult)
async def import_performance_data(
    file: UploadFile = File(...),
    batch_size: int = 1000
):
    """
    Import performance data from CSV file
    
    CSV Format:
    creative_id,date,impressions,clicks,spend,geography,device_type
    79783,2025-11-29,10000,250,125.50,BR,mobile
    """
    
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files supported")
    
    # Read CSV
    content = await file.read()
    csv_data = io.StringIO(content.decode('utf-8'))
    reader = csv.DictReader(csv_data)
    
    imported = 0
    skipped = 0
    errors = []
    batch = []
    
    for row_num, row in enumerate(reader, start=2):  # Start at 2 (after header)
        try:
            # Parse and validate
            record = PerformanceRecord(
                creative_id=int(row['creative_id']),
                date=datetime.strptime(row['date'], '%Y-%m-%d').date(),
                impressions=int(row.get('impressions', 0)),
                clicks=int(row.get('clicks', 0)),
                spend=float(row.get('spend', 0)),
                geography=row.get('geography', '').upper() or None,
                device_type=row.get('device_type', '').lower() or None,
                hour=int(row['hour']) if row.get('hour') else None,
                placement=row.get('placement') or None
            )
            
            # Calculate CPM and CPC
            cpm = (record.spend / record.impressions * 1000) if record.impressions > 0 else None
            cpc = (record.spend / record.clicks) if record.clicks > 0 else None
            
            batch.append({
                **record.dict(),
                'cpm': cpm,
                'cpc': cpc
            })
            
            # Batch insert
            if len(batch) >= batch_size:
                imported += insert_batch(batch)
                batch = []
                
        except ValueError as e:
            errors.append({
                'row': row_num,
                'error': str(e),
                'data': row
            })
            skipped += 1
        except Exception as e:
            errors.append({
                'row': row_num,
                'error': f"Unexpected error: {str(e)}",
                'data': row
            })
            skipped += 1
    
    # Insert remaining batch
    if batch:
        imported += insert_batch(batch)
    
    return ImportResult(
        imported=imported,
        skipped=skipped,
        errors=errors[:100]  # Limit to first 100 errors
    )

def insert_batch(records: List[Dict]) -> int:
    """
    Insert batch of performance records
    Returns: number of records inserted
    """
    from storage.sqlite_store import get_db_connection
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    inserted = 0
    
    for record in records:
        try:
            cursor.execute("""
                INSERT INTO performance_metrics (
                    creative_id, date, hour, impressions, clicks, spend,
                    cpm, cpc, geography, device_type, placement
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (creative_id, date, hour, geography, device_type)
                DO UPDATE SET
                    impressions = excluded.impressions,
                    clicks = excluded.clicks,
                    spend = excluded.spend,
                    cpm = excluded.cpm,
                    cpc = excluded.cpc,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                record['creative_id'], record['date'], record['hour'],
                record['impressions'], record['clicks'], record['spend'],
                record['cpm'], record['cpc'],
                record['geography'], record['device_type'], record['placement']
            ))
            inserted += 1
        except Exception as e:
            print(f"Error inserting record: {e}")
            # Continue with next record
    
    conn.commit()
    conn.close()
    
    return inserted

@router.get("/metrics/{creative_id}")
async def get_performance_metrics(
    creative_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    geography: str | None = None
):
    """
    Get performance metrics for a creative
    """
    from storage.sqlite_store import get_db_connection
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Build query
    query = "SELECT * FROM performance_metrics WHERE creative_id = ?"
    params = [creative_id]
    
    if start_date:
        query += " AND date >= ?"
        params.append(start_date)
    
    if end_date:
        query += " AND date <= ?"
        params.append(end_date)
    
    if geography:
        query += " AND geography = ?"
        params.append(geography.upper())
    
    query += " ORDER BY date DESC, hour DESC"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    # Convert to dict
    columns = [desc[0] for desc in cursor.description]
    results = [dict(zip(columns, row)) for row in rows]
    
    conn.close()
    
    return {
        'creative_id': creative_id,
        'records': len(results),
        'data': results
    }
```

---

### **Update Main API**

Update: `api/main.py`

```python
from api.performance import router as performance_router

app.include_router(performance_router)
```

---

## 📄 Part 3: Example CSV File

Create: `docs/performance_import_example.csv`

```csv
creative_id,date,impressions,clicks,spend,geography,device_type
79783,2025-11-29,10000,250,125.50,BR,mobile
79783,2025-11-29,5000,100,80.00,BR,desktop
79783,2025-11-29,2000,15,30.00,IE,mobile
79783,2025-11-28,12000,300,150.00,BR,mobile
144634,2025-11-29,50000,800,200.00,US,mobile
144634,2025-11-29,30000,450,135.00,US,desktop
144634,2025-11-29,5000,50,40.00,CA,mobile
144634,2025-11-28,48000,750,187.50,US,mobile
```

**Include README in docs:**

Create: `docs/PERFORMANCE_DATA_IMPORT.md`

```markdown
# Performance Data Import Guide

## CSV Format

Required columns:
- `creative_id` - Integer, must exist in creatives table
- `date` - Date in YYYY-MM-DD format
- `impressions` - Integer >= 0
- `clicks` - Integer >= 0 and <= impressions
- `spend` - Decimal >= 0 (in USD)

Optional columns:
- `geography` - ISO country code (BR, IE, US, etc.)
- `device_type` - mobile, desktop, tablet
- `hour` - 0-23 for hourly data
- `placement` - Site/app placement identifier

## Import via API

```bash
curl -X POST http://localhost:8000/api/performance/import \
  -F "file=@performance_data.csv"
```

## Import via UI

1. Go to Settings → Performance Data
2. Click "Import CSV"
3. Select your CSV file
4. Review import summary

## Data Sources

### From Google Authorized Buyers API
Limited performance data available via API (partial impressions).

### From Your Bidder
Export spend/click/impression data from your bidder's reporting system.

### From BigQuery (Enterprise)
Set up scheduled export from your data warehouse.

## Validation

The system validates:
- ✓ creative_id exists
- ✓ date not in future
- ✓ clicks <= impressions
- ✓ spend, clicks, impressions >= 0
- ✓ geography is 2-letter ISO code

Errors are reported in import summary.

## Duplicates

If you import the same data twice (same creative_id, date, hour, geo, device):
- Existing record is UPDATED
- New values replace old values
- No duplicate records created

## Performance

- Import in batches of 1000 rows
- Indexes created after initial load
- Large files (100k+ rows) may take 1-2 minutes

## Troubleshooting

**Error: "creative_id not found"**
- Ensure creative exists in database
- Run creative sync first

**Error: "clicks exceed impressions"**
- Check your data export
- Clicks should always be <= impressions

**Error: "date in future"**
- Check date format (YYYY-MM-DD)
- Dates cannot be in the future
```

---

## ✅ Testing Checklist

Before marking this complete, test:

1. **Migration**
   - [ ] Run migration on fresh database
   - [ ] Run migration on existing database (652 creatives)
   - [ ] Verify indexes created
   - [ ] Check campaigns table updated

2. **CSV Import**
   - [ ] Import example CSV (8 rows)
   - [ ] Import large CSV (10,000 rows)
   - [ ] Test duplicate detection (import same file twice)
   - [ ] Test validation (negative spend, clicks > impressions, future date)
   - [ ] Test missing columns (should use defaults)

3. **API Endpoints**
   - [ ] POST /api/performance/import with valid CSV
   - [ ] POST /api/performance/import with invalid CSV
   - [ ] GET /api/performance/metrics/{creative_id}
   - [ ] GET with date range filtering
   - [ ] GET with geography filtering

4. **Performance**
   - [ ] Import 100,000 rows (should take <2 minutes)
   - [ ] Query performance metrics for creative (should be <100ms)
   - [ ] Verify indexes are being used (EXPLAIN QUERY)

5. **Data Integrity**
   - [ ] Verify CPM calculated correctly (spend / impressions * 1000)
   - [ ] Verify CPC calculated correctly (spend / clicks)
   - [ ] Verify UNIQUE constraint prevents duplicates
   - [ ] Verify foreign key CASCADE deletes performance when creative deleted

---

## 📦 Deliverables

When complete, you should have:

1. ✅ Migration script: `storage/migrations/008_add_performance_metrics.py`
2. ✅ API endpoint: `api/performance.py`
3. ✅ Example CSV: `docs/performance_import_example.csv`
4. ✅ Documentation: `docs/PERFORMANCE_DATA_IMPORT.md`
5. ✅ Updated API docs: Performance endpoints in /docs
6. ✅ Working import: Can import CSV via API or curl

---

## 🎯 Success Criteria

**Phase 8.1 is complete when:**
- ✓ Database has performance_metrics table with proper indexes
- ✓ Can import CSV file with performance data
- ✓ Duplicate records are handled (UPDATE not INSERT)
- ✓ Validation catches bad data (negative values, future dates, etc.)
- ✓ API returns performance metrics for any creative_id
- ✓ All tests pass
- ✓ Documentation complete

**Next Phase:** 8.2 - Enhanced creatives page with "Sort by Spend"

---

## 💡 Notes

- Start with SQLite support (easier to test)
- Add PostgreSQL support after SQLite works
- Use batch inserts (1000 rows at a time) for performance
- Create indexes AFTER initial data load (much faster)
- Handle duplicates with UPSERT (INSERT ... ON CONFLICT UPDATE)
- Validate data thoroughly (bad data = bad insights)

**Current database location:** ~/.rtbcat/rtbcat.db

Let me know when migration and import are working, then we'll move to Phase 8.2 (UI enhancements).
