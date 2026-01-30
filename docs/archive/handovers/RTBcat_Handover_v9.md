# RTB.cat Creative Intelligence Platform - Handover Document v9

**Date:** December 1, 2025  
**Project:** RTB.cat Creative Intelligence & Performance Analytics Platform  
**Status:** Phase 8.4 ✅ Complete, Phase 8.5 📋 Ready, Phase 9 📋 Ready, **QPS Optimization Module 📋 Designed**  
**Developer:** Jen (jen@rtb.cat)  
**AI Assistants:** Claude CLI, Claude in VSCode, ChatGPT Codex CLI  
**Latest Updates:** QPS optimization system fully designed, pretargeting configs documented, size filtering strategy defined

---

## 🎯 Executive Summary

RTB.cat Creative Intelligence is a **comprehensive RTB (Real-Time Bidding) analytics platform** that helps media buyers optimize their programmatic advertising spend by:

1. **Collecting creatives** from Google Authorized Buyers API
2. **Importing performance data** from CSV exports (BigQuery or UI)
3. **Detecting fraud patterns** in traffic (click fraud, bot traffic)
4. **Clustering creatives into campaigns** using AI
5. **Optimizing QPS** by analyzing size coverage and pretargeting efficiency
6. **Identifying opportunities** (undervalued sizes, cheap inventory)

**Current State:**
- ✅ 653 creatives collected and stored
- ✅ CSV import pipeline working (with forgiving validation)
- ✅ Fraud anomaly detection implemented
- ✅ Schema audit complete, UPSERT logic fixed
- ✅ API access verified (Creatives API, Pretargeting API working)
- ✅ All 10 pretargeting configs documented with Billing IDs
- ✅ QPS optimization system fully designed (ready to implement)
- 🔄 Seat hierarchy needs cleanup (dropdown shows 0 creatives)
- 📋 AI Campaign Clustering ready to implement (Phase 9)

---

## 📋 Table of Contents

