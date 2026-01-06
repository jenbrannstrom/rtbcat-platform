# Cat-Scan QPS Optimizer & Creative Intelligence Tool

**Version:** 24.0 | **Phase:** Schema Refactoring | **Last Updated:** January 2026

A QPS optimization tool for Google Authorized Buyers. Cat-Scan helps RTB bidders improve QPS efficiency by learning which data-streams the bidder prefers to bid on, and fine-tune Pretargeting to allow more bid-requests through to the bidder for preferred placements/apps.

It has a free version that allows pretargeting settings to be edited based on efficiency findings, and a paid-for upgrade that auto-adjusts Pretargeting settings based on new creatives that get uploaded and approved to the Google AB seat, making it effectively hands-free.

---

## What This Solves

**The Problem:** Google Authorized Buyers provides a bulk waterfall of over 400 Billion QPS per 24 hours. It allows 10 pretargeting settings to adjust signal, shows you creative IDs like `cr-12345`, but doesn't tell you:

- How to improve efficiency of the QPS your bidder consumes
- What QPS is unused vs what should be increased
- Which creatives are underperforming and blocking potentially better signal

**The Solution:** Cat-Scan automatically:

1. Fetches all your creatives from Authorized Buyers API
2. Imports performance data from CSV exports
3. Identifies size gaps and configuration inefficiencies
4. Provides actionable recommendations to improve efficiency
5. Allows improvements in Pretargeting configs to be pushed to the Google account
6. Provides rollback and historical tracking of config changes
7. Allows MCP to connect to the DB and its "algo engine" to let AI make improvements or simply collect insights for campaign performance

**Typical efficiency improvement:** Unknown at this time. We are starting to test and need data to understand the % improvement.

Cat-Scan sits next to the Google seat, extracting data via API and CSV exports (since there is no reporting API for a Google AB seat, we compile data from CSV exports sent to a dedicated Gmail address, which is then parsed and stored in the DB. The schema normalizes the various CSV daily reports for a dataset that can be evaluated).

Because of this limited data, the insight is limited to QPS optimization. We deduce what the media buyer is trying to achieve based on the creatives' settings, spend, CPM and clicks. The goal is QPS optimization, which assists the media buyer in achieving their objectives.

**Campaign Clustering**

Clustering means grouping creatives together based on deduced logic. It also allows manual sorting. The purpose is to reveal insights for further QPS optimization.

It works by automatically grouping creatives based on same/similar destination URL. This could be augmented with AI image recognition to identify creative language (image/HTML/Video/Native ads) and group them by language, or surface localization configuration issues.

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/rtbcat/rtbcat-platform.git
cd rtbcat-platform
./setup.sh

# 2. Start services (from terminal)
./run.sh

# 3. Open http://localhost:3000
```

> **Note:** On Linux (Zorin, Ubuntu, etc.), run `./run.sh` from a terminal, not by double-clicking in the file manager. If double-clicking doesn't work, right-click → "Open With Terminal" or run from command line.

### Requirements

- Python 3.11+
- Node.js 18+
- ffmpeg (optional, for video thumbnails)

See **[INSTALL.md](INSTALL.md)** for detailed installation instructions.

---

## Features

### Core Capabilities

| Feature | Description |
|---------|-------------|
| **Creative Sync** | Fetch all creatives from Google Authorized Buyers API |
| **Multi-Seat Support** | Manage multiple buyer accounts under one bidder |
| **Efficiency Analysis** | Identify size gaps, config inefficiencies, optimization opportunities |
| **RTB Funnel** | Visualize reached queries → bids → impressions |
| **Campaign Clustering** | AI-powered grouping by destination URL, region, advertiser, language |
| **CSV Import** | Auto-import performance data from Google reports |
| **MCP Support** | APIs to enable MCP access for your own choice of AI |
| **Video Thumbnails** | Visualize creatives clearly: extract from VAST XML or generate via ffmpeg |

### Dashboard Pages

| Page | URL | Purpose |
|------|-----|---------|
| Home | `/` | Main dashboard with stats |
| Setup | `/setup` | Connect API, Gmail, configure retention |
| Efficiency Analysis | `/efficiency-analysis` | Size coverage, config performance |
| Creatives | `/creatives` | Browse synced creatives |
| Campaigns | `/campaigns` | AI-clustered campaign groups |
| Import | `/import` | Manual CSV upload |
| History | `/history` | Import history |
| Settings | `/settings` | General settings |
| Seats | `/settings/seats` | Buyer seat management |
| Admin | `/admin` | Admin dashboard |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│           Next.js Dashboard (Port 3000)                      │
│           /dashboard                                         │
└─────────────────────────────────────────────────────────────┘
                              │ HTTP/JSON
                              ▼
┌─────────────────────────────────────────────────────────────┐
│         FastAPI Backend (Port 8000)                          │
│                                                              │
│         Modular Router Architecture:                         │
│         • system      - Health, stats, thumbnails            │
│         • creatives   - Creative management & sync           │
│         • seats       - Buyer seat discovery                 │
│         • settings    - RTB endpoints, pretargeting          │
│         • analytics   - Efficiency analysis, RTB funnel      │
│         • config      - Configuration & credentials          │
│         • gmail       - Auto-import from Gmail               │
│         • recommendations - AI recommendations               │
│         • retention   - Data retention policies              │
│         • uploads     - CSV file uploads                     │
└─────────────────────────────────────────────────────────────┘
              │                               │
              ▼                               ▼
┌──────────────────────────┐    ┌──────────────────────────┐
│ SQLite Database          │    │ Google Authorized        │
│ ~/.catscan/catscan.db    │    │ Buyers API               │
└──────────────────────────┘    └──────────────────────────┘
```

