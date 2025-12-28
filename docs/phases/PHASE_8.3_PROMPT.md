# Phase 8.3: Performance Data Import UI

**Project:** RTB.cat Creative Intelligence Platform  
**Task:** Build CSV upload interface for performance data  
**Developer:** Claude in VSCode (Frontend) + Claude CLI (Backend validation)  
**Prerequisites:** Phase 8.1 (backend endpoints) and Phase 8.2 (UI ready for data) complete  
**Location:** `/home/jen/Documents/rtbcat-platform/dashboard/`

---

## 🎯 Objective

Create a user-friendly interface for importing performance data via CSV upload, so the "Sort by Spend" feature in Phase 8.2 can display actual data.

**Current State:** UI exists but shows "No data" - no performance metrics imported  
**Target State:** User can upload CSV file and see spend/CPC/CPM data populate on creative cards

---

## 📋 Requirements

### 1. Import Page/Modal

**Location:** New page at `/import` or modal accessible from creatives page

**Features:**
- File upload dropzone (drag & drop + click to browse)
- CSV format instructions/example
- Upload progress indicator
- Success/error feedback
- Preview of imported data (first 10 rows)
- Data validation before import

**Layout:**
```
┌─────────────────────────────────────────────────┐
│  Import Performance Data                        │
├─────────────────────────────────────────────────┤
│                                                 │
│  ┌───────────────────────────────────────┐    │
│  │   📁 Drag & drop CSV file here        │    │
│  │        or click to browse              │    │
│  └───────────────────────────────────────┘    │
│                                                 │
│  Expected CSV format:                          │
│  creative_id, date, impressions, clicks,       │
│  spend, geography                              │
│                                                 │
│  [Download Example CSV]                        │
│                                                 │
│  ┌───────────────────────────────────────┐    │
│  │ Preview (first 10 rows)               │    │
│  │ creative_id | date       | spend     │    │
│  │ 79783      | 2025-11-29 | 1234.56   │    │
│  │ 79784      | 2025-11-29 | 567.89    │    │
│  └───────────────────────────────────────┘    │
│                                                 │
│  [Cancel]  [Import Data] →                     │
└─────────────────────────────────────────────────┘
```

---

### 2. CSV Format

**Required columns:**
- `creative_id` (integer) - matches creatives.id
- `date` (YYYY-MM-DD) - performance date
- `impressions` (integer) - ad impressions
- `clicks` (integer) - ad clicks
- `spend` (decimal) - money spent in dollars

**Optional columns:**
- `geography` (2-letter country code) - e.g., "US", "BR"

**Example CSV:**
```csv
creative_id,date,impressions,clicks,spend,geography
79783,2025-11-29,1000,50,25.50,US
79783,2025-11-28,950,45,23.75,US
79784,2025-11-29,500,10,5.00,BR
79784,2025-11-28,480,12,6.00,BR
```

---

### 3. Client-Side Validation

**Before sending to backend, validate:**

1. **File type:** Only .csv files
2. **File size:** Max 10MB (prevents browser crashes)
3. **Required columns:** creative_id, date, impressions, clicks, spend
4. **Data types:**
   - creative_id: positive integer
   - date: valid YYYY-MM-DD format
   - impressions: non-negative integer
   - clicks: non-negative integer
   - spend: non-negative decimal
   - geography: 2-letter code (if present)

