# RTBcat: QPS Optimizer & Creative Intelligence Platform

**Privacy-First Campaign Performance Intelligence for Bidders & DSPs**

> Your data. Your infrastructure. Provably private.

**Status:** Phase 8.4 ✅ Complete | Phase 9-10 📋 Designed & Ready to Implement

---

## What is RTBcat?

RTBcat is a **privacy-first platform** for DSPs and performance bidders to:

1. **Optimize QPS** - Eliminate 20-40% of unprofitable bid requests
2. **Analyze creatives** - Fetch and classify creatives from Google Authorized Buyers
3. **Track performance** - Import spend, clicks, impressions by creative/geo/device
4. **Detect fraud signals** - Flag suspicious traffic patterns for human review
5. **Find opportunities** - Discover undervalued geos, neglected campaigns, size gaps
6. **Run privately** - Everything runs in YOUR infrastructure

---

## Current State

### ✅ Implemented & Working

| Component | Status | Details |
|-----------|--------|---------|
| Creative Collection | ✅ Working | 653 creatives synced from Google API |
| Performance Import | ✅ Working | CSV import with forgiving validation |
| Dashboard UI | ✅ Working | Next.js 14, creative browser, import page |
| Backend API | ✅ Working | FastAPI, systemd service |
| Google API Integration | ✅ Working | Creatives API, Pretargeting API |
| Database | ✅ Working | SQLite, 653 creatives stored |

### 📋 Designed & Ready to Implement

| Component | Status | Prompt Ready |
|-----------|--------|--------------|
| QPS Optimization Analyzer | 📋 Designed | `CLAUDE_CLI_QPS_Optimization_Analyzer_v2.md` |
| AI Campaign Clustering | 📋 Designed | `CODEX_PROMPT_Phase9_AI_Clustering.md` |
| Seat Hierarchy Fix | 📋 Designed | `CODEX_PROMPT_Phase8.5_Seat_Hierarchy.md` |

### 🐛 Known Issues

| Bug | Status |
|-----|--------|
| Seat dropdown shows 0 creatives | Open |
| Buyer Seats API AttributeError | Open |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    YOUR INFRASTRUCTURE                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │   Creative Intelligence Backend (Python FastAPI)         │    │
│  │   • Google Authorized Buyers API integration            │    │
│  │   • Performance data import (CSV)                       │    │
│  │   • QPS optimization analysis (designed, not impl.)     │    │
│  │   • Fraud signal detection (designed, not impl.)        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                           │                                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │   Web Dashboard (Next.js 14)                             │    │
│  │   • Creative browser with performance metrics           │    │
│  │   • CSV import with drag/drop                           │    │
│  │   • Performance data visualization                      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                           │                                      │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │   Database (SQLite)                                      │    │
│  │   • 653 creatives                                       │    │
│  │   • Performance metrics                                 │    │
│  │   • 10 pretargeting configs documented                  │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                ┌──────────────────────────┐
                │  Google Authorized       │
                │  Buyers RTB API v1       │
                └──────────────────────────┘
```

---

## QPS Optimization System (DESIGNED - NOT YET IMPLEMENTED)

> **Note:** This system is fully designed with Claude CLI prompts ready. Run `CLAUDE_CLI_QPS_Optimization_Analyzer_v2.md` to implement.

### The Problem

```
┌─────────────────────────────────────────────────────────────────┐
│                    THE PROFIT FUNNEL                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  REACHED QUERIES (QPS from Google)                              │
│         │                                                        │
│         ▼                                                        │
│  ┌─────────────┐     ┌────────────────────────────────────┐     │
│  │ CAN YOU BID?│────►│ NO: Wrong size, no creative        │     │
│  └──────┬──────┘     │     = TRUE WASTE (block these!)    │     │
│         │ YES        └────────────────────────────────────┘     │
│         ▼                                                        │
│  ┌─────────────┐     ┌────────────────────────────────────┐     │
│  │ AUCTION WON?│────►│ NO: Outbid = normal competition    │     │
│  └──────┬──────┘     └────────────────────────────────────┘     │
│         │ YES                                                    │
│         ▼                                                        │
│  ┌─────────────┐                                                │
│  │ IMPRESSION  │──► Delivered, may or may not convert           │
│  └─────────────┘                                                │
│                                                                  │
│  KEY INSIGHT: Only size mismatch is TRUE waste.                 │
│  Everything else is competition or cost of business.            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Critical Domain Knowledge

