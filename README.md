# Cat-Scan QPS Optimizer & Creative Intelligence Tool

**Version:** 24.0 | **Phase:** Schema Refactoring | **Last Updated:** December 11, 2025

A privacy-first QPS optimization platform for Google Authorized Buyers. Cat-Scan helps RTB bidders eliminate wasted QPS by learning which data-streams the bidder likes to bid on.

> **Philosophy:** Intelligence without assumptions. Facts that drive action.

---

## What This Solves

**The Problem:** Google Authorized Buyers shows you creative IDs like `cr-12345`, but doesn't tell you:
- How to improve efficiency of the QPS your bidder consumes
- What QPS is unused vs what should be increased
- Which creatives are wasting your budget

**The Solution:** Cat-Scan automatically:
1. Fetches all your creatives from Authorized Buyers API
2. Imports performance data from CSV exports
3. Identifies size mismatches, config inefficiencies, and fraud signals
4. Provides actionable recommendations to reduce waste

**Typical waste reduction: 20-40% of QPS.**

---

## Quick Start

```bash
# 1. Clone and setup
git clone https://github.com/yourorg/rtbcat-platform.git
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
| **Waste Analysis** | Identify size gaps, inefficient configs, fraud signals |
| **RTB Funnel** | Visualize reached queries → bids → impressions |
| **Campaign Clustering** | AI-powered grouping by URL, advertiser, language |
| **CSV Import** | Import performance data from Google reports |
| **Gmail Auto-Import** | Automatic daily report ingestion |
| **Video Thumbnails** | Extract from VAST XML or generate via ffmpeg |

### Dashboard Pages

| Page | URL | Purpose |
|------|-----|---------|
| Waste Optimizer | `/` | Main analysis dashboard |
| Setup | `/setup` | Connect API, Gmail, configure retention |
| Waste Analysis | `/waste-analysis` | Size coverage, config performance |
| Creatives | `/creatives` | Browse synced creatives |
| Campaigns | `/campaigns` | AI-clustered campaign groups |
| Import | `/import` | Manual CSV upload |

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
│         /creative-intelligence                               │
│                                                              │
│         Modular Router Architecture:                         │
│         • system      - Health, stats, thumbnails            │
│         • creatives   - Creative management & sync           │
│         • seats       - Buyer seat discovery                 │
│         • settings    - RTB endpoints, pretargeting          │
│         • analytics   - Waste analysis, RTB funnel           │
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

### Database Schema

| Table | Purpose |
|-------|---------|
| `rtb_daily` | THE fact table - all CSV imports |
| `creatives` | Creative inventory from API |
| `campaigns` | User-defined campaign groupings |
| `buyer_seats` | Buyer accounts under a bidder |
| `fraud_signals` | Detected fraud patterns |
| `waste_signals` | Evidence-based waste detection |

---

## CSV Format Requirements

Cat-Scan requires **3 separate CSV reports** from Google Authorized Buyers due to field incompatibilities in Google's reporting system.

> **See [docs/CSV_REPORTS_GUIDE.md](docs/CSV_REPORTS_GUIDE.md) for complete setup instructions.**

### The 3 Required Reports

| Report | Purpose | Key Fields | Table |
|--------|---------|------------|-------|
| **Performance Detail** | Creative/Size/App data | Creative ID, Size, App ID, Publisher | `rtb_daily` |
| **RTB Funnel (Geo)** | Bid pipeline by country | Bid requests, Bids, Auctions won | `rtb_funnel` |
| **RTB Funnel (Publishers)** | Bid pipeline by publisher | Publisher ID + Bid metrics | `rtb_funnel` |

### Why 3 Reports?

Google's limitation: *"Mobile app ID is not compatible with [Bid requests]..."*

- To get **App/Creative detail** → you lose Bid request metrics
- To get **Bid request metrics** → you lose App/Creative detail
- Cat-Scan **joins them** by date + country to give you the full picture

### Quick Reference

**Report 1 - Performance Detail:**
```
Dimensions: Day, Billing ID, Creative ID, Creative size, Country, Publisher ID, Mobile app ID
Metrics: Reached queries, Impressions, Clicks, Spend
```

**Report 2 - RTB Funnel (Geo):**
```
Dimensions: Day, Country, Buyer account ID
Metrics: Bid requests, Inventory matches, Reached queries, Bids, Bids in auction, Auctions won, Impressions
```

**Report 3 - RTB Funnel (Publishers):**
```
Dimensions: Day, Country, Buyer account ID, Publisher ID, Publisher name
Metrics: Same as Report 2
```

> **Waste Calculation:** `(Reached Queries - Impressions) / Reached Queries`

---

## CLI Commands

```bash
cd creative-intelligence

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

# Generate waste analysis report
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
| GET | `/analytics/waste` | Waste analysis |
| POST | `/performance/import-csv` | Import CSV |

Full API docs: http://localhost:8000/docs

---

## Services

### Systemd (Recommended for Production)

```bash
# Start services
sudo systemctl start rtbcat-api
sudo systemctl status rtbcat-api

# View logs
sudo journalctl -u rtbcat-api -f

# If port 8000 is stuck
sudo lsof -ti:8000 | xargs -r sudo kill -9
sudo systemctl restart rtbcat-api
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

Create `/creative-intelligence/.env`:

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
| **[docs/RTB_FRAUD_SIGNALS_REFERENCE.md](docs/RTB_FRAUD_SIGNALS_REFERENCE.md)** | Fraud detection reference |

### Historical Development Phases

Detailed phase documentation is archived in `docs/phases/`:
- Phase 11: Decision Intelligence
- Phase 12: Schema Cleanup
- Phase 21: RTB Funnel Analysis
- Phase 22: Unified Dashboard

---

## Project Status

### What Works (Production Ready)

- Creative sync from Google API (600+ creatives)
- Multi-seat buyer account support
- Waste analysis with recommendations
- CSV import (CLI and UI)
- Gmail auto-import (daily cron)
- Campaign clustering
- RTB funnel visualization
- Video thumbnail generation

### Next Steps

1. **Production deployment** - Cloud server, domain, SSL
2. **Multi-account support** - Account switching in UI
3. **RTB Troubleshooting API** - Integrate bid metrics
4. **Performance at scale** - Virtual scrolling, caching

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
cd creative-intelligence
./venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Dashboard
cd dashboard
npm run dev
```

**Why use `./venv/bin/python -m uvicorn`?** Running `uvicorn` directly after `source venv/bin/activate` can fail in some environments (Flatpak, certain shells). Using the venv's Python directly is more reliable.

---

## Development

```bash
cd creative-intelligence

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
