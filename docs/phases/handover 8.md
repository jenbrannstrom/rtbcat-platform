# RTB.cat Creative Intelligence Platform - Handover Document v8

**Date:** December 1, 2025  
**Project:** RTB.cat Creative Intelligence & Performance Analytics Platform  
**Status:** Phase 8.4 ✅ Complete, Phase 8.5 📋 Ready, Phase 9 📋 Ready  
**Developer:** Jen (jen@rtb.cat)  
**AI Assistants:** Claude CLI, Claude in VSCode, ChatGPT Codex CLI  
**Latest Updates:** Schema audit complete, forgiving validator implemented, fraud signals documented

---

## 🎯 Executive Summary

RTB.cat Creative Intelligence is a **comprehensive RTB (Real-Time Bidding) analytics platform** that helps media buyers optimize their programmatic advertising spend by:

1. **Collecting creatives** from Google Authorized Buyers API
2. **Importing performance data** from CSV exports
3. **Detecting fraud patterns** in traffic (click fraud, bot traffic)
4. **Clustering creatives into campaigns** using AI
5. **Identifying optimization opportunities** (undervalued geos, high-performing segments)

**Current State:**
- ✅ 652 creatives collected and stored
- ✅ CSV import pipeline working (with forgiving validation)
- ✅ Fraud anomaly detection implemented
- ✅ Schema audit complete, UPSERT logic fixed
- 🔄 Seat hierarchy needs cleanup (dropdown shows 0 creatives)
- 📋 AI Campaign Clustering ready to implement (Phase 9)