5. **Business rules:**
   - clicks ≤ impressions (can't have more clicks than impressions)
   - spend ≥ 0
   - date not in future
   - No negative values

**Validation feedback:**
```
❌ Row 5: Invalid date format (expected YYYY-MM-DD)
❌ Row 12: Clicks (150) exceeds impressions (100)
❌ Row 23: Negative spend value (-5.00)
✅ 97 rows valid, ready to import
```

---

### 4. Upload Flow

**Step 1: File Selection**
- User drags CSV file or clicks to browse
- File name displays
- Show file size

**Step 2: Parsing & Validation**
- Parse CSV on client (using Papa Parse or similar)
- Run validation checks
- Show validation results
- If errors: highlight problem rows, block import
- If valid: show preview, enable import button

**Step 3: Upload**
- POST to backend: `/api/performance/import`
- Show progress bar (if backend supports progress)
- Disable UI during upload

**Step 4: Results**
- Success: "✅ Imported 1,234 rows (45 duplicates skipped)"
- Partial success: "⚠️ Imported 1,000 rows, 234 errors"
- Error: "❌ Import failed: [reason]"
- Link to view imported data: "View creatives →"

---

### 5. Error Handling

**Client-side errors:**
- Invalid file type → "Please upload a .csv file"
- File too large → "File size exceeds 10MB limit"
- Missing required columns → "CSV must include: creative_id, date, impressions, clicks, spend"
- Validation errors → Show detailed error list with row numbers

**Server-side errors:**
- Network timeout → "Upload failed. Please try again."
- 400 Bad Request → Show backend validation errors
- 500 Server Error → "Server error. Contact support if this persists."
- 413 Payload Too Large → "File too large for server (max 50MB)"

**User-friendly messages:**
```
Instead of: "FOREIGN KEY constraint failed"
Show: "Creative ID 99999 doesn't exist in the system"

Instead of: "NULL constraint violation"
Show: "Row 45: Missing required field 'spend'"
```

---

### 6. Loading States

**Three loading states:**

1. **Parsing CSV**
   ```
   📄 Parsing CSV file...
   [Progress bar]
   ```

2. **Validating Data**
   ```
   ✓ Validating 1,234 rows...
   [Spinner]
   ```

3. **Uploading to Server**
   ```
   ☁️ Importing data...
   [Progress: 45%]
   ```

---

### 7. Success State

**After successful import:**
```
┌─────────────────────────────────────────────────┐
│  ✅ Import Complete!                            │
├─────────────────────────────────────────────────┤
│                                                 │
│  📊 Successfully imported 1,234 rows            │
│  🔄 Skipped 45 duplicates                       │
│  ⏱️  Date range: 2025-11-01 to 2025-11-30       │
│  💰 Total spend: $45,678.90                     │
│                                                 │
│  [View Creatives] →                             │
│  [Import More Data]                             │
└─────────────────────────────────────────────────┘
```

**Redirect to creatives page with:**
- Sort set to "Last 7 days"
- Performance data visible on cards
- Success toast: "Performance data imported successfully"

---

### 8. Example CSV Download

**Provide downloadable example CSV:**

**Button:** "Download Example CSV"

**File content:**
```csv
creative_id,date,impressions,clicks,spend,geography
79783,2025-11-29,1000,50,25.50,US
79783,2025-11-28,950,45,23.75,US
79784,2025-11-29,500,10,5.00,BR
79784,2025-11-28,480,12,6.00,BR
79785,2025-11-29,2000,100,50.00,GB
```

**Implementation:**
```typescript
const downloadExampleCSV = () => {
  const csv = `creative_id,date,impressions,clicks,spend,geography
79783,2025-11-29,1000,50,25.50,US
79783,2025-11-28,950,45,23.75,US
79784,2025-11-29,500,10,5.00,BR`;
  
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'performance_data_example.csv';
  a.click();
};
```

---

## 🛠️ Technical Implementation

### Frontend Files to Create/Update

**New files:**
```
dashboard/
├── app/
│   └── import/
│       └── page.tsx              # NEW: Import page
├── components/
│   ├── ImportDropzone.tsx        # NEW: File upload component
│   ├── ImportPreview.tsx         # NEW: Data preview table
│   └── ImportProgress.tsx        # NEW: Upload progress indicator
└── lib/
    ├── csv-validator.ts          # NEW: CSV validation logic
    └── csv-parser.ts             # NEW: CSV parsing utilities
```

**Updated files:**
```
dashboard/
├── app/
│   └── creatives/
│       └── page.tsx              # Add "Import Data" button
└── lib/
    └── api.ts                    # Add importPerformanceData() function
```

---

### Dependencies

**Install CSV parsing library:**
```bash
npm install papaparse
npm install --save-dev @types/papaparse
```

**Alternative:** Use built-in browser File API + manual CSV parsing

---

### API Integration

**Endpoint:** `POST /api/performance/import`

**Request:**
```typescript
// Multipart form data
const formData = new FormData();
formData.append('file', csvFile);

const response = await fetch('/api/performance/import', {
  method: 'POST',
  body: formData
});
```

**Response (Success - 200):**
```json
{
  "success": true,
  "imported": 1234,
  "duplicates": 45,
  "errors": 0,
  "date_range": {
    "start": "2025-11-01",
    "end": "2025-11-30"
  },
  "total_spend": 45678.90
}
```

**Response (Partial Success - 207):**
```json
{
  "success": false,
  "imported": 1000,
  "errors": 234,
  "error_details": [
    {
      "row": 5,
      "error": "Invalid date format",
      "value": "2025-13-01"
    },
    {
      "row": 12,
      "error": "Clicks exceed impressions",
      "clicks": 150,
      "impressions": 100
    }
  ]
}
```

**Response (Error - 400):**
```json
{
  "success": false,
  "error": "Missing required column: creative_id"
}
```

---

### CSV Validation Logic

**`lib/csv-validator.ts`:**

```typescript
interface ValidationError {
  row: number;
  field: string;
  error: string;
  value: any;
}

interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  rowCount: number;
}

export function validatePerformanceCSV(data: any[]): ValidationResult {
  const errors: ValidationError[] = [];
  
  // Check required columns
  const requiredColumns = ['creative_id', 'date', 'impressions', 'clicks', 'spend'];
  const columns = Object.keys(data[0] || {});
  
  for (const col of requiredColumns) {
    if (!columns.includes(col)) {
      errors.push({
        row: 0,
        field: col,
        error: `Missing required column: ${col}`,
        value: null
      });
    }
  }
  
  if (errors.length > 0) {
    return { valid: false, errors, rowCount: 0 };
  }
  
  // Validate each row
  data.forEach((row, index) => {
    const rowNum = index + 2; // +2 for header and 0-based index
    
    // creative_id: positive integer
    if (!Number.isInteger(Number(row.creative_id)) || Number(row.creative_id) <= 0) {
      errors.push({
        row: rowNum,
        field: 'creative_id',
        error: 'Must be a positive integer',
        value: row.creative_id
      });
    }
    
    // date: valid YYYY-MM-DD
    if (!/^\d{4}-\d{2}-\d{2}$/.test(row.date)) {
      errors.push({
        row: rowNum,
        field: 'date',
        error: 'Invalid date format (expected YYYY-MM-DD)',
        value: row.date
      });
    }
    
    // date: not in future
    const date = new Date(row.date);
    if (date > new Date()) {
      errors.push({
        row: rowNum,
        field: 'date',
        error: 'Date cannot be in the future',
        value: row.date
      });
    }
    
    // impressions: non-negative integer
    if (!Number.isInteger(Number(row.impressions)) || Number(row.impressions) < 0) {
      errors.push({
        row: rowNum,
        field: 'impressions',
        error: 'Must be a non-negative integer',
        value: row.impressions
      });
    }
    
    // clicks: non-negative integer
    if (!Number.isInteger(Number(row.clicks)) || Number(row.clicks) < 0) {
      errors.push({
        row: rowNum,
        field: 'clicks',
        error: 'Must be a non-negative integer',
        value: row.clicks
      });
    }
    
    // clicks <= impressions
    if (Number(row.clicks) > Number(row.impressions)) {
      errors.push({
        row: rowNum,
        field: 'clicks',
        error: 'Clicks cannot exceed impressions',
        value: `${row.clicks} clicks > ${row.impressions} impressions`
      });
    }
    
    // spend: non-negative decimal
    if (isNaN(Number(row.spend)) || Number(row.spend) < 0) {
      errors.push({
        row: rowNum,
        field: 'spend',
        error: 'Must be a non-negative number',
        value: row.spend
      });
    }
    
    // geography: 2-letter code (if present)
    if (row.geography && !/^[A-Z]{2}$/.test(row.geography)) {
      errors.push({
        row: rowNum,
        field: 'geography',
        error: 'Must be a 2-letter country code (e.g., US, BR)',
        value: row.geography
      });
    }
  });
  
  return {
    valid: errors.length === 0,
    errors,
    rowCount: data.length
  };
}
```

---

## 🎨 UI/UX Guidelines

### Dropzone Design

**Idle state:**
```
┌─────────────────────────────────────┐
│    📁                               │
│    Drag & drop CSV file here        │
│    or click to browse               │
│                                     │
│    Max file size: 10MB              │
└─────────────────────────────────────┘
```

**Drag over:**
```
┌─────────────────────────────────────┐
│    ↓                                │
│    Drop file to upload              │
│                                     │
└─────────────────────────────────────┘
(Blue border, subtle animation)
```

**File selected:**
```
┌─────────────────────────────────────┐
│    ✓ performance_data.csv           │
│    Size: 245 KB                     │
│    [Remove] [Preview]               │
└─────────────────────────────────────┘
```

### Color Scheme

**Validation states:**
- Valid: Green (#10B981)
- Warning: Yellow (#F59E0B)
- Error: Red (#EF4444)
- Info: Blue (#3B82F6)

**Progress:**
- Background: Light gray (#E5E7EB)
- Progress bar: Blue (#3B82F6)
- Success: Green (#10B981)

---

## ✅ Testing Checklist

### Functional Tests

- [ ] Can upload valid CSV file
- [ ] Can drag & drop CSV file
- [ ] Example CSV downloads correctly
- [ ] Validation catches all error types
- [ ] Import succeeds with valid data
- [ ] Duplicate detection works
- [ ] Error messages are clear
- [ ] Can import multiple files sequentially
- [ ] Progress indicator shows during upload
- [ ] Success message includes import stats

### Edge Cases

- [ ] Empty CSV file → Error
- [ ] CSV with only headers → Error
- [ ] CSV with 100,000 rows → Works (or shows file too large)
- [ ] CSV with invalid UTF-8 → Handles gracefully
- [ ] CSV with extra columns → Ignores them
- [ ] CSV with missing optional geography → Works
- [ ] Network error during upload → Retry option
- [ ] Browser refresh during upload → Graceful handling

### Validation Tests

- [ ] Catches negative spend
- [ ] Catches clicks > impressions
- [ ] Catches invalid date formats
- [ ] Catches future dates
- [ ] Catches non-existent creative IDs
- [ ] Catches missing required fields
- [ ] Allows optional fields to be missing

### UI/UX Tests

- [ ] Dropzone works on mobile
- [ ] Validation errors are readable
- [ ] Progress bar is smooth
- [ ] Success redirect works
- [ ] Can go back and import more data
- [ ] Works in Chrome, Firefox, Safari

---

## 🚨 Common Pitfalls to Avoid

1. **Don't block on large files**
   - Parse in chunks or use Web Workers
   - Show progress during parsing

2. **Don't send raw CSV to backend**
   - Validate on client first
   - Send JSON or FormData

3. **Don't ignore duplicate data**
   - Backend should handle UPSERT
   - Show user how many duplicates were skipped

4. **Don't forget mobile users**
   - File upload works on mobile
   - Validation errors are readable on small screens

5. **Don't show technical errors**
   - Translate backend errors to user-friendly messages
   - Provide actionable next steps

---

## 🎯 Success Criteria

**Phase 8.3 is complete when:**

1. ✅ User can upload CSV file via drag-drop or browse
2. ✅ Client-side validation catches all error types
3. ✅ Valid data imports successfully
4. ✅ Import progress is visible
5. ✅ Success message shows import statistics
6. ✅ After import, creatives page shows performance data
7. ✅ Error handling is user-friendly
8. ✅ Example CSV downloads correctly
9. ✅ Works on mobile and desktop
10. ✅ No console errors

---

## 📦 Deliverables

1. New import page at `/import` or modal component
2. CSV validation logic
3. Upload progress UI
4. Success/error states
5. Integration with Phase 8.2 creatives page
6. Example CSV download
7. Updated navigation (if needed)

---

## 🔄 Next Steps

**After Phase 8.3:**
- Phase 9: AI campaign clustering (group creatives by similarity)
- Phase 10: Opportunity detection (find profit pockets)
- Phase 11: Geographic intelligence (cross-campaign patterns)

---

## 📞 Support

**Backend API:** Should already have POST /api/performance/import endpoint (Phase 8.1)  
**API Docs:** http://localhost:8000/docs  

**Questions about:**
- Backend endpoint not working? → Check Phase 8.1 documentation
- CSV format unclear? → See example CSV section above
- Validation logic? → See csv-validator.ts example above

---

**Good luck! This is the final piece to make Phase 8.2's "Sort by Spend" feature come alive with real data! 🚀**
