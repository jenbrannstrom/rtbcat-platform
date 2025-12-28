# Cat-Scan Handover v11
**Date:** December 6, 2025
**Session:** QPS Waste Analysis Deep Dive & Data Integration

---

## Executive Summary

This session focused on understanding the **real RTB funnel** and discovering that Cat-Scan needs proper **CSV upload/import functionality** rather than hardcoded file paths. Key breakthrough: by joining two CSV exports on `creative_id`, we can see waste per billing_id (pretargeting config) even though Google doesn't allow Bids + Billing ID in the same export.

---

## Key Discoveries

### 1. The Real RTB Funnel

```
Google Offers:     29.5 BILLION bid requests (341K QPS)
                         ↓ 99.92% filtered by pretargeting
Reaches Bidder:        24.8 MILLION (287 QPS)
                         ↓ Bidder bids 7.4x per query
Bids Submitted:       183.5 MILLION
                         ↓ 66% don't convert
IMPRESSIONS WON:        8.4 MILLION
```

**Key insight:** The 99.92% filter rate is pretargeting working correctly. The real waste is the **66%** of reached traffic that doesn't convert to impressions.

### 2. Waste Analysis by Pretargeting Config

By joining the Billing ID CSV and Creative Bids CSV on `creative_id`:

| Billing ID | Format | Geos | Reached | Win% | Waste% |
|------------|--------|------|---------|------|--------|
| 72245759413 | Display+Video | IN, BR, JP | 1.96M | 36.0% | 64.0% |
| 157331516553 | Video | AU, CA, BD | 1.01M | 29.2% | **70.8%** ⚠️ |
| 83435423204 | Video | IN, ID, BR | 398K | 25.2% | **74.8%** ⚠️ |
| 137175951277 | Video | MY, TH, VN | 201 | 2.5% | **97.5%** 🚨 |

### 3. Critical Findings

**Config 137175951277 is catastrophically wasteful:**
- Only 201 reached queries
- 247,186 bids placed (1,230x per query!)
- Only 5 impressions won
- **97.5% waste**

**Video/Overlay size is a major waste source:**
- 954K reached → 181K impressions
- **81% waste** across all configs

### 4. High-Performing Sizes

| Size | Win Rate |
|------|----------|
| 336x280 | 73% |
| 336x300 | 66% |
| 300x250 | 54% |

---

## Technical State

### Project Structure

Two dashboard directories exist (this caused confusion):
- `/home/jen/Documents/rtbcat-platform/dashboard/` ← **Main frontend (port 3000)**
- `/home/jen/Documents/rtbcat-platform/creative-intelligence/dashboard/` ← Old/unused

### Backend

**Location:** `/home/jen/Documents/rtbcat-platform/creative-intelligence/`

**Start command:**
```bash
cd ~/Documents/rtbcat-platform/creative-intelligence
source venv/bin/activate
python -m uvicorn api.main:app --reload --port 8000
```

**Key files modified in this session:**
- `analytics/rtb_funnel_analyzer.py` - Added methods:
  - `parse_billing_config_csv()` (line ~582)
  - `parse_creative_bids_csv()` (line ~636)
  - `parse_publisher_csv()` (line ~680)
  - `join_billing_and_bids()` (line ~730)

- `api/main.py` - Updated endpoint:
  - `GET /analytics/rtb-funnel/configs` (line ~4461) - Now accepts `billing_csv_path` and `bids_csv_path` query params

### Frontend

**Location:** `/home/jen/Documents/rtbcat-platform/dashboard/`

**Start command:**
```bash
cd ~/Documents/rtbcat-platform/dashboard
npm run dev
```

**Key files:**
- `src/app/waste-analysis/page.tsx` - Main waste analysis page
- `src/components/rtb/config-performance.tsx` - Pretargeting config display component (created this session)

### Database

**Location:** `~/.catscan/catscan.db`

**Key tables:**
- `creatives` - 655 rows
- `performance_metrics` - CSV imported data
- `rtb_daily` - RTB metrics (may have limited data)

---

## What Works Now

1. **Backend API** returns data at `GET /analytics/rtb-funnel/configs`
   - Without CSV params: Returns publisher proxy data (20 configs)
   - With CSV params: Returns real billing_id data (7 configs) - but CSVs must exist at specified paths

2. **RTB Funnel view** shows:
   - Reached → Win Rate → Impressions funnel
   - Publisher performance breakdown
   - Geographic performance

3. **CSV parsing** works when files are in place

---

## What Needs To Be Built (Phase 30)

### The Core Problem

Currently, the app expects hardcoded CSV file paths. Users should instead:
1. Upload CSVs through the UI
2. Have data stored in the database
3. See analysis without manual file management

### Required CSV Exports (3 types)

| # | Report Name | Dimensions | Metrics |
|---|-------------|------------|---------|
| 1 | `catscan-billing-config` | Day, Billing ID, Creative ID, Creative size, Creative format | Reached queries, Impressions |
| 2 | `catscan-creative-bids` | Day, Creative ID, Country | Bids, Bids in auction, Reached queries |
| 3 | `catscan-publisher-perf` | Publisher ID, Publisher name | Bid requests, Reached queries, Bids, Successful responses, Impressions |

**Why 3 files?** Google doesn't allow Billing ID + Bids in same export. We join on Creative ID.

### Phase 30 Implementation