### Database Schema (Key Tables)

| Table | Purpose |
|-------|---------|
| `rtb_daily` | The fact table - all CSV imports |
| `creatives` | Creative inventory from API |
| `campaigns` | User-defined campaign groupings |
| `buyer_seats` | Buyer accounts under a bidder |
| `anomaly_signals` | Unusual patterns in traffic or performance |
| `inefficiency_signals` | QPS optimization opportunities |

See **[DATA_MODEL.md](DATA_MODEL.md)** for the complete 41-table schema.

---

## CSV Format Requirements

Cat-Scan requires **3 separate CSV reports** from Google Authorized Buyers due to field incompatibilities in Google's reporting system.

> **See [docs/CSV_REPORTS_GUIDE.md](docs/CSV_REPORTS_GUIDE.md) for complete setup instructions.**

### The Required Reports

| Report | Purpose | Key Fields | Table |
|--------|---------|------------|-------|
| **Performance Detail** | Creative/Size/App data | Creative ID, Size, App ID, Publisher | `rtb_daily` |
| **RTB Funnel (Regional)** | Bid pipeline by region | Bid requests, Bids, Auctions won | `rtb_funnel` |
| **RTB Funnel (Publishers)** | Bid pipeline by publisher | Publisher ID + Bid metrics | `rtb_funnel` |

### Why 3 Reports?

Google's limitation: *"Mobile app ID is not compatible with [Bid requests]..."*

- To get **App/Creative detail** → you lose Bid request metrics
- To get **Bid request metrics** → you lose App/Creative detail
- Cat-Scan **joins them** by date + region to give you the full picture

### Quick Reference

**Report 1 - Performance Detail:**
```
Dimensions: Day, Billing ID, Creative ID, Creative size, Region, Publisher ID, Mobile app ID
Metrics: Reached queries, Impressions, Clicks, Spend
```

**Report 2 - RTB Funnel (Regional):**
```
Dimensions: Day, Region, Buyer account ID
Metrics: Bid requests, Inventory matches, Reached queries, Bids, Bids in auction, Auctions won, Impressions
```

**Report 3 - RTB Funnel (Publishers):**
```
Dimensions: Day, Region, Buyer account ID, Publisher ID, Publisher name
Metrics: Same as Report 2
```

> **Efficiency Calculation:** `Impressions / Reached Queries`

---

## CLI Commands

```bash
# Smart import (auto-detects report type)
./venv/bin/python -m qps.smart_importer /path/to/any-report.csv

# Show CSV report creation instructions
./venv/bin/python -m qps.smart_importer --help

# Import performance CSV specifically
./venv/bin/python cli/qps_analyzer.py import /path/to/report.csv

# Import funnel CSV specifically
./venv/bin/python -m qps.funnel_importer /path/to/funnel-report.csv

# Validate CSV before import
./venv/bin/python cli/qps_analyzer.py validate /path/to/report.csv

# View database summary
./venv/bin/python cli/qps_analyzer.py summary

# Generate efficiency analysis report
./venv/bin/python cli/qps_analyzer.py full-report --days 7

# Generate video thumbnails
./venv/bin/python cli/qps_analyzer.py generate-thumbnails --limit 100
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/creatives` | List creatives |
| POST | `/collect/sync` | Sync from Google API |
| GET | `/campaigns` | List campaigns |
| POST | `/campaigns/auto-cluster` | AI clustering |
| GET | `/analytics/efficiency` | Efficiency analysis |
| POST | `/performance/import-csv` | Import CSV |