#### Pretargeting Size Filtering (IMPORTANT!)

```
┌─────────────────────────────────────────────────────────────────┐
│                    SIZE FILTERING RULES                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ⚠️  SIZE FILTERING IS INCLUDE-ONLY                             │
│                                                                  │
│  • Leave size list BLANK = Accept ALL sizes                     │
│  • Add ONE size = ONLY that size (all others EXCLUDED)          │
│  • Add MULTIPLE sizes = Those sizes accepted (OR within list)   │
│                                                                  │
│  There is NO "exclude" option!                                  │
│                                                                  │
│  PRETARGETING LOGIC:                                            │
│  • All settings use AND with each other                         │
│  • Exception: Web/App use OR with each other                    │
│  • Exception: Sizes within a list use OR with each other        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### Fraud Detection Limitations

```
┌─────────────────────────────────────────────────────────────────┐
│                    FRAUD DETECTION REALITY                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  What RTBcat CAN detect:                                        │
│  • Statistical anomalies over time                              │
│  • Apps with suspicious CTR patterns                            │
│  • Clicks exceeding impressions repeatedly                      │
│                                                                  │
│  What RTBcat CANNOT reliably detect:                            │
│  • Geographic anomalies (VPNs are everywhere)                   │
│  • Smart fraud (mixes 70-80% real with 20-30% fake)            │
│  • Single-occurrence oddities (need patterns)                   │
│                                                                  │
│  RTBcat's job: FLAG patterns for human review                   │
│  NOT: Definitively identify fraud                               │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Your 10 Pretargeting Configs

| # | Billing ID | Name | Geos | QPS Cap |
|---|------------|------|------|---------|
| 1 | 72245759413 | Africa/Asia | BF,BR,CI,CM,EG,NG,SA,SE,IN,PH,KZ | 50K |
| 2 | 83435423204 | ID/BR Android | ID,BR,IN,US,KR,ZA,AR | 50K |
| 3 | 104602012074 | MENA iOS&AND | SA,AE,EG,PH,IT,ES,BF,KZ,FR,PE,ZA,HU,SK | 50K |
| 4 | 137175951277 | SEA Whitelist | BR,ID,MY,TH,VN | 30K |
| 5 | 151274651962 | USEast CA/MX | CA,MX | 5K |
| 6 | 153322387893 | Brazil AND | BR | 30K |
| 7 | 155546863666 | Asia BL2003 | ID,IN,TH,CN,KR,TR,VN,BD,PH,MY | 50K |
| 8 | 156494841242 | Nova WL | ? | 30K |
| 9 | 157331516553 | US/Global | US,PH,AU,KR,EG,PK,BD,UZ,SA,JP,PE,ZA,HU,SK,AR,KW | 50K |
| 10 | 158323666240 | BR/PH Spotify | BR,PH | 30K |

**Total Pretargeting QPS Cap:** 375K  
**Actual Endpoint Limit:** 90K (this is the real bottleneck)

### Endpoint Configuration

| Location | URL | QPS Limit |
|----------|-----|-----------|
| US West | bidder.novabeyond.com | 10,000 |
| Asia | bidder-sg.novabeyond.com | 30,000 |
| US East | bidder-us.novabeyond.com | 50,000 |

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- Google Service Account with Authorized Buyers API access

### Backend Setup

