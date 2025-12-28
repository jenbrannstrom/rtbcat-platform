# Phase 8.2: Pre-Flight Checklist

**Before starting frontend work, verify the backend is ready**

---

## ✅ Backend Prerequisites (Phase 8.1)

### 1. Database Migration Complete

**Check if performance_metrics table exists:**

```bash
sqlite3 ~/.rtbcat/rtbcat.db ".tables"
```

**Expected output should include:**
```
campaigns          creatives          performance_metrics
buyer_seats        rtb_traffic
```

**Verify table structure:**

```bash
sqlite3 ~/.rtbcat/rtbcat.db ".schema performance_metrics"
```

**Expected output:**
```sql
CREATE TABLE performance_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creative_id INTEGER NOT NULL,
    date DATE NOT NULL,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    spend DECIMAL(10, 2) DEFAULT 0,
    geography VARCHAR(2),
    -- ... other columns
    FOREIGN KEY (creative_id) REFERENCES creatives(id)
);
```

**Status:** [ ] PASS / [ ] FAIL

---

### 2. API Endpoints Available

**Start the backend:**
```bash
cd /home/jen/Documents/rtbcat-platform/creative-intelligence
source venv/bin/activate
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

**Test endpoints exist:**

```bash
# Check API docs
curl http://localhost:8000/docs
# Should return HTML with API documentation

# Test health endpoint
curl http://localhost:8000/health
# Should return: {"status": "ok"}

# Test single performance metric endpoint
curl http://localhost:8000/api/performance/metrics/1?period=7d
# Should return JSON or 404 (both OK for now)

# Test batch endpoint
curl -X POST http://localhost:8000/api/performance/metrics/batch \
  -H "Content-Type: application/json" \
  -d '{"creative_ids": [1, 2, 3], "period": "7d"}'
# Should return JSON with data/missing arrays
```

**Status:** [ ] PASS / [ ] FAIL

---

### 3. Sample Data Available (Optional but Recommended)

**Check if sample performance data exists:**

```bash
sqlite3 ~/.rtbcat/rtbcat.db
SELECT COUNT(*) FROM performance_metrics;
.exit
```

**If count is 0, you can:**
- Option A: Work with "No data" states (valid approach)
- Option B: Ask Phase 8.1 developer to create sample data
- Option C: Import sample CSV (if Phase 8.1 import endpoint works)

**Sample CSV format for testing:**
```csv
creative_id,date,impressions,clicks,spend,geography
79783,2025-11-29,1000,50,25.50,US
79783,2025-11-28,950,45,23.75,US
79784,2025-11-29,500,10,5.00,BR
```

**Status:** [ ] Has data / [ ] No data (OK to proceed either way)

---

## 🔧 Environment Setup

### 1. Frontend Dependencies Installed

```bash
cd /home/jen/Documents/rtbcat-platform/dashboard
npm install
```

**Check package.json has:**
- Next.js (or React framework being used)
- TypeScript
- Tailwind CSS (or styling solution)

**Status:** [ ] PASS / [ ] FAIL

---

### 2. Development Server Works

```bash
cd /home/jen/Documents/rtbcat-platform/dashboard
npm run dev
```

**Should see:**
```
ready - started server on 0.0.0.0:3000
```

**Visit:** http://localhost:3000

**Status:** [ ] PASS / [ ] FAIL

---

### 3. Existing Creatives Page Works

**Navigate to creatives page** (usually http://localhost:3000/creatives)

**Verify:**
- [ ] Page loads without errors
- [ ] Creative cards display
- [ ] No console errors (check DevTools)
- [ ] Virtual scrolling works smoothly

**Status:** [ ] PASS / [ ] FAIL

---

## 📋 Quick Backend API Contract Verification

### Expected API Response Formats

**1. Single Performance Metric:**

```bash
curl http://localhost:8000/api/performance/metrics/79783?period=7d
```

**Expected response (if data exists):**
```json
{
  "creative_id": 79783,
  "period": "7d",
  "spend": 1234.56,
  "impressions": 50000,
  "clicks": 2500,
  "cpc": 0.45,
  "cpm": 2.20,
  "ctr": 0.05,
  "top_geo": "US",
  "geo_percentage": 45.2,
  "trend": 15.3,
  "updated_at": "2025-11-30T12:00:00Z"
}
```

**Expected response (if no data):**
```json
{
  "detail": "No performance data found for creative 79783 in period 7d"
}
```
**Status code:** 404

---

**2. Batch Performance Metrics:**

```bash
curl -X POST http://localhost:8000/api/performance/metrics/batch \
  -H "Content-Type: application/json" \
  -d '{"creative_ids": [79783, 79784, 79785], "period": "7d"}'
