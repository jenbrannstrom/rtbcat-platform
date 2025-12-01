# Cat-Scan: QPS Optimizer & Creative Intelligence Platform

**Privacy-First Campaign Performance Intelligence for Bidders & DSPs**

> Your data stays on your infrastructure. Always.

**Status:** Phase 9.6 ✅ Unified Data Architecture Complete  
**Version:** 10.2  
**Last Updated:** December 1, 2025

---

## What is Cat-Scan?

Cat-Scan is a **free, professional-grade tool** for DSPs and performance bidders to:

1. **Optimize QPS** - Eliminate 20-40% of wasted bid requests
2. **Analyze creatives** - Sync and track creatives via Google RTB API
3. **Track performance** - Import CSV data with strict validation
4. **Detect fraud signals** - Flag suspicious patterns for human review
5. **Run privately** - Everything runs on YOUR infrastructure

---

## Quick Start

### Prerequisites

- Python 3.12+
- Node.js 18+
- Google Service Account with Authorized Buyers API access

### Starting Services

```bash
# 1. Check API is running (systemd service)
sudo systemctl status catscan-api
curl http://localhost:8000/health

# 2. Start dashboard (manual)
cd dashboard
npm run dev
# Dashboard at http://localhost:3000
```

### Import Data

**Option 1: CLI (recommended for large files)**
```bash
cd creative-intelligence
source venv/bin/activate

python cli/qps_analyzer.py validate /path/to/export.csv
python cli/qps_analyzer.py import /path/to/export.csv
python cli/qps_analyzer.py full-report --days 7
```

**Option 2: Dashboard UI**
1. Go to http://localhost:3000/import
2. Drag and drop your CSV
3. Supports chunked uploads for large files (100MB+)

---

## CSV Export Requirements

Cat-Scan requires specific columns from your Authorized Buyers export. The importer will **reject** files missing required columns and show exactly how to fix it.

### Required Columns

| Column | Why Required |
|--------|--------------|
| **Day** | Time dimension for analysis |
| **Creative ID** | Links to your creative inventory |
| **Billing ID** | Identifies pretargeting config |
| **Creative size** | QPS coverage analysis |
| **Reached queries** | THE critical waste metric |
| **Impressions** | Basic performance |

### How to Configure Your Export

```
In Authorized Buyers:

1. Go to Reports → Create Report

2. Under DIMENSIONS, add:
   • Day (under Time dimensions)
   • Creative ID (under Demand dimensions)
   • Billing ID (under Demand dimensions)
   • Creative size (under Demand dimensions)
   
   Optional but recommended:
   • Country
   • Mobile app ID / Mobile app name
   • Platform
   • Environment (App/Web)

3. Under METRICS, add:
   • Reached queries (CRITICAL!)
   • Impressions
   • Clicks
   • Spend (buyer currency)
   
   Optional:
   • Video starts, Video completions
   • Active view measurable/viewable
   • VAST error count

4. Click "Run Report" → Download as CSV

5. Import via CLI or dashboard
```

### What Happens If Columns Are Missing

```
❌ VALIDATION FAILED

Error: Missing required columns: reached_queries, billing_id

============================================================
HOW TO FIX YOUR CSV EXPORT
============================================================

In Authorized Buyers, go to Reports → Create Report

1. Under DIMENSIONS, add:
   • Billing ID

2. Under METRICS, add:
   • Reached queries

3. Click 'Run Report' and download as CSV
============================================================
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    YOUR INFRASTRUCTURE                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌─────────────────────────────────────────────────────────┐│
│  │   QPS Optimization Module (Python)                      ││
│  │   • CSV Validator (strict requirements)                 ││
│  │   • Raw data storage (no aggregation at import)         ││
│  │   • Size coverage analysis                              ││
│  │   • Config performance tracking                         ││
│  │   • Fraud signal detection                              ││
│  └─────────────────────────────────────────────────────────┘│
│                           │                                  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │   Backend API (FastAPI, port 8000)                      ││
│  │   • /qps/* endpoints for reports                        ││
│  │   • /creatives/* for creative data                      ││
│  │   • /performance/import-csv for uploads                 ││
│  │   • Systemd service                                     ││
│  └─────────────────────────────────────────────────────────┘│
│                           │                                  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │   Dashboard (Next.js, port 3000)                        ││
│  │   • Creative browser                                    ││
│  │   • CSV import interface (chunked upload support)       ││
│  │   • Performance visualization                           ││
│  └─────────────────────────────────────────────────────────┘│
│                           │                                  │
│  ┌─────────────────────────────────────────────────────────┐│
│  │   Database (SQLite)                                     ││
│  │   • performance_data (raw CSV rows)                     ││
│  │   • creatives (synced from API)                         ││
│  │   • fraud_signals, import_history                       ││
│  └─────────────────────────────────────────────────────────┘│
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### Main Table: `performance_data`

Stores raw CSV data. One CSV row = one database row. No aggregation at import.

```sql
-- Identity (all optional except date)
metric_date DATE NOT NULL
creative_id TEXT           -- Links to creatives.id
billing_id TEXT            -- Pretargeting config

