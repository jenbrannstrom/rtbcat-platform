# Cat-Scan Handover v21

**Date:** December 3, 2025  
**Status:** Phase 21 - UI Polish (In Progress)  
**Purpose:** Complete project context for continuation in new chat

---

## Quick Start for New Chat

```
You are continuing work on Cat-Scan, a privacy-first QPS optimization platform 
for Google Authorized Buyers. 

Key files to read:
- README.md (project overview)
- INSTALL.md (installation guide)
- CHANGELOG.md (version history)
- This handover document

Current state: Core platform working. Onboarding, creative sync, and CSV import functional.
Database: ~/.catscan/catscan.db (SQLite)
Project paths:
  - Backend: ~/Documents/rtbcat-platform/creative-intelligence
  - Frontend: ~/Documents/rtbcat-platform/dashboard
```

---

## What is Cat-Scan?

A **free tool** for DSPs and performance bidders distributed as a marketing trojan horse to gain introductions and establish trust as RTB experts. Must be:
- **Professional quality** - production-ready
- **Easy to install** - minimal setup  
- **Privacy-first** - runs entirely on user's infrastructure (no cloud dependencies)

### Core Value Proposition

Helps users eliminate 20-40% of wasted QPS by identifying:
1. **Size mismatch** - Receiving bid requests for sizes you have no creatives for
2. **Config inefficiency** - Pretargeting configs with poor performance
3. **Fraud signals** - Suspicious patterns for human review

---

## Current State (v21)

### What's Working

| Feature | Status | Notes |
|---------|--------|-------|
| Installation | ✅ | INSTALL.md + setup.sh |
| Google API connection | ✅ | /connect wizard |
| Buyer seat discovery | ✅ | Single seat: "Tuky Display" |
| Creative sync | ✅ | 655 creatives (7 HTML, 50 Native, 598 Video) |
| CSV import | ✅ | Simplified, unified import |
| Creatives page | ✅ | Grid view with format filters |
| Dashboard stats | ✅ | Shows creative counts |
| Thumbnail generation | 🔄 | API exists, UI button being added (Phase 21) |

### What Needs Work

| Feature | Status | Notes |
|---------|--------|-------|
| Campaigns/Clustering | ❓ | "0 creatives" dropdown bug reported earlier |
| Waste analysis | ❓ | Needs rtb_daily data from CSV import |
| Evaluation engine | ❓ | Untested with real data |
| HTML report export | ❌ | Not built yet |

---

## Architecture

### Directory Structure

```
rtbcat-platform/
├── creative-intelligence/     # Python backend
│   ├── api/                   # FastAPI routes
│   │   ├── main.py           # Main app + endpoints
│   │   └── routes/           # Route modules
│   ├── collectors/           # Google API clients
│   │   ├── creatives/        # CreativesClient
│   │   ├── seats.py          # BuyerSeatsClient
│   │   ├── troubleshooting/  # TroubleshootingClient
│   │   └── pretargeting/     # PretargetingClient
│   ├── storage/              # Database layer
│   │   └── sqlite_store.py   # SQLite operations
│   ├── analysis/             # Business logic
│   │   └── evaluation_engine.py
│   ├── cli/                  # Command-line tools
│   │   └── qps_analyzer.py
│   └── config.py             # Configuration management
│
├── dashboard/                 # Next.js frontend
│   ├── src/app/              # Pages (App Router)
│   │   ├── page.tsx          # Dashboard home
│   │   ├── connect/          # Onboarding wizard
│   │   ├── creatives/        # Creative grid
│   │   ├── campaigns/        # Campaign management
│   │   ├── import/           # CSV import
│   │   └── settings/         # System settings
│   ├── src/components/       # Shared components
│   └── src/lib/              # API client, utilities
│
├── INSTALL.md                # Installation guide
├── README.md                 # Project overview
├── CHANGELOG.md              # Version history
└── setup.sh                  # One-command setup
```

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    Google Authorized Buyers                  │
└─────────────────────┬───────────────────────┬───────────────┘
                      │                       │
              RTB API (creatives)      CSV Export (performance)
                      │                       │
                      ▼                       ▼
              ┌───────────────┐       ┌───────────────┐
              │   creatives   │       │   rtb_daily   │
              │    table      │       │    table      │
              └───────┬───────┘       └───────┬───────┘
                      │                       │
                      └───────────┬───────────┘
                                  │
                          creative_id (key)
                                  │
                                  ▼
                      ┌───────────────────────┐
                      │   Waste Analysis      │
                      │   - Size coverage     │
                      │   - Config efficiency │
                      │   - Fraud signals     │
                      └───────────────────────┘