Full API docs: http://localhost:8000/docs (118 endpoints total)

---

## Services

### Systemd (Recommended for Production)

```bash
# Start services
sudo systemctl start catscan-api
sudo systemctl status catscan-api

# View logs
sudo journalctl -u catscan-api -f

# If port 8000 is stuck
sudo lsof -ti:8000 | xargs -r sudo kill -9
sudo systemctl restart catscan-api
```

### Docker

```bash
docker compose build api
docker compose up -d api
```

---

## Configuration

### Data Directory: `~/.catscan/`

```
~/.catscan/
├── catscan.db              # SQLite database
├── thumbnails/             # Generated video thumbnails
├── imports/                # Downloaded CSV reports
└── credentials/
    └── google-credentials.json
```

### Environment Variables

Create `.env` in the project root:

```bash
GOOGLE_APPLICATION_CREDENTIALS=~/.catscan/credentials/google-credentials.json
DATABASE_PATH=~/.catscan/catscan.db
```

---

## Documentation

| Document | Purpose |
|----------|---------|
| **[docs/HANDOVER.md](docs/HANDOVER.md)** | Complete project handover with next steps |
| **[INSTALL.md](INSTALL.md)** | Detailed installation guide |
| **[docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md)** | Google API setup instructions |
| **[DATA_MODEL.md](DATA_MODEL.md)** | Complete database schema (41 tables) |
| **[docs/CSV_REPORTS_GUIDE.md](docs/CSV_REPORTS_GUIDE.md)** | CSV report setup |

### Historical Development Phases

Detailed phase documentation is archived in `docs/phases/`:
- Phase 11: Decision Intelligence
- Phase 12: Schema Cleanup
- Phase 21: RTB Funnel Analysis
- Phase 22: Unified Dashboard

---

## Project Status

**Deployed:** Live at `scan.rtb.cat` on AWS

### What Works (Production Ready)

- Creative sync from Google API (600+ creatives)
- Multi-seat buyer account support
- Efficiency analysis with recommendations
- CSV import (CLI and UI)
- Gmail auto-import (daily cron)
- Campaign clustering
- RTB funnel visualization
- Video thumbnail generation

### Roadmap

1. **Multi-account support** - Account switching in UI
2. **Multi-seat improvements** - Enhanced seat management
3. **RTB Troubleshooting API** - Integrate bid metrics
4. **Performance at scale** - Virtual scrolling, caching
5. **Auto-optimization (paid)** - Hands-free pretargeting adjustments
6. **Creative modal enhancements** - Additional data in creative details

See **[docs/HANDOVER.md](docs/HANDOVER.md)** for complete roadmap.

---

## Known Issues

| Issue | Workaround |
|-------|------------|
| Port 8000 stuck | `sudo lsof -ti:8000 \| xargs -r sudo kill -9` |
| No video thumbnails | Run `./venv/bin/python cli/qps_analyzer.py generate-thumbnails` |
| Dashboard not updating | Run `npm run build` |
| uvicorn "module not found" | Use `./venv/bin/python -m uvicorn` instead of `uvicorn` directly |

### API Startup (Manual Method)

If `./run.sh` doesn't work, start the services manually:

```bash
# Terminal 1: API
./venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Dashboard
cd dashboard
npm run dev
```

**Why use `./venv/bin/python -m uvicorn`?** Running `uvicorn` directly after `source venv/bin/activate` can fail in some environments (Flatpak, certain shells). Using the venv's Python directly is more reliable.

---

## Development

```bash
# Format and lint
./venv/bin/black . && ./venv/bin/isort . && ./venv/bin/ruff check .

# Run tests
./venv/bin/pytest tests/ -v

# Type check
./venv/bin/mypy .
```

---

## License

MIT License - see [LICENSE](LICENSE) file

---

## Acknowledgments

- [Google Authorized Buyers RTB API](https://developers.google.com/authorized-buyers/apis)
- [FastAPI](https://fastapi.tiangolo.com/)
- [Next.js](https://nextjs.org/)

---

**Built for RTB bidders who want to improve QPS efficiency.**