```bash
cd creative-intelligence
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Start API server
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Setup

```bash
cd dashboard
npm install
npm run dev
```

### Access Points

- **Dashboard:** http://localhost:3000
- **API Docs:** http://localhost:8000/docs
- **API Health:** http://localhost:8000/health

### Systemd Service (Production)

```bash
# Status
sudo systemctl status rtbcat-api

# Restart after code changes
sudo systemctl restart rtbcat-api

# Logs
sudo journalctl -u rtbcat-api -f
```

---

## API Endpoints (Currently Implemented)

### Creatives

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/creatives` | List all creatives with filters |
| GET | `/creatives/{id}` | Get creative details |
| POST | `/collect/sync` | Sync creatives from Google API |

### Performance

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/performance/import` | Import performance metrics (JSON) |
| POST | `/performance/import-csv` | Import performance CSV |
| GET | `/performance/metrics/batch` | Get batch metrics |

### Seats

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/seats` | List buyer seats |
| POST | `/seats/discover` | Discover seats from Google API |
| POST | `/seats/{buyer_id}/sync` | Sync creatives for seat |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | API health check |

> **Note:** QPS optimization endpoints (`/qps/*`) are designed but not yet implemented. See Claude CLI prompts.

---

## Google API Configuration

### Current Setup

| Configuration | Value |
|--------------|-------|
| Credentials Path | `~/.rtb-cat/credentials/google-credentials.json` |
| Service Account | `rtb-cat-collector@creative-intel-api.iam.gserviceaccount.com` |
| Google Cloud Project | `creative-intel-api` |
| Bidder Account ID | `299038253` |
| Account Name | Tuky Data Research Ltd. |

### APIs Status

| API | Status |
|-----|--------|
| Real-time Bidding API v1 | ✅ Working |
| Creatives API | ✅ Working (653 creatives) |
| Pretargeting API | ✅ Working (10 configs) |
| Buyer Seats API | ❌ Error (AttributeError) |

### Testing API Access

```bash
cd creative-intelligence
source venv/bin/activate
python scripts/test_api_access.py
```

---

## Database Schema

### Current Tables (Implemented)

```sql
-- Creatives (653 rows)
creatives (
    id TEXT PRIMARY KEY,  -- Note: TEXT not INTEGER
    name, format, account_id, buyer_id,
    width, height, canonical_size, size_category,
    approval_status, final_url, advertiser_name
)

-- Performance metrics
performance_metrics (
    creative_id, metric_date, impressions, clicks,
    spend_micros, geography, device_type, placement,
    billing_account_id
)

-- Import anomalies (fraud signals)
import_anomalies (
    id, creative_id, anomaly_type, severity,
    message, raw_data, detected_at
)

-- Geographies (51 pre-populated)
geographies (code, name, region, is_active)

-- Apps, Publishers
apps, publishers
```

### Tables To Be Created (After Running Prompts)

```sql
-- Pretargeting configs (after QPS prompt)
pretargeting_configs (billing_id, name, geos, budget_daily, qps_limit)

-- Size metrics daily (after QPS prompt)
size_metrics_daily (metric_date, billing_id, creative_size, reached_queries, ...)

-- Fraud signals (after QPS prompt)
fraud_signals (app_id, signal_type, signal_strength, evidence, status)

-- AI campaigns (after Phase 9 prompt)
ai_campaigns (id, name, description, creative_ids, confidence_score)
```

---

## Project Structure

