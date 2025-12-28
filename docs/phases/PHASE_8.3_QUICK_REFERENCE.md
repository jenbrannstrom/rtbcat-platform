# Phase 8.3: Quick Reference

**CSV Import UI - Troubleshooting & Tips**

---

## 🎯 Quick Goals

1. Upload CSV via drag-drop or browse
2. Validate data client-side
3. Preview before import
4. Show progress during upload
5. Display success/error states
6. Redirect to creatives with data visible

---

## 📋 Development Checklist

**Setup (5 min):**
- [ ] Install papaparse: `npm install papaparse @types/papaparse`
- [ ] Create types file: `lib/types/import.ts`
- [ ] Create import page: `app/import/page.tsx`

**Components (60 min):**
- [ ] ImportDropzone.tsx - file upload
- [ ] ImportPreview.tsx - data table
- [ ] ValidationErrors.tsx - error display
- [ ] ImportProgress.tsx - upload progress

**Logic (45 min):**
- [ ] csv-parser.ts - parse CSV with papaparse
- [ ] csv-validator.ts - validate data
- [ ] Update api.ts - add import function

**Integration (30 min):**
- [ ] Add "Import Data" button to creatives page
- [ ] Test full flow
- [ ] Verify data appears on creative cards

---

## 🚨 Common Issues

### Issue: "papaparse not found"
```bash
npm install papaparse
npm install --save-dev @types/papaparse
```

### Issue: CSV parsing fails
**Check:**
- File is valid CSV (not Excel)
- Has header row
- Uses commas (not semicolons)
- Encoding is UTF-8

**Debug:**
```typescript
Papa.parse(file, {
  header: true,
  complete: (results) => {
    console.log('Parsed:', results.data);
    console.log('Errors:', results.errors);
  }
});
```

### Issue: Validation errors not showing
**Check:**
- ValidationErrors component receiving errors prop
- Errors array is not empty
- Component is actually rendering (check React DevTools)

### Issue: Upload progress stuck at 0%
**Cause:** Progress callback not implemented

**Fix:**
```typescript
// Backend needs to support progress events
// OR just set to 100% on completion
onProgress?.(100);
```

### Issue: File upload fails with CORS error
**Check:**
- Backend allows multipart/form-data
- CORS headers set correctly
- API endpoint exists: POST /api/performance/import

**Test backend:**
```bash
curl -X POST http://localhost:8000/api/performance/import \
  -F "file=@test.csv"
```

### Issue: "Maximum file size exceeded"
**Client-side limit:** 10MB (change in ImportDropzone maxSizeMB prop)
**Server-side limit:** Check backend configuration

---

## 🧪 Testing Scenarios

### Scenario 1: Valid CSV
```csv
creative_id,date,impressions,clicks,spend,geography
79783,2025-11-29,1000,50,25.50,US
```
**Expected:** Validates, imports successfully

### Scenario 2: Missing required column
```csv
creative_id,date,impressions,clicks
79783,2025-11-29,1000,50
```
**Expected:** Validation error: "Missing required column: spend"

### Scenario 3: Invalid data type
```csv
creative_id,date,impressions,clicks,spend
abc,2025-11-29,1000,50,25.50
```
**Expected:** Validation error: "Row 2: creative_id must be a positive integer"

### Scenario 4: Clicks > Impressions
```csv
creative_id,date,impressions,clicks,spend
79783,2025-11-29,100,150,25.50
```
**Expected:** Validation error: "Row 2: Clicks cannot exceed impressions"

### Scenario 5: Future date
```csv
creative_id,date,impressions,clicks,spend
79783,2099-12-31,1000,50,25.50
```
**Expected:** Validation error: "Row 2: Date cannot be in the future"

### Scenario 6: Large file (1000+ rows)
**Expected:** 
- Parses successfully
- Shows "first 10 rows" in preview
- Imports all rows
- Shows total in success message

---

## 💡 Pro Tips

### 1. File Size Limits
```typescript
// Client-side (prevents browser crash)
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

// Server might have different limit
// Check with backend team
```