```

**Expected response:**
```json
{
  "data": [
    {
      "creative_id": 79783,
      "period": "7d",
      "spend": 1234.56,
      // ... other fields
    },
    {
      "creative_id": 79784,
      "period": "7d",
      "spend": 567.89,
      // ... other fields
    }
  ],
  "missing": [79785],
  "timestamp": "2025-11-30T12:00:00Z"
}
```

**Status:** [ ] Response format matches / [ ] Needs adjustment

---

## 🚨 Common Pre-Flight Issues

### Issue: Database table doesn't exist

**Solution:**
```bash
cd /home/jen/Documents/rtbcat-platform/creative-intelligence
source venv/bin/activate
python -m storage.migrations.run
```

---

### Issue: API endpoint returns 404

**Possible causes:**
1. Route not registered in `api/main.py`
2. Import missing
3. Wrong URL path

**Check:**
```python
# api/main.py should have:
from api.performance import router as performance_router
app.include_router(performance_router, prefix="/api/performance")
```

---

### Issue: CORS error in browser

**Backend should have CORS middleware:**

```python
# api/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

### Issue: Backend not running

**Check if port 8000 is in use:**
```bash
lsof -i :8000
# Or
ps aux | grep uvicorn
```

**Kill if needed:**
```bash
kill -9 <PID>
```

**Restart:**
```bash
cd creative-intelligence
source venv/bin/activate
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 📊 Performance Baseline

**Before starting Phase 8.2, measure current performance:**

### Page Load Time
```javascript
// In browser console on creatives page
performance.timing.loadEventEnd - performance.timing.navigationStart
```
**Current baseline:** _______ ms

### Scroll Performance
1. Open Chrome DevTools
2. Go to Performance tab
3. Click Record
4. Scroll through creatives
5. Stop recording
6. Check for dropped frames

**Current baseline:** Smooth 60fps? [ ] YES / [ ] NO

---

## ✅ Final Go/No-Go Decision

**Phase 8.2 is READY TO START if:**

- [x] Backend API is running on port 8000
- [x] Performance endpoints exist (even if returning empty data)
- [x] Frontend dev server works on port 3000/3001
- [x] Existing creatives page loads without errors
- [x] You have access to both codebases
- [x] CORS is configured (no browser errors)

**If any items above are NOT checked:**
→ Complete Phase 8.1 first, or notify Jen of blockers

---

## 🎯 What Phase 8.2 Needs from Backend

**Minimum requirements:**
1. ✅ GET /api/performance/metrics/{id}?period={period}
2. ✅ POST /api/performance/metrics/batch (optional but highly recommended)
3. ✅ Returns valid JSON
4. ✅ Handles 404 gracefully when no data
5. ✅ CORS enabled for localhost:3000

**Nice to have:**
- [ ] Sample data in database
- [ ] API documentation at /docs
- [ ] Error messages are descriptive
- [ ] Response times <100ms

---

## 🚀 Ready to Start

**If all checks pass, you can proceed with:**

1. Read `PHASE_8.2_PROMPT.md` (main requirements)
2. Review `PHASE_8.2_CODE_EXAMPLES.md` (implementation guide)
3. Keep `PHASE_8.2_QUICK_REFERENCE.md` open (troubleshooting)
4. Start coding!

**First step:**
Create TypeScript types in `/dashboard/types/performance.ts`

---

## 📞 Escalation Path

**If backend is not ready:**
1. Check this pre-flight checklist
2. Review Phase 8.1 documentation
3. Test API endpoints manually
4. Contact Phase 8.1 developer (Claude CLI)
5. Notify Jen if blocking issue

**If frontend environment issues:**
1. Check npm version: `npm --version` (should be 8+)
2. Check node version: `node --version` (should be 18+)
3. Clear cache: `rm -rf .next node_modules && npm install`
4. Restart dev server

---

## 📝 Notes Section

**Use this space to record any deviations or special configurations:**

```
Date: _____________
Backend Status: _____________
Special Notes: _____________






```

---

**Once all checks pass, proceed to Phase 8.2 development! 🎉**