```
rtbcat-platform/
├── creative-intelligence/          # Python backend
│   ├── api/                        # FastAPI application
│   │   ├── main.py                 # API endpoints
│   │   └── performance.py          # Performance endpoints
│   ├── collectors/                 # Google API clients
│   │   ├── base.py                 # Base client with auth
│   │   ├── creatives/              # Creatives client
│   │   ├── pretargeting/           # Pretargeting client
│   │   └── seats.py                # Buyer seats client
│   ├── storage/                    # Database layer
│   │   └── sqlite_store.py         # SQLite backend
│   ├── scripts/                    # CLI tools
│   │   └── test_api_access.py      # API verification
│   └── config/                     # Configuration
│       └── config_manager.py       # Encrypted config
│
├── dashboard/                      # Next.js 14 frontend
│   ├── src/
│   │   ├── app/                    # Pages (import, creatives, etc.)
│   │   ├── components/             # React components
│   │   └── lib/                    # API client, validators
│   └── package.json
│
└── docs/                           # Documentation
    ├── RTBcat_Handover_v9.md       # Full handover doc
    └── CLAUDE_CLI_*.md             # Implementation prompts
```

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.12, FastAPI, asyncio |
| Database | SQLite |
| Frontend | Next.js 14, React, Tailwind CSS |
| AI (planned) | Claude (Anthropic) |
| Charts | Recharts |
| Data Fetching | TanStack React Query |
| Google APIs | google-api-python-client, google-auth |

---

## Phase Status

### Complete ✅

| Phase | Feature |
|-------|---------|
| 1-6 | Creative Management, Dashboard, Smart URLs |
| 8.1 | Backend Performance API |
| 8.2 | Performance UI (sort, badges, tier filter) |
| 8.3 | CSV Import UI (drag/drop, preview, validation) |
| 8.4 | Large Files & Schema Fix (UPSERT, normalization) |

### Ready to Implement 📋

| Phase | Feature | Prompt File |
|-------|---------|-------------|
| 8.5 | Seat Hierarchy Fix | `CODEX_PROMPT_Phase8.5_Seat_Hierarchy.md` |
| 9 | AI Campaign Clustering | `CODEX_PROMPT_Phase9_AI_Clustering.md` |
| 9.5 | QPS Optimization | `CLAUDE_CLI_QPS_Optimization_Analyzer_v2.md` |

### Planned 📝

| Phase | Feature |
|-------|---------|
| 10 | Thumbnail Generation |
| 11 | Opportunity Intelligence |

---

## CSV Import Format

### Performance Metrics (BigQuery Export)

The importer handles Google's BigQuery CSV format with 46 columns including:

| Column | Description |
|--------|-------------|
| `#Day` | Date (MM/DD/YYYY) |
| `Creative ID` | Maps to creative_id |
| `Billing ID` | Maps to pretargeting config |
| `Creative size` | e.g., "300x250", "Video 9:16" |
| `Reached queries` | QPS that matched pretargeting |
| `Impressions` | Successful deliveries |
| `Clicks` | User clicks |
| `Spend _buyer currency_` | Spend in dollars |

---

## Troubleshooting

### "PERMISSION_DENIED" from Google API

1. Verify service account is authorized in Authorized Buyers UI
2. Check Real-time Bidding API is enabled in Google Cloud Console
3. Verify account ID is correct

### Port 8000 already in use

```bash
sudo lsof -ti:8000 | xargs -r sudo kill -9
sudo systemctl restart rtbcat-api
```

### Database errors

```bash
# Check database exists
ls -la ~/.rtbcat/rtbcat.db

# Quick verification
sqlite3 ~/.rtbcat/rtbcat.db "SELECT COUNT(*) FROM creatives;"
# Expected: 653
```

---

## Next Steps for New Engineer

1. **Read the handover doc:** `RTBcat_Handover_v9.md`
2. **Implement QPS Optimization:** Run `CLAUDE_CLI_QPS_Optimization_Analyzer_v2.md`
3. **Import real CSV data** and generate first reports
4. **Fix seat dropdown:** Run `CODEX_PROMPT_Phase8.5_Seat_Hierarchy.md`
5. **Implement AI clustering:** Run `CODEX_PROMPT_Phase9_AI_Clustering.md`

---

## Support

- **Developer:** Jen (jen@rtb.cat)
- **Repository:** `/home/jen/Documents/rtbcat-platform/`
- **Database:** `~/.rtbcat/rtbcat.db`
- **API Docs:** http://localhost:8000/docs

---

**Last Updated:** December 1, 2025  
**Version:** 9.0 (QPS Optimization Designed)  
**Next Milestone:** Implement QPS Optimization Analyzer