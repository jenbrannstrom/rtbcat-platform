# ChatGPT Codex CLI Prompt: Fix Backend CSV Column Validation

**Project:** RTB.cat Creative Intelligence Platform  
**Context:** Frontend correctly maps columns, but backend rejects the import  
**Goal:** Ensure column mapping is applied before backend validation

---

## 🎯 The Problem

**Frontend shows:**
```
Auto-detected columns:
#Creative ID → creative_id ✓
Day → date ✓
Impressions → impressions ✓
Clicks → clicks ✓
Spend (buyer currency) → spend ✓
Country → geography ✓
```

**But backend returns:**
```
CSV missing required columns: impressions, creative_id, clicks, date, spend
```

**The disconnect:** Frontend maps columns for display, but sends original column names to backend.

---

## 🔍 Where to Look

### 1. Frontend: How is data sent to backend?

```typescript
// dashboard/src/lib/api.ts (around line 266)
// or dashboard/src/app/import/page.tsx (around line 160)

// Is it sending the original CSV blob?
// Or the transformed/mapped data?
```

### 2. Backend: What validation is happening?

```python
# creative-intelligence/api/performance.py
# or creative-intelligence/storage/sqlite_store.py

# Backend probably has its own column check like:
required_columns = ['creative_id', 'date', 'impressions', 'clicks', 'spend']
if not all(col in data.columns for col in required_columns):
    raise HTTPException(400, "CSV missing required columns: ...")
```

---

## 📋 Part 1: Trace the Data Flow

```
User uploads CSV with columns: "#Creative ID", "Day", "Spend (buyer currency)"
                    ↓
Frontend csv-parser.ts: Detects and maps → "creative_id", "date", "spend"
                    ↓
Frontend shows preview with mapped names ✓
                    ↓
Frontend sends to backend... but WHAT does it send?
                    ↓
Option A: Original file blob → Backend sees "#Creative ID" → FAILS
Option B: Transformed JSON → Backend sees "creative_id" → Should work
```

---

## 📋 Part 2: The Fix

### Option A: Send Transformed Data (Recommended)

Frontend should send the **already-mapped data**, not the raw file:

```typescript
// dashboard/src/app/import/page.tsx

const handleImport = async () => {
  setImporting(true);
  try {
    // DON'T send: the original file
    // DO send: the parsed + mapped data
    
    const result = await importPerformanceData({
      rows: parsedData.rows,        // Already has mapped column names
      mappings: parsedData.mappings, // The column mappings used
      anomalies: validation.anomalies,
      csvType: csvType,
    });
    
    // ...
  } catch (error) {
    // ...
  }
};
```

```typescript
// dashboard/src/lib/api.ts

export async function importPerformanceData(data: {
  rows: ParsedRow[];
  mappings: Record<string, string>;
  anomalies: Anomaly[];
  csvType: 'performance' | 'video';
}): Promise<ImportResponse> {
  
  const response = await fetch('/api/performance/import', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      rows: data.rows,  // Pre-mapped data with correct column names
      mappings: data.mappings,
      anomalies: data.anomalies,
      csv_type: data.csvType,
    }),
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || error.error || "Import failed");
  }
  
  return response.json();
}
```

### Option B: Backend Applies Mapping

If frontend sends raw file, backend should apply the same column mapping:

```python
# creative-intelligence/api/performance.py

from fastapi import APIRouter, UploadFile, File

router = APIRouter()

# Column name aliases (same logic as frontend)
COLUMN_ALIASES = {
    'creative_id': ['creative_id', 'creativeid', '#creative id', '#creative_id', 'creative id'],
    'date': ['date', 'day', '#day', 'metric_date'],
    'impressions': ['impressions', 'imps'],
    'clicks': ['clicks'],
    'spend': ['spend', 'spend (buyer currency)', 'spend_buyer_currency', 'cost'],
    'geography': ['geography', 'country', 'geo', 'region'],
}

def normalize_column_name(col: str) -> str:
    """Convert any column name variant to standard name."""
    col_lower = col.lower().strip().replace(' ', '_').replace('(', '').replace(')', '')
    
    for standard_name, aliases in COLUMN_ALIASES.items():
        if col_lower in [a.lower() for a in aliases]:
            return standard_name
    
    # Remove # prefix
    if col_lower.startswith('#'):
        return normalize_column_name(col_lower[1:])
    
    return col_lower  # Return as-is if no match

@router.post("/api/performance/import")
async def import_performance_csv(file: UploadFile = File(...)):
    """Import CSV with flexible column name matching."""
    
    import pandas as pd
    import io
    
    content = await file.read()
    df = pd.read_csv(io.BytesIO(content))
    
    # Normalize all column names
    df.columns = [normalize_column_name(col) for col in df.columns]
    
    # Now check for required columns (using normalized names)
    required = ['creative_id', 'date', 'impressions', 'clicks', 'spend']
    missing = [col for col in required if col not in df.columns]
    
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"CSV missing required columns: {', '.join(missing)}. Found: {', '.join(df.columns.tolist())}"
        )
    
    # Continue with import...
```