### 2. Validation Performance
```typescript
// For large files, validate in chunks
const CHUNK_SIZE = 1000;
for (let i = 0; i < data.length; i += CHUNK_SIZE) {
  const chunk = data.slice(i, i + CHUNK_SIZE);
  validateChunk(chunk);
}
```

### 3. Better UX
```typescript
// Show how many rows will be imported
Import {validRowCount} of {totalRows} rows

// Show estimated time for large files
Estimated time: ~30 seconds

// Auto-redirect with countdown
Redirecting in 3 seconds... [Cancel]
```

### 4. Error Recovery
```typescript
// Allow fixing errors and re-validating
[Fix Errors] button → opens modal with editable table

// Or download error report
[Download Error Report] → CSV with error rows
```

---

## 📊 Validation Rules Quick Reference

| Field | Type | Rules |
|-------|------|-------|
| creative_id | integer | > 0 |
| date | string | YYYY-MM-DD, not future |
| impressions | integer | ≥ 0 |
| clicks | integer | ≥ 0, ≤ impressions |
| spend | decimal | ≥ 0 |
| geography | string | 2 letters (optional) |

---

## 🎨 UI States Checklist

- [ ] **Idle:** Dropzone ready for upload
- [ ] **Drag over:** Visual feedback when dragging
- [ ] **File selected:** Show file name & size
- [ ] **Parsing:** "Parsing CSV..." loader
- [ ] **Validation errors:** Red border, error list
- [ ] **Valid preview:** Green checkmark, data table
- [ ] **Importing:** Progress bar with percentage
- [ ] **Success:** Green success message with stats
- [ ] **Error:** Red error message with details
- [ ] **Redirecting:** Countdown or spinner

---

## 🔧 Debugging Commands

### Check file upload
```bash
# Terminal 1: Watch backend logs
sudo journalctl -u rtbcat-api -f

# Terminal 2: Test upload
curl -X POST http://localhost:8000/api/performance/import \
  -F "file=@test.csv"
```

### Check validation logic
```typescript
// In browser console on import page
const testData = [
  { creative_id: 79783, date: '2025-11-29', impressions: 1000, clicks: 50, spend: 25.50 }
];
const result = validatePerformanceCSV(testData);
console.log(result);
```

### Check CSV parsing
```typescript
// In browser console
import Papa from 'papaparse';

const csv = `creative_id,date,impressions,clicks,spend
79783,2025-11-29,1000,50,25.50`;

Papa.parse(csv, {
  header: true,
  complete: (r) => console.log(r.data)
});
```

---

## 🎯 Success Criteria

**Phase 8.3 is complete when:**

✅ Can upload CSV via drag-drop  
✅ Can upload CSV via file browser  
✅ Example CSV downloads correctly  
✅ Client-side validation catches errors  
✅ Preview shows first 10 rows  
✅ Import progress is visible  
✅ Success shows import statistics  
✅ After import, creatives show performance data  
✅ Error messages are user-friendly  
✅ Works on mobile  

---

## 📱 Mobile Testing

**Test on:**
- [ ] Mobile Chrome (Android)
- [ ] Mobile Safari (iOS)
- [ ] Tablet

**Check:**
- [ ] File picker opens on mobile
- [ ] Dropzone works (or fallback to button)
- [ ] Preview table is scrollable
- [ ] Error messages readable
- [ ] Success redirect works

---

## 🚀 Performance Targets

- File parsing (1000 rows): <1 second
- Validation (1000 rows): <2 seconds
- Upload (1MB file): <5 seconds
- Total flow (upload to success): <10 seconds

---

## 📞 Need Help?

**CSV not parsing?**
- Check PHASE_8.3_CODE_EXAMPLES.md → csv-parser.ts
- Try Papa Parse online tool: papaparse.com/demo

**Validation not working?**
- Check PHASE_8.3_PROMPT.md → Validation Logic section
- Copy validation function from examples

**Upload failing?**
- Verify backend is running: `curl http://localhost:8000/health`
- Check backend endpoint exists: check API docs
- Test with curl (see debugging commands above)

**UI not updating?**
- Check React state updates
- Verify step changes correctly
- Check browser console for errors

---

**Remember:** Start simple, test incrementally, iterate! 🎯
