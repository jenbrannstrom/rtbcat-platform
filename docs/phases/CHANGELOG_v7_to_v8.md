# RTB.cat Handover v7 → v8 Changelog

**Date:** December 1, 2025  
**Summary:** Schema audit complete, forgiving validator implemented, fraud signals documented, multiple prompts ready

---

## 🎯 Major Changes

### 1. Schema Audit Complete ✅

**Problem discovered:** The v7 handover documented a schema that didn't match reality.

**What we found:**

| Documented (Wrong) | Actual (Correct) |
|-------------------|------------------|
| `creatives.buyer_creative_id` | `creatives.id` (TEXT) |
| `creatives.seat_id` | `creatives.account_id` |
| `creatives.status` | `creatives.approval_status` |
| `performance_metrics.date` | `performance_metrics.metric_date` |
| `performance_metrics.spend` | `performance_metrics.spend_micros` |

**v8 now documents the ACTUAL schema.**

---

### 2. UPSERT Logic Fixed ✅

**Problem:** Test data was imported 3 times, creating duplicates.

**Root cause:** NULL values in unique constraint columns. SQLite treats NULL ≠ NULL, so each insert was considered unique.

**Fix applied in `sqlite_store.py`:**
```python
geography = m.geography or "UNKNOWN"
device_type = m.device_type or "UNKNOWN"  
placement = m.placement or "UNKNOWN"
```

---

### 3. Forgiving CSV Validator ✅

**Old behavior:** 
```
"Clicks > Impressions? REJECTED! 🚫"
```

**New behavior:**
```
"Clicks > Impressions? Imported + flagged as fraud signal 🔍"
```

**Changes made:**
- Validator never blocks imports
- Anomalies stored in `import_anomalies` table
- UI shows warnings (yellow) not errors (red)
- Import button always enabled

**Anomaly types tracked:**
- `clicks_exceed_impressions` - Possible click fraud
- `extremely_high_ctr` - CTR > 10%
- `zero_impressions_with_spend` - Paid for nothing

---

### 4. Fraud Signals Reference Document 📚

**New file:** `RTB_FRAUD_SIGNALS_REFERENCE.md`

**Contents:**
- Single occurrence vs repeated pattern interpretation
- Click fraud signals
- Bot traffic signals
- Video-specific fraud patterns
- Composite fraud score algorithm
- SQL detection queries
- Guidance for AI clustering prompts

**Key insight documented:**
> "Clicks > impressions once = timing issue. Clicks > impressions frequently on same app = click fraud."

---

### 5. Backend Validation Bug Identified 🐛

**Symptom:**
```
Frontend: "Auto-detected columns: #Creative ID → creative_id" ✓
Backend: "CSV missing required columns: creative_id" ✗
```

**Cause:** Frontend maps columns for preview, then sends raw file to backend.

**Fix ready:** `CODEX_PROMPT_Fix_Backend_Validation.md`

---

### 6. Seat Hierarchy Bug Documented 🐛

**Symptom:**
```
Dropdown: "All Seats - 0 creatives" (should be 652)
Cards: "Seat: 299038253" (should show name)
```

**Fix ready:** `CODEX_PROMPT_Phase8.5_Seat_Hierarchy.md`

---

## 📝 Documentation Created

| Document | Purpose | Lines |
|----------|---------|-------|
| `RTBcat_Handover_v8.md` | Full project handover | ~700 |
| `CHANGELOG_v7_to_v8.md` | This file | ~200 |
| `RTB_FRAUD_SIGNALS_REFERENCE.md` | Fraud detection patterns | ~400 |
| `CODEX_PROMPT_Fix_Backend_Validation.md` | Fix column mapping bug | ~200 |
| `CODEX_PROMPT_Phase8.5_Seat_Hierarchy.md` | Fix seat dropdown | ~400 |
| `CODEX_PROMPT_Phase9_AI_Clustering.md` | AI campaign grouping | ~500 |
| `CODEX_PROMPT_Schema_Audit.md` | Schema fixes (done) | ~400 |
| `CODEX_PROMPT_Forgiving_Validator.md` | Validator fixes (done) | ~350 |