---

## 📋 Part 3: Debug Steps

### Step 1: Check what frontend actually sends

Add logging to see the request payload:

```typescript
// dashboard/src/lib/api.ts

export async function importPerformanceData(data: any): Promise<ImportResponse> {
  console.log('=== IMPORT REQUEST ===');
  console.log('Data being sent:', JSON.stringify(data).slice(0, 500));
  
  const response = await fetch('/api/performance/import', {
    // ...
  });
  
  console.log('Response status:', response.status);
  // ...
}
```

### Step 2: Check backend receives

```python
# creative-intelligence/api/performance.py

@router.post("/api/performance/import")
async def import_performance_csv(file: UploadFile = File(...)):
    import logging
    logging.info(f"=== IMPORT REQUEST ===")
    logging.info(f"Filename: {file.filename}")
    
    content = await file.read()
    logging.info(f"Content size: {len(content)} bytes")
    logging.info(f"First 200 chars: {content[:200]}")
    
    # ... rest of handler
```

### Step 3: Check the actual request in browser

Open DevTools → Network tab → Click Import → Look at the request:
- Is it sending `FormData` with file?
- Or JSON with parsed data?
- What headers?

---

## 📋 Part 4: Likely Root Cause

Looking at the error flow:

```typescript
// src/lib/api.ts line 266
throw new Error(error.detail || error.error || "Import failed");
```

The backend returned:
```json
{"detail": "CSV missing required columns: impressions, creative_id, clicks, date, spend"}
```

This means the **backend is parsing the raw CSV** and seeing the original column names like `#Creative ID` instead of `creative_id`.

---

## 📋 Part 5: The Fix (Most Likely)

Find where the frontend sends the file and ensure it sends **mapped data**:

```typescript
// FIND THIS (probably in api.ts or import/page.tsx):
const formData = new FormData();
formData.append('file', file);  // ← Sending raw file!

// CHANGE TO:
const response = await fetch('/api/performance/import', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    rows: parsedData.rows,  // Already mapped!
  }),
});
```

**OR** update the backend to normalize columns (see Option B above).

---

## 📋 Part 6: Files to Check/Modify

```
dashboard/src/app/import/page.tsx     # handleImport function
dashboard/src/lib/api.ts              # importPerformanceData function
creative-intelligence/api/performance.py  # Backend import endpoint
creative-intelligence/api/main.py     # Route registration
```

---

## 📋 Part 7: Quick Test

After fix, this should work:

```bash
# Check the backend endpoint directly with correct column names
curl -X POST http://localhost:8000/api/performance/import \
  -H "Content-Type: application/json" \
  -d '{
    "rows": [
      {"creative_id": "100518", "date": "2025-11-27", "impressions": 3158, "clicks": 22, "spend": 1.57, "geography": "INDIA"}
    ]
  }'
```

---

## 🚀 Summary

| Component | Issue | Fix |
|-----------|-------|-----|
| Frontend parsing | Works correctly ✓ | - |
| Frontend preview | Shows mapped names ✓ | - |
| API call | Sends raw file? | Send mapped JSON |
| Backend validation | Expects exact names | Add column normalization |

The frontend did all the work to map columns, but then threw it away and sent the raw file. Either send the mapped data, or make the backend do the same mapping.

---

**Location:**
```
Project: /home/jen/Documents/rtbcat-platform/
```

**After code changes:**
```bash
sudo systemctl restart rtbcat-api
```