```

---

## Database Schema

### Main Fact Table: `rtb_daily`

**Note:** This was renamed from `performance_data` in Phase 12 to eliminate confusion.

```sql
-- Core identity (all required for import)
metric_date DATE NOT NULL
creative_id TEXT NOT NULL      -- Links to creatives table
billing_id TEXT NOT NULL       -- Pretargeting config identifier
creative_size TEXT NOT NULL    -- "300x250", "Interstitial", etc.

-- Core metrics (required)
reached_queries INTEGER        -- THE critical waste metric (QPS received)
impressions INTEGER            -- Wins / successful bids

-- Optional dimensions (imported if present in CSV)
creative_format TEXT
country TEXT
platform TEXT
environment TEXT
app_id TEXT
app_name TEXT
publisher_id TEXT
publisher_name TEXT
publisher_domain TEXT
advertiser TEXT
buyer_account_id TEXT
buyer_account_name TEXT

-- Optional metrics
clicks INTEGER
spend_micros INTEGER
video_starts, video_completions, vast_errors INTEGER
-- Plus conversion fields from Phase 13

-- Deduplication
row_hash TEXT UNIQUE

-- Tracking
import_batch_id TEXT
imported_at TIMESTAMP
```

### Supporting Tables

| Table | Purpose |
|-------|---------|
| `creatives` | Synced from Google RTB API (~650 rows) |
| `buyer_seats` | Discovered buyer accounts |
| `campaigns` | User-defined groupings (formerly ai_campaigns) |
| `creative_campaigns` | Junction table |
| `thumbnail_status` | Track thumbnail generation |
| `fraud_signals` | Detected patterns for review |
| `import_history` | Track CSV imports |
| `troubleshooting_data` | RTB troubleshooting API data |
| `troubleshooting_collections` | Troubleshooting runs |

---

## Google API Integration

### Key Discovery (Phase 15)

The Real-Time Bidding API structure:

```python
# CORRECT - buyers() is at root level
service.buyers().list()  # Lists buyer seats
service.buyers().get(name=f"buyers/{buyer_id}")

# WRONG - this doesn't exist
service.bidders().buyers().list()  # AttributeError!

# Creatives are under bidders
service.bidders().creatives().list(parent=f"bidders/{bidder_id}")
```

### Clients

| Client | Location | Purpose |
|--------|----------|---------|
| `CreativesClient` | `collectors/creatives/client.py` | Sync creatives |
| `BuyerSeatsClient` | `collectors/seats.py` | Discover buyer seats |
| `TroubleshootingClient` | `collectors/troubleshooting/client.py` | Troubleshooting API |
| `PretargetingClient` | `collectors/pretargeting/` | Pretargeting configs |

### Current Account

- **Bidder ID:** 299038253
- **Buyer ID:** 299038253 (same - single-seat account)
- **Display Name:** "Tuky Display"
- **Creatives:** 655 (7 HTML, 50 Native, 598 Video)

---

## Running the Application

### Quick Start

```bash
# Terminal 1: API
cd ~/Documents/rtbcat-platform/creative-intelligence
source venv/bin/activate
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Dashboard
cd ~/Documents/rtbcat-platform/dashboard
npm run dev
```

### As a Service

```bash
# Start/stop API service
sudo systemctl start rtbcat-api
sudo systemctl stop rtbcat-api
sudo systemctl status rtbcat-api

# View logs
sudo journalctl -u rtbcat-api -f
```

### URLs

- Dashboard: http://localhost:3000
- API: http://localhost:8000
- API Health: http://localhost:8000/health
- API Docs: http://localhost:8000/docs

---

## CLI Commands

```bash
cd ~/Documents/rtbcat-platform/creative-intelligence
source venv/bin/activate

# CSV operations
python cli/qps_analyzer.py validate /path/to/file.csv
python cli/qps_analyzer.py import /path/to/file.csv