-- Dimensions
creative_size TEXT         -- "300x250", "Interstitial", "Video 9:16"
creative_format TEXT       -- "Video", "Display"
country TEXT               -- "Brazil", "India"
platform TEXT              -- "High-end mobile devices"
environment TEXT           -- "App", "Web"
app_id TEXT                -- Package name: "com.spotify.music"
app_name TEXT              -- "Spotify"
publisher_id TEXT
publisher_name TEXT
publisher_domain TEXT
deal_id TEXT
deal_name TEXT
transaction_type TEXT      -- "Open auction", "Private auction"
advertiser TEXT
buyer_account_id TEXT
buyer_account_name TEXT

-- Metrics
reached_queries INTEGER    -- THE critical waste metric
impressions INTEGER
clicks INTEGER
spend_micros INTEGER       -- 1,000,000 = $1.00
video_starts INTEGER
video_completions INTEGER
vast_errors INTEGER
active_view_measurable INTEGER
active_view_viewable INTEGER

-- Deduplication & Tracking
row_hash TEXT UNIQUE       -- Prevents duplicate rows
import_batch_id TEXT
imported_at TIMESTAMP
```

### Supporting Tables

```sql
-- Your creative inventory (synced from Google RTB API)
creatives (id, name, format, width, height, status, ...)

-- Detected fraud patterns for human review
fraud_signals (entity_type, entity_id, signal_type, signal_strength, evidence, status)

-- Track imports
import_history (batch_id, filename, rows_imported, date_range, columns_found, ...)
```

---

## CLI Commands

```bash
cd creative-intelligence
source venv/bin/activate

# Validate CSV (check before importing)
python cli/qps_analyzer.py validate ~/exports/bigquery.csv

# Import CSV (validates first, then imports)
python cli/qps_analyzer.py import ~/exports/bigquery.csv

# View data summary
python cli/qps_analyzer.py summary

# Size coverage analysis
python cli/qps_analyzer.py coverage --days 7

# Config performance tracking
python cli/qps_analyzer.py configs --days 7

# Fraud signal detection
python cli/qps_analyzer.py fraud --days 14

# Get pretargeting include list
python cli/qps_analyzer.py include-list

# Full combined report
python cli/qps_analyzer.py full-report --days 7 > qps_report.txt
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/qps/summary` | GET | Data summary statistics |
| `/qps/size-coverage?days=N` | GET | Size coverage report |
| `/qps/config-performance?days=N` | GET | Config performance report |
| `/qps/fraud-signals?days=N` | GET | Fraud signals report |
| `/qps/report?days=N` | GET | Full combined report |
| `/qps/include-list` | GET | Pretargeting size list |
| `/creatives` | GET | List all creatives |
| `/creatives/{id}` | GET | Single creative details |
| `/performance/import-csv` | POST | Import CSV (small files) |
| `/performance/import/batch` | POST | Import CSV (chunked, large files) |

### Example

```bash
curl http://localhost:8000/qps/summary | python -m json.tool
curl "http://localhost:8000/qps/size-coverage?days=7"
```

---

## Critical Domain Knowledge

### Size Filtering is INCLUDE-ONLY

```
⚠️  IMPORTANT: Adding ONE size EXCLUDES ALL OTHERS!

• Empty size list = Accept ALL sizes
• Add "300x250" = ONLY 300x250 (all others EXCLUDED)
• Add multiple sizes = Those sizes only (OR within list)

There is NO "exclude" option!