```bash
claude "Add a CSV upload feature to Cat-Scan:

1. Backend (api/main.py):
   - POST /analytics/rtb-funnel/upload endpoint that accepts CSV file uploads
   - Detect CSV type from headers (billing config vs creative bids vs publisher)
   - Parse and store in SQLite database tables: rtb_billing_configs, rtb_creative_bids, rtb_publishers
   - Return summary of what was imported

2. Update GET /analytics/rtb-funnel/configs:
   - Read from database tables instead of CSV file paths
   - Join rtb_billing_configs with rtb_creative_bids on creative_id
   - Remove the csv_path query parameters

3. Frontend (dashboard/src/app/waste-analysis/page.tsx):
   - Add an 'Import RTB Data' button that opens a file picker
   - Accept multiple CSV files at once
   - Show upload progress and success/error messages
   - After successful upload, refresh the data

4. Database schema in SQLite:
   - rtb_billing_configs: day, billing_id, creative_id, creative_size, creative_format, reached_queries, impressions
   - rtb_creative_bids: day, creative_id, country, bids, bids_in_auction, reached_queries
   - rtb_publishers: publisher_id, publisher_name, bid_requests, reached_queries, bids, successful_responses, impressions"
```

---

## Files Created This Session

### Output Files

| File | Description |
|------|-------------|
| `CatScan_Phase28v3_BiddingInterest_Analysis_Prompt.md` | Bids per query analysis |
| `CatScan_Phase28v4_WinRate_Analysis_Prompt.md` | Win rate focus (before discovering full funnel) |
| `CatScan_Phase28v5_RealFunnel_Analysis_Prompt.md` | Correct funnel understanding |
| `CatScan_Phase29_MultiView_Waste_Analysis_Prompt.md` | Multi-view with expandable configs |
| `CatScan_Waste_Analysis_Findings.md` | Analysis of real data |
| `CatScan_CSV_Export_Guide.md` | User guide for exporting CSVs from Google |

---

## Commits Made

**Phase 28:** RTB Funnel Analysis
- RTBFunnelAnalyzer class
- API endpoints: /analytics/rtb-funnel, /rtb-funnel/publishers, /rtb-funnel/geos
- FunnelCard component

**Phase 29:** Multi-view waste analysis (partial)
- CSV parsing methods added to RTBFunnelAnalyzer
- /analytics/rtb-funnel/configs endpoint updated with CSV params
- ConfigPerformanceSection component created

---

## Known Issues

1. **Two dashboard directories** - Confusion about which is active. Main one is `/dashboard/`, not `/creative-intelligence/dashboard/`

2. **CSV files not persisted** - Must be manually placed in `docs/` folder. Need proper upload feature.

3. **Component may not render** - ConfigPerformanceSection was added but may have import issues. Check browser console for errors.

4. **Claude CLI memory issues** - Gets "Killed" when exploring large codebases. Use focused, single-task prompts instead.

---

## Quick Start for Next Session

```bash
# 1. Start backend
cd ~/Documents/rtbcat-platform/creative-intelligence
source venv/bin/activate
python -m uvicorn api.main:app --reload --port 8000

# 2. Start frontend
cd ~/Documents/rtbcat-platform/dashboard
npm run dev

# 3. Copy CSVs if testing with real data
cp ~/Downloads/cat-scan-*.csv ~/Documents/rtbcat-platform/creative-intelligence/docs/

# 4. Test backend
curl "http://localhost:8000/analytics/rtb-funnel/configs" | python3 -m json.tool | head -50

# 5. Open browser
open http://localhost:3000/waste-analysis
```

---

## Context for Claude CLI

When using Claude CLI, prefer focused single-task prompts to avoid memory kills:

**Good:**
```bash
claude "In api/main.py, add method X that does Y"
```

**Bad:**
```bash
claude "Explore the codebase and implement feature X with all components"
```

---

## Priority Next Steps

1. **Implement Phase 30** - CSV upload to database (eliminates file path dependency)
2. **Fix ConfigPerformanceSection rendering** - Debug why it may not show
3. **Add expandable size breakdown** - Show per-size win rates within each billing_id config
4. **Creative win performance view** - Win rate metrics, not CTR

---

## Key Mental Model Corrections

| Wrong | Right |
|-------|-------|
| "Utilization > 100%" | Multiple impressions per query (video ad pods) |
| "99.92% waste" | That's pretargeting filtering - by design |
| "Optimize CTR" | That's media buyer's job, not Cat-Scan's |
| "Bid rate = efficiency" | Win rate on reached traffic = real efficiency |
| "All QPS is equal" | Different billing_ids have different purposes |

---

## Data Files Used

| File | Columns | Purpose |
|------|---------|---------|
| `cat-scan-Billingid-reached.csv` | Day, Billing ID, Creative ID, Creative size, Creative format, Reached queries, Impressions | Config → Size mapping |
| `cat-scan-criD-bids-reached.csv` | Day, Creative ID, Country, Bids, Bids in auction, Reached queries | Bidding activity per creative |
| `Bids-per-Pub.csv` | Publisher ID, Publisher name, Bid requests, Reached queries, Bids, Impressions | Publisher funnel |
| `ADX_bidding_metrics_Yesterday__2_.csv` | Creative ID, Country, Bids, Reached queries, Bids in auction, Auctions won | Creative bidding detail |

---

## End of Handover v11