# Analysis
python cli/qps_analyzer.py summary
python cli/qps_analyzer.py coverage --days 7
python cli/qps_analyzer.py configs --days 7
python cli/qps_analyzer.py fraud --days 14
python cli/qps_analyzer.py full-report --days 7
```

---

## CSV Import Requirements

### Export from Google Authorized Buyers

Users create ONE scheduled report with:
- **ALL dimensions** (Creative ID is the key)
- **ALL metrics** (we want everything)
- **Daily schedule** (yesterday's data)

### Required Columns

| Column | Maps To | Purpose |
|--------|---------|---------|
| Day / #Day | metric_date | Time dimension |
| Creative ID / #Creative ID | creative_id | **THE KEY** - links to inventory |
| Billing ID | billing_id | Pretargeting config |
| Creative size | creative_size | Size coverage analysis |
| Reached queries | reached_queries | **THE WASTE METRIC** |
| Impressions | impressions | Basic performance |

### If File Too Large

Split by DATE only (never by metrics). Each file must contain all dimensions and all metrics for its date range. Upload separately - Cat-Scan merges using creative_id as key.

---

## Critical Domain Knowledge

### Size Filtering is INCLUDE-ONLY

Google's pretargeting size filter is INCLUDE-ONLY:
- Empty size list = Accept ALL sizes
- Add ONE size = ONLY that size (all others EXCLUDED)
- NO "exclude" option exists

### Format Naming

| API Value | UI Display | Notes |
|-----------|------------|-------|
| HTML | Display | Renamed for clarity |
| IMAGE | Display | Same category as HTML |
| VIDEO | Video | |
| NATIVE | Native | |

### Thumbnails

- Generated by Cat-Scan using ffmpeg
- **Not visible to end users** - internal preview only
- Requires ffmpeg installed (`sudo apt install ffmpeg`)
- Some videos may fail (expired URLs, access denied)

### Fraud Detection Approach

Cat-Scan FLAGS patterns for human review. Does NOT definitively identify fraud.

**Key Principle:** Patterns over time matter, not single anomalies.

---

## Recent Phase History

| Phase | Date | Summary |
|-------|------|---------|
| 11 | Dec 3 | RTB Troubleshooting API, evaluation engine |
| 12 | Dec 3 | Schema cleanup: performance_data → rtb_daily |
| 13 | Dec 3 | Additional fields, fresh DB install |
| 14 | Dec 3 | Fix onboarding flow (/connect wizard) |
| 15 | Dec 3 | Debug buyer seats (buyers() at root level) |
| 16 | Dec 3 | Fix bidder ID bug in sync |
| 17 | Dec 3 | Fix /creatives 500 error, remove advanced sync options |
| 18 | Dec 3 | Thumbnail generation, IMAGE → Display rename |
| 19 | Dec 3 | INSTALL.md, setup.sh, system requirements |
| 20 | Dec 3 | Simplify CSV import (remove type selection) |
| 21 | Dec 3 | UI polish - thumbnail button on /creatives, tooltips |

---

## Known Issues & Next Steps

### Open Issues

| Issue | Priority | Notes |
|-------|----------|-------|
| Campaigns "0 creatives" dropdown | Medium | Reported but not investigated |
| Waste analysis untested | High | Needs CSV data in rtb_daily |

### Suggested Next Phases

| Phase | Focus | Value |
|-------|-------|-------|
| 22 | Test waste analysis with real data | Core feature validation |
| 23 | Fix campaigns/clustering | UI completeness |
| 24 | Port cat-scan analytics | Tolerance-based sizes, problem format detection |
| 25 | HTML report generation | Shareable reports for clients |

### Features from Legacy cat-scan to Port

From earlier analysis:

1. **Tolerance-based size normalization** (P1) - Map 298x250 → 300x250
2. **Problem format detection** (P2) - zero_bids, non_standard, low_bid_rate
3. **Publisher/SSP breakdown** (P3) - Per-publisher waste analysis
4. **Interactive HTML report** (P4) - Self-contained shareable reports
5. **Time-based trend analysis** (P5) - Bid rate trends over time

---

## File Locations

### User Data

```
~/.catscan/
├── catscan.db                 # SQLite database
├── thumbnails/                # Generated video thumbnails
└── credentials/               # Google service account JSON

~/.rtb-cat/credentials/        # Alternative credentials location
```

### Configuration

- Credentials: `~/.rtb-cat/credentials/google-credentials.json`
- Config: Stored encrypted alongside credentials

### Logs

```bash
# API logs (if running as service)
sudo journalctl -u rtbcat-api -f

# Dashboard logs
# Check terminal running npm run dev
```

---

## Testing Checklist for New Engineer

### Verify Current State

```bash
# 1. Check API health
curl http://localhost:8000/health

# 2. Check database
sqlite3 ~/.catscan/catscan.db "SELECT COUNT(*) FROM creatives"
# Should return: 655

# 3. Check seats
curl http://localhost:8000/api/seats
# Should return: 1 seat "Tuky Display"

# 4. Check creatives endpoint
curl http://localhost:8000/api/creatives | python -m json.tool | head -50
```

### Test Key Flows

1. **Fresh install** - Does setup.sh work on clean system?
2. **Onboarding** - /connect wizard completes?
3. **CSV import** - Upload a real CSV, does it import?
4. **Waste analysis** - After import, does analysis show data?
5. **Thumbnails** - Does generation work with ffmpeg installed?

---

## Contact & Resources

- **GitHub:** (internal repo)
- **Google RTB API Docs:** https://developers.google.com/authorized-buyers/apis/realtimebidding/reference/rest/v1
- **Authorized Buyers UI:** https://authorized-buyers.google.com/

---

**Version:** 21.0  
**Last Updated:** December 3, 2025  
**Author:** Development Team
