# Claude CLI Prompt: Fix Backend CSV Validation Bug

## The Problem

The CSV import flow is broken:

1. **Frontend** correctly auto-detects columns: `#Creative ID` → `creative_id` ✅
2. **Frontend** shows a nice preview with mapped columns ✅
3. **Frontend** sends the raw file to backend... ❌
4. **Backend** sees `#Creative ID` header, doesn't know the mapping, rejects: "Missing required column: creative_id" ❌

**The mapping lives only in the frontend and never reaches the backend.**

---

## Your Task

Fix this so that CSV imports actually work. There are two valid approaches:

### Option A: Send mapping WITH the file (Recommended)

Modify the frontend to send both the file AND the column mapping to the backend. The backend then uses the mapping to transform the data.

**Frontend changes (`dashboard/src/app/import/page.tsx` or `dashboard/src/lib/api.ts`):**
- When calling the import endpoint, include the `columnMapping` object
- Example payload: `{ file: <CSV>, mapping: { "#Creative ID": "creative_id", "Impressions": "impressions", ... } }`

**Backend changes (`creative-intelligence/api/performance.py`):**
- Accept the mapping in the request
- Apply the mapping when parsing CSV rows
- Transform `row["#Creative ID"]` → `row["creative_id"]` before validation

### Option B: Duplicate mapping logic in backend

Make the backend also do column auto-detection (same logic as frontend).

**Downside:** Duplicate code, can drift out of sync.

---

## Key Files to Examine

```
/home/jen/Documents/rtbcat-platform/
├── dashboard/
│   ├── src/app/import/page.tsx          # Upload UI, has columnMapping state
│   ├── src/lib/csv-parser.ts            # Parses CSV
│   ├── src/lib/csv-validator.ts         # Validates, detects columns
│   └── src/lib/api.ts                   # API client, sends to backend
│
└── creative-intelligence/
    ├── api/performance.py               # POST /api/performance/import endpoint
    └── storage/sqlite_store.py          # save_performance_metrics()
```

---

## Step-by-Step Instructions

### 1. Examine current frontend flow

```bash
# Look at how the import page handles the mapping
cat /home/jen/Documents/rtbcat-platform/dashboard/src/app/import/page.tsx

# Look at how API calls are made
cat /home/jen/Documents/rtbcat-platform/dashboard/src/lib/api.ts
```

Find:
- Where `columnMapping` is stored
- How the file upload API call is made
- What data is currently sent to backend

### 2. Examine current backend endpoint

```bash
cat /home/jen/Documents/rtbcat-platform/creative-intelligence/api/performance.py
```

Find:
- The `POST /api/performance/import` endpoint
- What it expects to receive
- Where it validates columns

### 3. Implement the fix

**Frontend (`api.ts` or wherever the upload function lives):**

```typescript
// BEFORE (sends only file):
const formData = new FormData();
formData.append('file', file);

// AFTER (sends file + mapping):
const formData = new FormData();
formData.append('file', file);
formData.append('column_mapping', JSON.stringify(columnMapping));
```

**Backend (`performance.py`):**

```python
from fastapi import Form
import json

@router.post("/api/performance/import")
async def import_csv(
    file: UploadFile = File(...),
    column_mapping: str = Form(None)  # JSON string
):
    # Parse mapping
    mapping = json.loads(column_mapping) if column_mapping else {}
    
    # Read CSV
    content = await file.read()
    reader = csv.DictReader(io.StringIO(content.decode('utf-8')))
    
    # Apply mapping to each row
    for raw_row in reader:
        row = {}
        for original_col, value in raw_row.items():
            # Use mapped name if exists, otherwise use original
            mapped_name = mapping.get(original_col, original_col)
            row[mapped_name] = value
        
        # Now row has standardized column names
        # Proceed with validation and import...
```

### 4. Test the fix

```bash
# Restart backend after changes
sudo systemctl restart rtbcat-api

# Check logs for errors
sudo journalctl -u rtbcat-api -f
```

Then in browser:
1. Go to http://localhost:3000/import
2. Upload a real Google CSV
3. Check that preview still works
4. Click Import
5. Should succeed now!

### 5. Verify data imported

```bash
sqlite3 ~/.rtbcat/rtbcat.db "SELECT COUNT(*) FROM performance_metrics;"
# Should be > 0

sqlite3 ~/.rtbcat/rtbcat.db "SELECT creative_id, metric_date, impressions, clicks FROM performance_metrics LIMIT 5;"
```

---

## Database Schema Reference

The backend needs to save data matching this schema:

```sql
performance_metrics:
  - creative_id TEXT (required) - matches creatives.id
  - metric_date DATE (required)
  - impressions INTEGER
  - clicks INTEGER  
  - spend_micros INTEGER (spend × 1,000,000)
  - geography TEXT (use "UNKNOWN" if NULL)
  - device_type TEXT (use "UNKNOWN" if NULL)
  - placement TEXT (use "UNKNOWN" if NULL)
```

---

## Google CSV Column Mapping Reference

Typical Google Authorized Buyers CSV columns:

| Google Header | Maps To |
|--------------|---------|
| `#Creative ID` or `Creative ID` | `creative_id` |
| `Date` | `metric_date` |
| `Impressions` | `impressions` |
| `Clicks` | `clicks` |
| `Spend` or `Cost` | `spend_micros` (multiply by 1,000,000) |
| `Country` or `Geography` | `geography` |
| `Device Type` | `device_type` |
| `Placement` or `App` | `placement` |

---

## Success Criteria

- [ ] CSV upload completes without "missing column" errors
- [ ] Data appears in `performance_metrics` table
- [ ] Column mapping from frontend is respected
- [ ] Spend is correctly converted to micros (× 1,000,000)
- [ ] NULL values become "UNKNOWN" (UPSERT logic preserved)

---

## After Success

Tell Jen:
```
"Fixed! Please restart the backend: sudo systemctl restart rtbcat-api"
```

Then update `RTBcat_Handover_v8.md`:
- Change "Backend validation bug" from 🐛 to ✅
- Note date of fix

---

## DO NOT

- ❌ Kill or restart processes directly (tell user to do it)
- ❌ Delete any data without confirmation
- ❌ Change the database schema
- ❌ Break the existing frontend preview functionality

---

**Priority:** HIGH - This is blocking all imports
**Estimated time:** 30-60 minutes
**Risk:** Low (isolated change to import flow)