This is why we generate an INCLUDE list of sizes you CAN serve.
Apply carefully and monitor for 24-48 hours.
```

### Google's 114 Available Sizes

Only these sizes can be filtered in pretargeting. Sizes not in this list cannot be filtered. See `qps/constants.py` for the complete list.

Common sizes: `300x250`, `320x50`, `728x90`, `160x600`, `300x600`  
Special labels: `Interstitial`, `Video 9:16`, `Native`, `Rewarded`

### Pretargeting Logic

```
All settings use AND with each other
EXCEPT:
  • Web/App targets use OR with each other
  • Sizes within a list use OR with each other
```

---

## Fraud & Anomaly Detection

### Key Principle: Context Matters

A single anomaly isn't proof of fraud. **Patterns over time** are what matter.

```
Single occurrence:  Could be timing, tracking glitch, edge case
Repeated pattern:   Likely systematic issue (fraud, bots, bad inventory)
```

### Click Fraud Signals

#### Clicks > Impressions

| Frequency | Interpretation | Confidence |
|-----------|----------------|------------|
| Once | Timing issue - click registered after daily cutoff | Low |
| Occasionally | Tracking discrepancy between systems | Low |
| Frequently (same app) | Click injection / click fraud | High 🚨 |
| Always (specific app) | Definitely fraudulent app | Very High 🚨 |

**Why it happens legitimately:**
- Impression counted at 11:59 PM, click at 12:01 AM → different days
- Different tracking pixels with different latencies
- Viewability filtering removed impression but click still counted

**Why it indicates fraud:**
- App injects fake clicks without ever showing the ad
- Malware clicking in background
- Click farms

#### Abnormal CTR

| CTR Range | Interpretation |
|-----------|----------------|
| < 1% | Normal for most display/video |
| 1-3% | Good performance |
| Very high | Investigate - could be excellent targeting OR fraud |

**Note:** CTR thresholds vary by campaign, creative type, and targeting. Don't apply rigid rules without sufficient data. What's suspicious for one campaign may be normal for another.

**Industry rough benchmarks (for reference only):**
- Display ads: 0.1% - 0.5% typical
- Video ads: 0.5% - 2% typical
- Native ads: 0.5% - 1.5% typical
- Retargeting: Can be higher

### Bot Traffic Signals

#### High Impressions, Zero Clicks (Over Time)

| Timeframe | 0 Clicks | Interpretation |
|-----------|----------|----------------|
| 1 day | Normal | Users might not engage that day |
| 3 days | Watch | Could be bad creative or placement |
| 7+ days | Suspicious | Likely bot traffic 🚨 |
| 30+ days, thousands of imps | Definite bots | 99% bot farm 🚨 |

**Why it indicates bots:**
- Bots "view" ads to generate impression revenue for publishers
- Bots don't click (clicking would be too obvious/traceable)
- Real humans occasionally click, even on bad ads

#### Perfect Metrics (Too Consistent)

Real traffic has variance. Bot traffic is often suspiciously consistent.

| Signal | Why It's Suspicious |
|--------|---------------------|
| Exactly same impressions every hour | Bots running on schedule |
| CTR exactly 1.00% or 2.00% | Configured bot behavior |
| No weekend/weekday variance | Real users have patterns |
| Same impressions across all geos | Real traffic varies by region |

### Video-Specific Fraud Signals

#### High Starts, Zero Completions

| Start/Complete Ratio | Interpretation |
|---------------------|----------------|
| 30-50% completion | Normal for skippable video |
| 70-90% completion | Normal for non-skippable |
| < 10% completion | Suspicious - auto-skip or hidden player 🚨 |
| 0% completion (many starts) | Fraud - video never plays 🚨 |

#### High VAST Errors

| VAST Error Rate | Interpretation |
|-----------------|----------------|
| < 5% | Normal |
| 5-15% | Technical issues |
| > 15% | Suspicious inventory 🚨 |
| > 30% | Likely fraud 🚨 |

### App Quality Tiers

Based on fraud score and performance:

| Tier | Action |
|------|--------|
| **Premium** | Bid higher, good inventory |
| **Standard** | Normal bidding |
| **Watch** | Monitor closely |
| **Suspicious** | Reduce bids or pause |
| **Fraud** | Block from bidding |

### Key Takeaways

1. **One anomaly ≠ fraud** - Look for patterns over time
2. **Context matters** - What's fraud for one campaign might be normal for another
3. **Both extremes are signals** - Too many clicks AND too few clicks can indicate fraud
4. **Real traffic has variance** - Perfect consistency is suspicious
5. **Campaign-specific analysis** - Always analyze within campaign context

---

## Endpoint Configuration

Configure your bidder endpoints in `qps/constants.py`:

```python
ENDPOINTS = [
    {"name": "Region 1", "url": "your-bidder-url-1", "qps_limit": 10000},
    {"name": "Region 2", "url": "your-bidder-url-2", "qps_limit": 30000},
    {"name": "Region 3", "url": "your-bidder-url-3", "qps_limit": 50000},
]
```

**Note:** Your pretargeting QPS caps may exceed your actual endpoint capacity. The endpoint limit is typically the real bottleneck.

---

## Project Structure

```
catscan-platform/
├── creative-intelligence/          # Python backend
│   ├── qps/                        # QPS Optimization Module
│   │   ├── __init__.py             # Exports all components
│   │   ├── constants.py            # Google sizes, billing IDs, endpoints
│   │   ├── models.py               # Data classes
│   │   ├── importer.py             # CSV validator + importer
│   │   ├── size_analyzer.py        # Size coverage analysis
│   │   ├── config_tracker.py       # Config performance tracking
│   │   └── fraud_detector.py       # Fraud signal detection
│   ├── cli/
│   │   └── qps_analyzer.py         # CLI tool
│   ├── api/
│   │   └── main.py                 # FastAPI endpoints
│   ├── collectors/                 # Google API clients
│   │   ├── base.py                 # Base client with auth
│   │   ├── creatives/              # Creatives client
│   │   └── pretargeting/           # Pretargeting client
│   ├── storage/
│   │   ├── sqlite_store.py         # SQLite backend
│   │   └── migrations/             # SQL migrations
│   ├── scripts/
│   │   └── reset_database.py       # Database reset utility
│   └── config/
│       └── settings.py             # Configuration
│
├── dashboard/                      # Next.js frontend
│   ├── src/
│   │   ├── app/                    # Pages
│   │   │   ├── import/             # CSV import
│   │   │   └── creatives/          # Creative browser
│   │   ├── components/             # React components
│   │   └── lib/                    # API client, validators
│   └── package.json
│
└── docs/                           # Documentation
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
| Google APIs | google-api-python-client |