1. [Quick Start](#quick-start)
2. [What's New in v9](#whats-new-in-v9)
3. [QPS Optimization System](#qps-optimization-system)
4. [Pretargeting Configs](#pretargeting-configs)
5. [Endpoint Configuration](#endpoint-configuration)
6. [Phase Status Overview](#phase-status-overview)
7. [Database Schema](#database-schema)
8. [Known Issues & Bugs](#known-issues--bugs)
9. [Pending Claude CLI Prompts](#pending-claude-cli-prompts)
10. [Server Management](#server-management)
11. [File Locations](#file-locations)
12. [Google API Configuration](#google-api-configuration)
13. [Next Steps](#next-steps)

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

### Test API Access

```bash
cd /home/jen/Documents/rtbcat-platform/creative-intelligence
source venv/bin/activate
python scripts/test_api_access.py
```

**Expected output:**
```
[OK] Credentials file exists
[PASS] Found 653 creatives
[PASS] Found 10 pretargeting configs
```

### Database Quick Check

```bash
sqlite3 ~/.rtbcat/rtbcat.db "SELECT 'creatives', COUNT(*) FROM creatives UNION SELECT 'performance_metrics', COUNT(*) FROM performance_metrics;"

# Expected output:
# creatives|653
# performance_metrics|<varies based on imports>
```

---

## 🆕 What's New in v9

### 1. QPS Optimization System Designed ✅

**Complete system architecture for reducing wasted QPS:**

- Size Coverage Analyzer: Maps your creatives to market sizes
- Include List Generator: Produces safe pretargeting size lists
- Fraud Signal Detector: Flags patterns for human review
- All outputs are "printouts" for manual implementation

**Key insight documented:** Size filtering is INCLUDE-only. Adding one size to pretargeting excludes all others.

### 2. All 10 Pretargeting Configs Documented ✅

| Billing ID | Name | Geos | Budget | QPS Limit |
|------------|------|------|--------|-----------|
| 72245759413 | Africa/Asia Mix | BF,BR,CI,CM,EG,NG,SA,SE,IN,PH,KZ | $1,200 | 50K |
| 83435423204 | ID/BR Android | ID,BR,IN,US,KR,ZA,AR | $2,000 | 50K |
| 104602012074 | MENA iOS&AND | SA,AE,EG,PH,IT,ES,BF,KZ,FR,PE,ZA,HU,SK | $1,200 | 50K |
| 137175951277 | SEA Whitelist | BR,ID,MY,TH,VN | $1,200 | 30K |
| 151274651962 | USEast CA/MX | CA,MX | $1,500 | 5K |
| 153322387893 | Brazil Android | BR | $1,500 | 30K |
| 155546863666 | Asia BL2003 | ID,IN,TH,CN,KR,TR,VN,BD,PH,MY | $1,800 | 50K |
| 156494841242 | Nova WL | ? | $2,000 | 30K |
| 157331516553 | US/Global | US,PH,AU,KR,EG,PK,BD,UZ,SA,JP,PE,ZA,HU,SK,AR,KW | $3,000 | 50K |
| 158323666240 | BR/PH Spotify | BR,PH (Spotify) | $2,000 | 30K |

**Total Daily Budget:** ~$17,600  
**Total Pretargeting QPS Cap:** 375K (limited by endpoints to 90K)

### 3. Endpoint Configuration Documented ✅

| Location | URL | QPS Limit |
|----------|-----|-----------|
| US West | bidder.novabeyond.com | 10,000 |
| Asia | bidder-sg.novabeyond.com | 30,000 |
| US East | bidder-us.novabeyond.com | 50,000 |

**Total Endpoint Capacity:** 90,000 QPS (the real bottleneck)

### 4. API Access Verified ✅

```
Credentials: ~/.rtb-cat/credentials/google-credentials.json
Service Account: rtb-cat-collector@creative-intel-api.iam.gserviceaccount.com
Project: creative-intel-api

APIs Working:
  ✅ Creatives API (653 creatives)
  ✅ Pretargeting API (10 configs)
  ❌ Buyer Seats API (needs fix - AttributeError)
  📋 RTB Troubleshooting API (not yet integrated)
```

### 5. CSV Data Structure Understood ✅

**BigQuery CSV has 46 columns including:**
- `Creative size` - The key field for size analysis
- `Billing ID` - Maps to pretargeting config
- `Reached queries` - QPS that matched pretargeting
- `Impressions` - Successful ad deliveries
- Full video metrics, VAST errors, viewability data

### 6. Pretargeting Logic Documented ✅

```
PRETARGETING LOGIC:
├── All settings use AND with each other
├── Exception: Web/App use OR with each other
├── Exception: Sizes within a list use OR with each other
│
├── SIZE FILTERING (Critical!):
│   ├── Leave blank = Accept ALL sizes
│   ├── Add ONE size = ONLY that size (all others excluded)
│   └── Add MULTIPLE = Those sizes accepted (OR within list)
│
└── ⚠️ There is NO "exclude" option - it's INCLUDE-only
```

### 7. Fraud Detection Limitations Documented ✅

- VPNs make geographic analysis unreliable
- Smart fraudsters mix 70-80% real with 20-30% fake
- Pure fraud gets caught by Google's systems
- RTBcat can only flag patterns for human review

---

## 📊 QPS Optimization System

### The Problem

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TRUE QPS WASTE                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  WASTE = Reached queries for sizes you have NO creatives for               │
│                                                                             │
│  NOT WASTE:                                                                 │
│  - Impressions without clicks (normal funnel, 95%+ expected)               │
│  - Lost auctions (normal competition)                                      │
│  - Low conversion rates (cost of doing business)                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### The Solution

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    RTBcat QPS OPTIMIZATION MODULES                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. SIZE COVERAGE ANALYZER                                                  │
│     - Maps your 653 creatives to market sizes                              │
│     - Calculates match rate (% of QPS you can serve)                       │
│     - Identifies gap (sizes you receive but can't serve)                   │
│                                                                             │
│  2. INCLUDE LIST GENERATOR                                                  │
│     - Produces safe size list for pretargeting                             │
│     - Only includes sizes you have creatives for                           │
│     - Warns about excluding future sizes                                   │
│                                                                             │
│  3. FRAUD SIGNAL DETECTOR                                                   │
│     - Flags suspicious patterns (high CTR, clicks > impressions)           │
│     - Does NOT claim definitive fraud                                      │
│     - All signals require human review                                     │
│                                                                             │
│  4. OPPORTUNITY FINDER (Planned)                                            │
│     - Identifies high-volume sizes worth creating creatives for            │
│     - Briefs for creative team                                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### The Trade-off

| Strategy | Keep | Lose | Risk |
|----------|------|------|------|
| Blank (all sizes) | All opportunities | N/A | ~25% waste on unservable sizes |
| Include your sizes only | Zero waste | Future new sizes | Must maintain list |
| Include + quarterly review | Low waste | Some new sizes temporarily | Management overhead |

---

## 🎯 Pretargeting Configs

### Full Configuration Details

```python
PRETARGETING_CONFIGS = {
    "72245759413": {
        "name": "Africa/Asia Mix",
        "display_name": "BF, BR, CI, CM, EG, NG, SA, SE, IN, PH, KZ",
        "geos": ["BF", "BR", "CI", "CM", "EG", "NG", "SA", "SE", "IN", "PH", "KZ"],
        "budget": 1200,
        "qps_limit": 50000
    },
    "83435423204": {
        "name": "ID/BR Android",
        "display_name": "ID\\BR \\IN\\US\\KR\\ZA\\AR Android",
        "geos": ["ID", "BR", "IN", "US", "KR", "ZA", "AR"],
        "platform": "Android",
        "budget": 2000,
        "qps_limit": 50000
    },
    "104602012074": {
        "name": "MENA iOS&AND",
        "display_name": "SA,UAE, EGY, PH,IT,ES,BF\\KZ\\FR\\PE\\ZA\\HU\\SK: iOS&AND",
        "geos": ["SA", "AE", "EG", "PH", "IT", "ES", "BF", "KZ", "FR", "PE", "ZA", "HU", "SK"],
        "budget": 1200,
        "qps_limit": 50000
    },
    "137175951277": {
        "name": "SEA Whitelist",
        "display_name": "BR\\iD\\MY\\TH\\VN/ - WL",
        "geos": ["BR", "ID", "MY", "TH", "VN"],
        "budget": 1200,
        "qps_limit": 30000
    },
    "151274651962": {
        "name": "USEast CA/MX",
        "display_name": "(USEast) CA, MX, blackList",
        "geos": ["CA", "MX"],
        "budget": 1500,
        "qps_limit": 5000
    },
    "153322387893": {
        "name": "Brazil Android",
        "display_name": "BRAZ, Android-919WL",
        "geos": ["BR"],
        "platform": "Android",
        "budget": 1500,
        "qps_limit": 30000
    },
    "155546863666": {
        "name": "Asia BL2003",
        "display_name": "(Asia) ID, IN, TH\\CN\\KR\\TR\\VN\\BD\\PH\\MY\\ \\IE-\\ZA- BL2003",
        "geos": ["ID", "IN", "TH", "CN", "KR", "TR", "VN", "BD", "PH", "MY"],
        "budget": 1800,
        "qps_limit": 50000
    },
    "156494841242": {
        "name": "Nova WL",
        "display_name": "Nova WL",
        "geos": [],  # Unknown
        "budget": 2000,
        "qps_limit": 30000
    },
    "157331516553": {
        "name": "US/Global",
        "display_name": "US\\PH\\AU\\KR\\EG\\PK\\BD\\UZ\\SA\\JP\\PE\\ZA\\HU\\SK\\AR\\KW And&iOS",
        "geos": ["US", "PH", "AU", "KR", "EG", "PK", "BD", "UZ", "SA", "JP", "PE", "ZA", "HU", "SK", "AR", "KW"],
        "budget": 3000,
        "qps_limit": 50000
    },
    "158323666240": {
        "name": "BR/PH Spotify",
        "display_name": "BR PH com.spotify.music",
        "geos": ["BR", "PH"],
        "apps": ["com.spotify.music"],
        "budget": 2000,
        "qps_limit": 30000
    }
}
```

---

## 🌐 Endpoint Configuration

```python
ENDPOINTS = {
    "us_west": {
        "url": "https://bidder.novabeyond.com/dsp/doubleclick/bidding.do",
        "qps": 10000,
        "location": "US West",
        "protocol": "OpenRTB/JSON"
    },
    "asia": {
        "url": "https://bidder-sg.novabeyond.com/dsp/doubleclick/bidding.do",
        "qps": 30000,
        "location": "Asia",
        "protocol": "OpenRTB/JSON"
    },
    "us_east": {
        "url": "https://bidder-us.novabeyond.com/dsp/doubleclick/bidding.do",
        "qps": 50000,
        "location": "US East",
        "protocol": "OpenRTB/JSON"
    }
}

# Total: 90,000 QPS (this is the real limit, not the 375K pretargeting sum)
```

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
| **10** | **QPS Optimization** | **📋 Designed** | **Full system architecture ready** |

---

## 🗄️ Database Schema

### Existing Tables (from v8)

```sql
-- creatives (653 rows)
-- performance_metrics
-- import_anomalies
-- geographies (51 countries)
-- apps
-- publishers
```

### New Tables for QPS Optimization (to be created)

```sql
-- Pretargeting configurations
CREATE TABLE IF NOT EXISTS pretargeting_configs (
    id INTEGER PRIMARY KEY,
    billing_id TEXT UNIQUE NOT NULL,
    name TEXT,
    display_name TEXT,
    geos TEXT,  -- JSON array
    platforms TEXT,  -- JSON array or NULL for all
    apps TEXT,  -- JSON array for app-specific configs
    budget_daily REAL,
    qps_limit INTEGER,
    current_size_filter TEXT,  -- JSON array of included sizes
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Endpoint configurations
CREATE TABLE IF NOT EXISTS endpoints (
    id INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    url TEXT NOT NULL,
    qps_limit INTEGER NOT NULL,
    location TEXT NOT NULL,
    is_active BOOLEAN DEFAULT 1
);

-- Daily aggregated metrics by size
CREATE TABLE IF NOT EXISTS size_metrics_daily (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_date DATE NOT NULL,
    billing_id TEXT NOT NULL,
    creative_size TEXT NOT NULL,
    country TEXT,
    platform TEXT,
    environment TEXT,
    reached_queries INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    spend_micros INTEGER DEFAULT 0,
    video_starts INTEGER DEFAULT 0,
    video_completions INTEGER DEFAULT 0,
    vast_errors INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(metric_date, billing_id, creative_size, country, platform, environment)
);

-- Creative size coverage analysis
CREATE TABLE IF NOT EXISTS creative_size_coverage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creative_size TEXT UNIQUE NOT NULL,
    creative_count INTEGER DEFAULT 0,
    creative_ids TEXT,  -- JSON array
    is_google_standard BOOLEAN DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Fraud signals (patterns for human review)
CREATE TABLE IF NOT EXISTS fraud_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    app_id TEXT,
    app_name TEXT,
    signal_type TEXT,
    signal_strength TEXT,  -- 'low', 'medium', 'high'
    evidence TEXT,  -- JSON
    days_observed INTEGER,
    status TEXT DEFAULT 'pending',
    reviewed_by TEXT,
    reviewed_at TIMESTAMP,
    notes TEXT
);
```

---

## 🐛 Known Issues & Bugs

| Bug | Status | Fix |
|-----|--------|-----|
| Duplicate rows on import | ✅ Fixed | UPSERT with UNKNOWN defaults |
| Validator too strict | ✅ Fixed | Forgiving validator |
| Schema mismatch in docs | ✅ Fixed | v8 documents actual schema |
| Backend column validation | ✅ Fixed | Column mapping implemented |
| Seat dropdown shows 0 | 📋 Ready | Prompt created |
| Buyer Seats API error | 🐛 Open | AttributeError on bidders.buyers |

---

## 📋 Pending Claude CLI Prompts

### Priority 1: QPS Optimization Analyzer
- **File:** `CLAUDE_CLI_QPS_Optimization_Analyzer_v2.md`
- **Why:** Core feature for reducing wasted QPS
- **Creates:**
  - `importers/bigquery_csv_importer.py`
  - `analyzers/size_coverage_analyzer.py`
  - `analyzers/fraud_signal_detector.py`
  - `cli/qps_analyzer.py`
- **Effort:** ~2-3 hours

### Priority 2: RTB API Setup Documentation
- **File:** `CLAUDE_CLI_RTB_API_Setup_and_Documentation.md`
- **Why:** Documents API access, creates test scripts
- **Effort:** ~30-45 minutes

### Priority 3: Phase 8.5 Seat Hierarchy
- **File:** `CODEX_PROMPT_Phase8.5_Seat_Hierarchy.md`
- **Why:** UI bug, user confusion
- **Effort:** ~1-2 hours

### Priority 4: Phase 9 AI Clustering
- **File:** `CODEX_PROMPT_Phase9_AI_Clustering.md`
- **Why:** Core feature
- **Effort:** ~4-6 hours

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

### QPS Changes (NEW IN v9)

```
⚠️ CRITICAL: Pretargeting changes affect live bidding!

✅ ALWAYS DO:
- Generate "printout" recommendations
- Require human review before changes
- Suggest monitoring for 24-48 hours after changes

❌ NEVER DO:
- Automatically apply pretargeting changes via API
- Claim definitive fraud detection
- Recommend changes without explaining trade-offs
```

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
│   │   └── sqlite_store.py        # Database operations
│   ├── collectors/
│   │   ├── creatives/client.py    # Creatives API client
│   │   ├── seats.py               # Buyer seats client
│   │   └── pretargeting/client.py # Pretargeting API client
│   ├── scripts/
│   │   └── test_api_access.py     # API access test
│   ├── importers/                 # (To be created)
│   │   └── bigquery_csv_importer.py
│   ├── analyzers/                 # (To be created)
│   │   ├── size_coverage_analyzer.py
│   │   └── fraud_signal_detector.py
│   └── cli/                       # (To be created)
│       └── qps_analyzer.py
├── dashboard/                      # Next.js frontend
│   ├── src/
│   │   ├── app/
│   │   │   ├── import/page.tsx
│   │   │   ├── creatives/page.tsx
│   │   │   └── ...
│   │   ├── lib/
│   │   │   ├── csv-parser.ts
│   │   │   ├── csv-validator.ts
│   │   │   └── api.ts
│   │   └── components/
│   └── ...
└── docs/
    ├── RTBcat_QPS_Optimization_Strategy_v2.md
    ├── CLAUDE_CLI_QPS_Optimization_Analyzer_v2.md
    └── ...
```

### Key Files

| File | Purpose |
|------|---------|
| `~/.rtbcat/rtbcat.db` | SQLite database |
| `~/.rtb-cat/credentials/google-credentials.json` | API credentials |
| `creative-intelligence/storage/sqlite_store.py` | All database operations |
| `creative-intelligence/api/main.py` | FastAPI app with column mapping |
| `dashboard/src/app/import/page.tsx` | CSV upload UI |

---

## 🔐 Google API Configuration

### Credentials

```
Path: ~/.rtb-cat/credentials/google-credentials.json
Type: Service Account
Project: creative-intel-api
Service Account: rtb-cat-collector@creative-intel-api.iam.gserviceaccount.com
```

### APIs Integrated

| API | Status | Scope |
|-----|--------|-------|
| Real-time Bidding API v1 | ✅ Working | `https://www.googleapis.com/auth/realtime-bidding` |
| Creatives | ✅ Working | 653 creatives fetched |
| Pretargeting Configs | ✅ Working | 10 configs fetched |
| Buyer Seats | ❌ Error | AttributeError (needs fix) |
| Ad Exchange Buyer II | 📋 Not integrated | For RTB Troubleshooting |

### Test API Access

```bash
cd /home/jen/Documents/rtbcat-platform/creative-intelligence
source venv/bin/activate
python scripts/test_api_access.py
```

---

## 🎯 Next Steps

### Immediate (This Session)

1. **Implement QPS Optimization Analyzer**
   - Run `CLAUDE_CLI_QPS_Optimization_Analyzer_v2.md`
   - Creates import, analysis, and CLI tools
   - Test with sample BigQuery CSV

2. **Import Full CSV Data**
   ```bash
   python cli/qps_analyzer.py import /path/to/bigquery_export.csv
   ```

3. **Generate First Size Coverage Report**
   ```bash
   python cli/qps_analyzer.py coverage --days 7
   ```

### Short Term (This Week)

4. **Review Size Coverage with AdOps**
   - Analyze match rate
   - Decide on include list strategy
   - Implement manually in UI (one config at a time)

5. **Fix Seat Dropdown (Phase 8.5)**
   - Apply `CODEX_PROMPT_Phase8.5_Seat_Hierarchy.md`

### Medium Term (Next 2 Weeks)

6. **AI Campaign Clustering (Phase 9)**
   - Group 653 creatives into campaigns
   - Use Claude API for intelligent clustering

7. **CSV Automation**
   - Set up scheduled CSV email
   - Investigate BigQuery direct integration

8. **RTB Troubleshooting API Integration**
   - Would provide bid metrics (reached_queries, bids, wins)
   - More granular than CSV data

---

## 📊 Current Metrics

| Metric | Value |
|--------|-------|
| Creatives in DB | 653 |
| Pretargeting Configs | 10 |
| Endpoints | 3 (90K QPS total) |
| Total Daily Budget | ~$17,600 |
| Performance rows | Varies (import pending) |
| Geographies | 51 pre-populated |
| Phases complete | 1-6, 8.1-8.4 |
| Open bugs | 2 (seat dropdown, buyer seats API) |
| Pending prompts | 4 ready to execute |

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

# Creative sizes in your inventory
sqlite3 ~/.rtbcat/rtbcat.db "SELECT width || 'x' || height as size, COUNT(*) FROM creatives WHERE width IS NOT NULL GROUP BY size ORDER BY COUNT(*) DESC;"
```

### QPS Analysis (after implementing)

```bash
cd /home/jen/Documents/rtbcat-platform/creative-intelligence
source venv/bin/activate

# Import CSV
python cli/qps_analyzer.py import /path/to/csv

# Coverage report
python cli/qps_analyzer.py coverage --days 7

# Generate include list
python cli/qps_analyzer.py include-list

# Fraud signals
python cli/qps_analyzer.py fraud --days 14

# Full report
python cli/qps_analyzer.py full-report
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

# Restart backend after changes
sudo systemctl restart rtbcat-api
```

---

## 📞 Context for Next Engineer

### What Jen Does

- Media buyer running RTB campaigns via Google Authorized Buyers
- Has 653+ creatives across potentially multiple seats
- Imports daily CSV reports from Google (BigQuery or UI)
- Needs to reduce QPS waste, identify fraud, optimize spend
- Works with AdOps team who manage pretargeting settings

### Tech Stack

- **Backend:** Python, FastAPI, SQLite
- **Frontend:** Next.js 14, React, TypeScript, Tailwind
- **AI:** Claude API for clustering (Phase 9)
- **Infrastructure:** Ubuntu, systemd, Zorin OS
- **APIs:** Google Real-time Bidding API, BigQuery

### Working Style

- Uses Claude CLI and Claude in VSCode for development
- Prefers forgiving systems (import everything, flag issues)
- Values domain expertise being captured in docs
- All pretargeting changes require human review (printouts first)
- Sensitive to live bidding impact - no auto-apply

### Key Domain Terms

| Term | Meaning |
|------|---------|
| RTB | Real-Time Bidding - auction for ad impressions |
| QPS | Queries Per Second - bid requests received |
| Pretargeting | Filters that determine which bid requests you receive |
| Billing ID | Identifier for a pretargeting config |
| Creative | An ad (image, video, native) |
| Seat | A bidding entity within a buyer account |
| VAST | Video Ad Serving Template - video ad standard |
| CPM | Cost Per Mille (per 1000 impressions) |
| CTR | Click-Through Rate |

---

## 🎉 Version History

### v9.0 - December 1, 2025 (Current)
- ✅ QPS Optimization system fully designed
- ✅ All 10 pretargeting configs documented with Billing IDs
- ✅ 3 endpoints documented (90K QPS total capacity)
- ✅ API access verified (Creatives, Pretargeting working)
- ✅ Pretargeting logic documented (AND/OR, INCLUDE-only sizes)
- ✅ Fraud detection limitations documented (VPNs, smart fraud)
- 📝 Created comprehensive Claude CLI prompts for implementation

### v8.0 - December 1, 2025
- ✅ Schema audit complete (documented ACTUAL schema)
- ✅ UPSERT logic fixed (prevents duplicate imports)
- ✅ Forgiving CSV validator (never blocks, flags anomalies)
- ✅ Fraud signals reference created
- ✅ Backend validation mismatch fixed

### v7.0 - November 30, 2025
- ✅ Phase 8.2: Performance UI complete
- ✅ Systemd service configured
- 🔄 Phase 8.3: CSV import UI created

### Earlier versions
- Phases 1-6 complete
- 653 creatives collected
- Core platform established

---

## 🚀 Ready to Continue

**Priority order:**
1. Implement QPS Optimization Analyzer (main feature)
2. Import real CSV data and generate reports
3. Review with AdOps, decide on size filtering strategy
4. Fix seat dropdown (UI polish)
5. Implement AI clustering (major feature)

**All prompts are ready. Start with `CLAUDE_CLI_QPS_Optimization_Analyzer_v2.md`!**

---

**End of Handover Document v9**

*Last updated: December 1, 2025*  
*Next update: After QPS Optimization Analyzer implementation*

---

**Developer:** Jen (jen@rtb.cat)  
**Project:** RTB.cat Creative Intelligence  
**Repository:** /home/jen/Documents/rtbcat-platform/  
**Status:** 🚀 READY FOR QPS OPTIMIZATION IMPLEMENTATION