---

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [What's New in v8](#whats-new-in-v8)
3. [Phase Status Overview](#phase-status-overview)
4. [Database Schema (ACTUAL)](#database-schema-actual)
5. [Known Issues & Bugs](#known-issues--bugs)
6. [Pending Codex Prompts](#pending-codex-prompts)
7. [Fraud Detection Reference](#fraud-detection-reference)
8. [Server Management](#server-management)
9. [Claude CLI / VSCode Rules](#claude-cli--vscode-rules)
10. [File Locations](#file-locations)
11. [Next Steps](#next-steps)

---

## 🚀 Quick Start

### System Status

```bash
# Backend runs as systemd service
sudo systemctl status rtbcat-api
# Should show: Active (running)

# Check backend health
curl http://localhost:8000/health
# Should return: {"status": "ok"}

# Frontend
cd /home/jen/Documents/rtbcat-platform/dashboard
npm run dev

# Access Points
Dashboard: http://localhost:3000
Import Data: http://localhost:3000/import
API Docs: http://localhost:8000/docs
Database: ~/.rtbcat/rtbcat.db
```

### Database Quick Check

```bash
# Install sqlite3 if not present
sudo apt install sqlite3 -y

# Check current state
sqlite3 ~/.rtbcat/rtbcat.db "SELECT 'creatives', COUNT(*) FROM creatives UNION SELECT 'performance_metrics', COUNT(*) FROM performance_metrics;"

# Expected output:
# creatives|652
# performance_metrics|<varies based on imports>
```

### Restart Server After Code Changes

```bash
sudo systemctl restart rtbcat-api
sudo journalctl -u rtbcat-api -f  # View logs
```

---

## 🆕 What's New in v8

### 1. Schema Audit Complete ✅

**Problem discovered:** Handover docs described a different schema than what actually exists.

**Actual schema documented:** See [Database Schema (ACTUAL)](#database-schema-actual) section.

**Key findings:**
- `creatives.id` is TEXT (Google's creative ID), not INTEGER
- `performance_metrics` uses `metric_date` not `date`
- `spend_micros` stores spend × 1,000,000 (not dollars)
- Lookup tables exist (geographies, apps, publishers) but aren't fully utilized yet

### 2. UPSERT Logic Fixed ✅

**Problem:** Import ran 3x = 3 copies of every row (NULL ≠ NULL in SQL unique constraints)

**Fix applied in `sqlite_store.py`:**
```python
# Convert NULLs to 'UNKNOWN' for unique constraint columns
geography = m.geography or "UNKNOWN"
device_type = m.device_type or "UNKNOWN"
placement = m.placement or "UNKNOWN"
```

### 3. Forgiving CSV Validator ✅

**Old behavior:** "Clicks > Impressions? REJECTED!"

**New behavior:** "Clicks > Impressions? Imported + flagged as fraud signal"

**Changes made:**
- Never blocks imports (only unparseable files rejected)
- Anomalies flagged and stored in `import_anomalies` table
- Fraud signals: `clicks_exceed_impressions`, `extremely_high_ctr`, `zero_impressions_with_spend`
- UI shows warnings but allows import

### 4. Fraud Signals Documentation 📚

Created comprehensive reference: `RTB_FRAUD_SIGNALS_REFERENCE.md`

Key patterns documented:
- Clicks > Impressions (timing vs fraud)
- High impressions, zero clicks over time (bot traffic)
- Video starts with zero completions
- Suspiciously consistent metrics

### 5. Backend Validation Bug Identified 🐛

**Current bug:** Frontend maps columns correctly, but sends raw file to backend. Backend rejects because it sees `#Creative ID` instead of `creative_id`.

**Fix ready:** See `CODEX_PROMPT_Fix_Backend_Validation.md`

---

## 📊 Phase Status Overview

| Phase | Name | Status | Notes |
|-------|------|--------|-------|
| 1-6 | Core Platform | ✅ Complete | Creatives, analysis, smart URLs |
| 8.1 | Backend Performance API | ✅ Complete | Endpoints exist |
| 8.2 | Performance UI | ✅ Complete | Sort, badges, tier filter |
| 8.3 | CSV Import UI | ✅ Complete | Drag/drop, preview, validation |
| 8.4 | Large Files & Schema | ✅ Complete | UPSERT, normalization, retention |
| 8.5 | Seat Hierarchy | 📋 Ready | Prompt created, needs implementation |
| 9 | AI Campaign Clustering | 📋 Ready | Prompt created, needs implementation |

### Phase 8 Details

**8.1 Backend (Complete):**
- `POST /api/performance/import` - CSV upload
- `GET /api/performance/metrics/{creative_id}` - Get metrics
- `POST /api/performance/metrics/batch` - Batch insert

**8.2 Frontend UI (Complete):**
- Sort dropdown (Yesterday, 7d, 30d, All time)
- Performance badges on creative cards
- Tier filter (High/Medium/Low/No Data)

**8.3 CSV Import (Complete, bug pending):**
- Upload page at `/import`
- Drag & drop with preview
- Column auto-detection and mapping
- ⚠️ Bug: Backend rejects mapped columns (fix ready)

**8.4 Schema & Optimization (Complete):**
- Forgiving validator (never blocks)
- Fraud anomaly detection
- UPSERT logic fixed
- Lookup tables ready

---

## 🗄️ Database Schema (ACTUAL)

**IMPORTANT:** This is the REAL schema, not what previous docs described.

### creatives

```sql
CREATE TABLE creatives (
    id TEXT PRIMARY KEY,                    -- Google's creative ID (e.g., "144634")
    name TEXT,                              -- Full path: "buyers/299038253/creatives/144634"
    format TEXT,                            -- NATIVE, DISPLAY, VIDEO
    account_id TEXT,                        -- Buyer account: "299038253"
    approval_status TEXT,                   -- APPROVED, DISAPPROVED
    width INTEGER,
    height INTEGER,
    final_url TEXT,                         -- Landing page URL
    display_url TEXT,
    utm_source TEXT,
    utm_medium TEXT,
    utm_campaign TEXT,
    utm_content TEXT,
    utm_term TEXT,
    advertiser_name TEXT,
    campaign_id TEXT,                       -- FK to campaigns
    cluster_id TEXT,                        -- FK to clusters
    raw_data TEXT,                          -- JSON blob
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    canonical_size TEXT,                    -- e.g., "300x250"
    size_category TEXT,                     -- e.g., "medium_rectangle"
    buyer_id TEXT
);
```

### performance_metrics

```sql
CREATE TABLE performance_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creative_id TEXT NOT NULL,              -- FK to creatives.id (TEXT!)
    campaign_id TEXT,
    metric_date DATE NOT NULL,              -- Note: metric_date, not date
    impressions INTEGER NOT NULL DEFAULT 0,
    clicks INTEGER NOT NULL DEFAULT 0,
    spend_micros INTEGER NOT NULL DEFAULT 0, -- Spend × 1,000,000
    cpm_micros INTEGER,
    cpc_micros INTEGER,
    geography TEXT,
    device_type TEXT,
    placement TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    geo_id INTEGER,                         -- FK to geographies
    app_id_fk INTEGER,                      -- FK to apps
    billing_account_id INTEGER,
    publisher_id_fk INTEGER,
    seat_id INTEGER,
    reached_queries INTEGER DEFAULT 0       -- QPS metric
);

-- Unique constraint (with UNKNOWN defaults to prevent NULL duplicates)
CREATE UNIQUE INDEX idx_perf_unique_daily ON performance_metrics(
    creative_id, metric_date, geography, device_type, placement
);
```

### Lookup Tables (Exist, Partially Used)

```sql
-- 51 countries pre-populated
CREATE TABLE geographies (
    id INTEGER PRIMARY KEY,
    country_code TEXT,
    country_name TEXT UNIQUE NOT NULL
);

-- Exists, needs population during import
CREATE TABLE apps (
    id INTEGER PRIMARY KEY,
    app_id TEXT UNIQUE,
    app_name TEXT,
    platform TEXT,
    quality_tier TEXT DEFAULT 'unknown',
    first_seen TIMESTAMP
);

-- Exists
CREATE TABLE publishers (
    id INTEGER PRIMARY KEY,
    publisher_id TEXT UNIQUE,
    publisher_name TEXT,
    first_seen TIMESTAMP
);
```

### import_anomalies (New in v8)

```sql
CREATE TABLE import_anomalies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    import_id TEXT,
    row_number INTEGER,
    anomaly_type TEXT NOT NULL,             -- 'clicks_exceed_impressions', etc.
    creative_id TEXT,
    app_id TEXT,
    app_name TEXT,
    details TEXT,                           -- JSON blob
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🐛 Known Issues & Bugs

### Critical: Backend CSV Validation Mismatch

**Status:** Fix ready, not yet applied

**Symptom:**
```
Frontend: "Auto-detected: #Creative ID → creative_id" ✓
Backend: "CSV missing required columns: creative_id" ✗
```

**Cause:** Frontend maps columns for preview, then sends raw file to backend. Backend does its own validation and rejects.

**Fix:** `CODEX_PROMPT_Fix_Backend_Validation.md` - Either send mapped JSON or apply same normalization in backend.

---

### Important: Seat Dropdown Shows 0 Creatives

**Status:** Prompt ready, not yet implemented

**Symptom:**
```
Dropdown: "All Seats - 0 creatives"  (Should show 652)
Card: "Seat: 299038253"              (Should show name)
```

**Cause:** Query not joining correctly, or creatives missing seat_id.

**Fix:** `CODEX_PROMPT_Phase8.5_Seat_Hierarchy.md`

---

### Minor: Test Data Was Imported

**Status:** Resolved

The database previously had fake test data (round numbers like 50000, 30000) imported 3x. This was cleared. Any remaining test data should be purged:

```bash
# Check for suspicious round numbers
sqlite3 ~/.rtbcat/rtbcat.db "SELECT * FROM performance_metrics WHERE impressions IN (50000, 30000, 5000);"

# Clear if found
sqlite3 ~/.rtbcat/rtbcat.db "DELETE FROM performance_metrics WHERE impressions IN (50000, 30000, 5000);"
```

---

## 📝 Pending Codex Prompts

These prompts are ready to execute. Located in `/mnt/user-data/outputs/` or project docs folder.

### 1. CODEX_PROMPT_Fix_Backend_Validation.md ⭐ PRIORITY

**What:** Fix the column name mismatch between frontend and backend
**Why:** Blocks all CSV imports
**Effort:** ~30 minutes

### 2. CODEX_PROMPT_Phase8.5_Seat_Hierarchy.md

**What:** Fix seat dropdown, display names, clarify hierarchy
**Why:** UI bug, user confusion
**Effort:** ~1-2 hours

### 3. CODEX_PROMPT_Phase9_AI_Clustering.md

**What:** Group 652 creatives into ~15-20 campaigns using AI
**Why:** Core feature for usability
**Effort:** ~4-6 hours

### 4. CODEX_PROMPT_Forgiving_Validator.md ✅ DONE

**What:** Make validator import all data, flag anomalies
**Status:** Implemented

### 5. CODEX_PROMPT_Schema_Audit.md ✅ DONE

**What:** Audit and fix database schema
**Status:** Implemented

---

## 🚨 Fraud Detection Reference

Key fraud signals to watch for (full doc: `RTB_FRAUD_SIGNALS_REFERENCE.md`):

### Clicks > Impressions

| Frequency | Meaning | Action |
|-----------|---------|--------|
| Once | Timing (24h cutoff) | Ignore |
| Frequently (same app) | Click fraud | Flag app |
| Always | Definite fraud | Block app |

### High Impressions, Zero Clicks

| Duration | Meaning | Action |
|----------|---------|--------|
| 1 day | Normal | Ignore |
| 7+ days | Bot traffic | Flag app |
| 30+ days, 1000s imps | Bot farm (99%) | Block app |

### Video Funnel

| Pattern | Meaning |
|---------|---------|
| 30-50% completion | Normal (skippable) |
| < 10% completion | Poor |
| 0% (many starts) | Fraud - fake player or broken |

### Campaign-Specific Context

> *"TrueCaller inventory is good in India. Outside it, non-converting garbage. But this may not be for ALL campaigns - it has to be looked at for every campaign."* — Jen

---

## 🖥️ Server Management

### Systemd Service

```bash
# Service file: /etc/systemd/system/rtbcat-api.service
# The backend runs as a managed service, not manually

# Commands
sudo systemctl status rtbcat-api    # Check status
sudo systemctl restart rtbcat-api   # Restart after code changes
sudo systemctl stop rtbcat-api      # Stop
sudo systemctl start rtbcat-api     # Start
sudo journalctl -u rtbcat-api -f    # View logs (live)
sudo journalctl -u rtbcat-api -n 50 # Last 50 log lines
```

### Service File Content

```ini
[Unit]
Description=RTB.cat API Server
After=network.target

[Service]
Type=simple
User=jen
WorkingDirectory=/home/jen/Documents/rtbcat-platform/creative-intelligence
ExecStart=/usr/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

---

## 🤖 Claude CLI / VSCode Rules

### Server Management (CRITICAL)

**Claude NEVER directly manages the server. Always tell the user to restart.**

```
❌ NEVER DO:
- subprocess.run(["pkill", "uvicorn"])
- os.system("kill ...")
- Any direct process management

✅ ALWAYS DO:
- Make code changes
- Tell user: "Please restart: sudo systemctl restart rtbcat-api"
- Continue with other work
```

### File Editing

```
✅ DO:
- Edit files in /home/jen/Documents/rtbcat-platform/
- Create new files as needed
- Run npm/pip commands

❌ DON'T:
- Edit system files without permission
- Delete files without confirmation
- Run commands that affect other services
```

### Database Access

```bash
# Read-only queries are fine
sqlite3 ~/.rtbcat/rtbcat.db "SELECT COUNT(*) FROM creatives;"

# Write operations - be careful, confirm with user
# Especially DELETE, DROP, TRUNCATE
```

### Documentation

When making changes, update:
1. This handover document (increment version)
2. CHANGELOG if significant
3. Inline code comments

---

## 📁 File Locations

### Project Structure

```
/home/jen/Documents/rtbcat-platform/
├── creative-intelligence/          # Python backend
│   ├── api/
│   │   ├── main.py                # FastAPI app
│   │   ├── performance.py         # Performance endpoints
│   │   └── ...
│   ├── storage/
│   │   ├── sqlite_store.py        # Database operations
│   │   └── ...
│   └── ...
├── dashboard/                      # Next.js frontend
│   ├── src/
│   │   ├── app/
│   │   │   ├── import/
│   │   │   │   └── page.tsx       # CSV import UI
│   │   │   ├── creatives/
│   │   │   │   └── page.tsx       # Creatives list
│   │   │   └── ...
│   │   ├── lib/
│   │   │   ├── csv-parser.ts      # CSV parsing
│   │   │   ├── csv-validator.ts   # Validation (forgiving)
│   │   │   ├── api.ts             # API client
│   │   │   └── ...
│   │   └── components/
│   │       └── ...
│   └── ...
└── docs/                           # Documentation
    ├── phases/
    ├── fixes/
    └── RTB_FRAUD_SIGNALS_REFERENCE.md
```

### Key Files

| File | Purpose |
|------|---------|
| `creative-intelligence/storage/sqlite_store.py` | All database operations |
| `creative-intelligence/api/performance.py` | Performance import endpoint |
| `dashboard/src/app/import/page.tsx` | CSV upload UI |
| `dashboard/src/lib/csv-validator.ts` | Forgiving validation |
| `dashboard/src/lib/api.ts` | Frontend API client |
| `~/.rtbcat/rtbcat.db` | SQLite database |

---

## 🎯 Next Steps

### Immediate (Fix Blockers)

1. **Fix Backend Validation** ⭐
   - Apply `CODEX_PROMPT_Fix_Backend_Validation.md`
   - Test: Import a real Google CSV
   - Verify: Data appears in database

2. **Test Full Import Flow**
   - Upload CSV at `/import`
   - Check `performance_metrics` table
   - Verify UI shows real data

### Short Term (This Week)

3. **Fix Seat Dropdown (Phase 8.5)**
   - Apply `CODEX_PROMPT_Phase8.5_Seat_Hierarchy.md`
   - Connect 3-seat account for testing
   - Document actual hierarchy

4. **AI Campaign Clustering (Phase 9)**
   - Apply `CODEX_PROMPT_Phase9_AI_Clustering.md`
   - Group 652 creatives into campaigns
   - Test clustering UI

### Medium Term (Next 2 Weeks)

5. **Phase 10: Opportunity Detection**
   - Find undervalued geos
   - Identify high-performing low-spend creatives
   - Generate recommendations

6. **Fraud Dashboard**
   - Display apps with fraud signals
   - Allow blocking suspicious apps
   - Show quality tiers

---

## 📊 Current Metrics

| Metric | Value |
|--------|-------|
| Creatives in DB | 652 |
| Performance rows | Varies (import pending) |
| Geographies | 51 pre-populated |
| Phases complete | 1-6, 8.1-8.4 |
| Open bugs | 2 (validation, seat dropdown) |
| Pending prompts | 3 ready to execute |

---

## 🔧 Useful Commands

### Database Inspection

```bash
# Tables
sqlite3 ~/.rtbcat/rtbcat.db ".tables"

# Schema for a table
sqlite3 ~/.rtbcat/rtbcat.db ".schema performance_metrics"

# Row counts
sqlite3 ~/.rtbcat/rtbcat.db "SELECT 'creatives', COUNT(*) FROM creatives UNION SELECT 'performance_metrics', COUNT(*) FROM performance_metrics;"

# Check for duplicates
sqlite3 ~/.rtbcat/rtbcat.db "SELECT creative_id, metric_date, COUNT(*) FROM performance_metrics GROUP BY creative_id, metric_date HAVING COUNT(*) > 1;"

# Recent imports
sqlite3 ~/.rtbcat/rtbcat.db "SELECT DISTINCT metric_date FROM performance_metrics ORDER BY metric_date DESC LIMIT 10;"
```

### Frontend Development

```bash
cd /home/jen/Documents/rtbcat-platform/dashboard
npm run dev          # Start dev server
npm run build        # Production build
npm run lint         # Check for issues
```

### Logs

```bash
# Backend logs
sudo journalctl -u rtbcat-api -f

# Frontend (in dev mode, logs appear in terminal)
```

---

## 📞 Context for Next Engineer

### What Jen Does

- Media buyer running RTB campaigns via Google Authorized Buyers
- Has 652+ creatives across potentially multiple seats
- Imports daily CSV reports from Google
- Needs to optimize QPS & spend, identify fraud, group creatives to do the optimisation

### Tech Stack

- **Backend:** Python, FastAPI, SQLite
- **Frontend:** Next.js 14, React, TypeScript, Tailwind
- **AI:** Claude API for clustering (Phase 9)
- **Infrastructure:** Ubuntu, systemd

### Working Style

- Uses Claude CLI and Claude in VSCode for development
- Also uses ChatGPT Codex CLI for some tasks
- Prefers forgiving systems (import everything, flag issues)
- Values domain expertise being captured in docs (see fraud signals)

### Key Domain Terms

| Term | Meaning |
|------|---------|
| RTB | Real-Time Bidding - auction for ad impressions |
| QPS | Queries Per Second - bid requests received |
| Creative | An ad (image, video, native) |
| Seat | A bidding entity within a buyer account |
| SSP | Supply-Side Platform (Google is one) |
| CPM | Cost Per Mille (per 1000 impressions) |
| CTR | Click-Through Rate |



---

## 🎉 Version History

### v8.0 - December 1, 2025 (Current)
- ✅ Schema audit complete (documented ACTUAL schema)
- ✅ UPSERT logic fixed (prevents duplicate imports)
- ✅ Forgiving CSV validator (never blocks, flags anomalies)
- ✅ Fraud signals reference created
- 🐛 Identified backend validation mismatch (fix ready)
- 📝 Created prompts for Phase 8.5, Phase 9

### v7.0 - November 30, 2025
- ✅ Phase 8.2: Performance UI complete
- ✅ Systemd service configured
- 🔄 Phase 8.3: CSV import UI created

### v6.0 - November 30, 2025
- 🔄 Phase 8 started
- 📝 Strategic pivot to performance-first analytics

### v5.0 and earlier
- Phases 1-6 complete
- 652 creatives collected
- Core platform established

---

## 🚀 Ready to Continue

**Priority order:**
1. Fix backend validation (blocks imports)
2. Test full import with real data
3. Fix seat dropdown (UI polish)
4. Implement AI clustering (major feature)

**All prompts are ready. Just pick one and execute!**

---

**End of Handover Document v8**

*Last updated: December 1, 2025*  
*Next update: After backend validation fix and successful import*

---

**Developer:** Jen (jen@rtb.cat)  
**Project:** RTB.cat Creative Intelligence  
**Repository:** /home/jen/Documents/rtbcat-platform/  
**Status:** 🚀 READY FOR NEXT PHASE