---

## Troubleshooting

### API Not Running

```bash
sudo systemctl status catscan-api
sudo systemctl restart catscan-api
journalctl -u catscan-api -f  # View logs
```

### Port Already in Use

```bash
sudo lsof -ti:8000 | xargs -r sudo kill -9
sudo systemctl restart catscan-api
```

### Database Issues

```bash
# Check database
sqlite3 ~/.catscan/catscan.db "SELECT COUNT(*) FROM creatives;"
sqlite3 ~/.catscan/catscan.db "SELECT COUNT(*) FROM performance_data;"

# Reset if needed (backup first!)
python scripts/reset_database.py
```

### CSV Import Fails

```bash
# Validate first to see what's wrong
python cli/qps_analyzer.py validate /path/to/file.csv

# Common issues:
# - Missing required columns → Follow fix instructions shown
# - Wrong date format → Should be MM/DD/YYYY or MM/DD/YY
# - Empty Creative ID → Filter these out of your export
```

---

## Phase Status

### Complete ✅

| Phase | Feature |
|-------|---------|
| 1-6 | Creative Management, Dashboard, Smart URLs |
| 8.1-8.4 | Performance API, Import UI, Large Files |
| 9.5 | QPS Optimization (CLI + API) |
| 9.6 | Unified Data Architecture |

### Ready to Implement 📋

| Phase | Feature | Prompt |
|-------|---------|--------|
| 8.5 | Seat Hierarchy Fix | `CODEX_PROMPT_Phase8.5_Seat_Hierarchy.md` |
| 9.0 | AI Campaign Clustering | `CODEX_PROMPT_Phase9_AI_Clustering.md` |

### Known Issues

| Issue | Status |
|-------|--------|
| Seat dropdown shows 0 creatives | Open |

---

## Support

- **API Docs:** http://localhost:8000/docs

---

**Next Steps:**
1. Import your BigQuery CSV (CLI or dashboard)
2. Generate QPS report
3. Review recommendations with AdOps