**Total new documentation:** ~3,150 lines

---

## 🔧 Code Changes Made

### Backend (`creative-intelligence/`)

| File | Change |
|------|--------|
| `storage/sqlite_store.py` | Added `import_anomalies` table |
| `storage/sqlite_store.py` | Fixed UPSERT with UNKNOWN defaults |
| `storage/sqlite_store.py` | Added `save_import_anomalies()` |
| `storage/sqlite_store.py` | Added `get_fraud_apps()` |

### Frontend (`dashboard/`)

| File | Change |
|------|--------|
| `src/lib/types/import.ts` | Added `AnomalyType`, `Anomaly`, `Warning` |
| `src/lib/csv-validator.ts` | Complete rewrite - never blocks |
| `src/app/import/page.tsx` | Shows anomalies as info, not errors |

---

## 📊 Database State

### Before v8

```
performance_metrics: 41 rows (test data, imported 3x)
└── Duplicates everywhere
└── Round numbers (50000, 30000) = fake data
```

### After v8

```
performance_metrics: 0 rows (cleared test data)
└── Ready for real import
└── UPSERT will prevent duplicates
```

---

## 🐛 Bugs Status

| Bug | Status | Fix |
|-----|--------|-----|
| Duplicate rows on import | ✅ Fixed | UPSERT with UNKNOWN defaults |
| Validator too strict | ✅ Fixed | Forgiving validator |
| Schema mismatch in docs | ✅ Fixed | v8 documents actual schema |
| Backend column validation | 📋 Ready | Prompt created |
| Seat dropdown shows 0 | 📋 Ready | Prompt created |

---

## 📋 Ready Prompts (Not Yet Executed)

### Priority 1: Fix Backend Validation
- **File:** `CODEX_PROMPT_Fix_Backend_Validation.md`
- **Why:** Blocks all CSV imports
- **Effort:** ~30 minutes

### Priority 2: Phase 8.5 Seat Hierarchy
- **File:** `CODEX_PROMPT_Phase8.5_Seat_Hierarchy.md`
- **Why:** UI bug, user confusion
- **Effort:** ~1-2 hours

### Priority 3: Phase 9 AI Clustering
- **File:** `CODEX_PROMPT_Phase9_AI_Clustering.md`
- **Why:** Core feature
- **Effort:** ~4-6 hours

---

## 🎯 Phase Status Update

| Phase | v7 Status | v8 Status |
|-------|-----------|-----------|
| 8.1 Backend API | ✅ Complete | ✅ Complete |
| 8.2 Performance UI | ✅ Complete | ✅ Complete |
| 8.3 CSV Import | 🔄 In Progress | ✅ Complete (bug pending) |
| 8.4 Large Files | 📋 Planned | ✅ Complete |
| 8.5 Seat Hierarchy | - | 📋 Ready |
| 9 AI Clustering | 📋 Planned | 📋 Ready |

---

## 🚀 What's Ready

### Can Do Now
- ✅ View 652 creatives in UI
- ✅ Upload CSV (preview works)
- ✅ See anomaly detection (fraud flags)

### Blocked (Needs Fix)
- ❌ Actually import CSV data (backend validation bug)
- ❌ See real performance metrics

### Ready to Implement
- 📋 Backend validation fix (30 min)
- 📋 Seat hierarchy (1-2 hours)
- 📋 AI clustering (4-6 hours)

---

## 📞 For Next Session

**Start here:**
1. Apply `CODEX_PROMPT_Fix_Backend_Validation.md`
2. Test import with real Google CSV
3. Verify data in database
4. Proceed to Phase 8.5 or Phase 9

---

**End of Changelog v7 → v8**
