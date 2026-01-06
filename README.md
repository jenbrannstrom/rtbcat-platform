# Cat-Scan QPS Optimizer & Creative Intelligence Tool

**Version:** 25.0 | **Status:** Production | **Last Updated:** January 2026

A QPS optimization tool for Google Authorized Buyers. Cat-Scan helps RTB bidders eliminate wasted QPS by learning which data-streams the bidder likes to bid on, as well as fine-tune Pretargeting to allow more bid-requests to come through to the bidder for those placements/apps that the bidder prefers.

It has a free version that allows pretargeting settings to be edited based on the efficiency findings, and a paid-for upgrade that adjusts Pretargeting settings based on new creatives that get uploaded and approved to the Google AB seat, so it is effectively hands-free.

**Live:** [scan.rtb.cat](https://scan.rtb.cat)

---

## What This Solves

**The Problem:** Google Authorized Buyers provides a bulk waterfall of over 400 Billion QPS per 24 hours, it allows 10 pretargeting settings to adjust signal, but doesn't tell you:

- How to improve efficiency of the QPS your bidder consumes
- What QPS is unused vs what should be increased
- Which creatives are wasting your QPS ingress, and blocking out potentially other signal that could be more worthwhile

**The Solution:** Cat-Scan automatically:

1. Fetches all your creatives from Authorized Buyers API
2. Imports performance data from CSV exports (5 report types)
3. Identifies size mismatches, config inefficiencies, traffic quality issues
4. Provides actionable recommendations to reduce waste and improve efficiency
5. Allows improvements in Pretargeting configs to be pushed to the Google account
6. Provides rollback and historical tracking of config changes
7. Allows MCP to connect to the DB and its "algo engine" to let AI make improvements or collect insights for campaign performance

**Typical waste reduction:** Testing in progress - collecting data to understand % improvement.

Cat-Scan sits next to the Google seat, extracting data via API and CSV exports (since there is no reporting API for a Google AB seat, we compile these from CSV exports sent to a dedicated Gmail address, which is then parsed and input to the DB).

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/rtbcat/rtbcat-platform.git
cd rtbcat-platform

# 2. Setup (creates venv, installs dependencies)
./setup.sh

# 3. Start services
./run.sh

# 4. Open http://localhost:3000
```

> **Note:** On Linux, run `./run.sh` from a terminal, not by double-clicking in the file manager.

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
| **Waste Analysis** | Identify size gaps, inefficient configs, traffic quality signals |
| **RTB Funnel** | Visualize reached queries → bids → impressions |
| **Campaign Clustering** | AI-powered grouping by destination URL, country, advertiser, language |
| **CSV Import** | Auto-import performance data from Google reports (5 report types) |
| **MCP Support** | APIs to enable MCP access for your choice of AI |
| **Video Thumbnails** | Extract from VAST XML or generate via ffmpeg |
| **User Authentication** | Multi-user support with role-based access |
| **Audit Logging** | Complete audit trail of all changes |

### Dashboard Pages

| Page | URL | Purpose |
|------|-----|---------|
| **Waste Optimizer** | `/` | Main analysis dashboard with stats |
| **Creatives** | `/creatives` | Browse and search synced creatives |
| **Campaigns** | `/campaigns` | AI-clustered campaign groups |
| **Change History** | `/history` | Import history and audit trail |
| **Import** | `/import` | CSV upload interface |
| **Settings Hub** | `/settings` | All settings in one place |
| ↳ Connected Accounts | `/settings/accounts` | API credential setup |
| ↳ Buyer Seats | `/settings/seats` | Buyer seat management |
| ↳ Data Retention | `/settings/retention` | Data retention policies |
| ↳ System Status | `/settings/system` | System diagnostics & thumbnails |
| **Admin Hub** | `/admin` | Administration dashboard |
| ↳ Users | `/admin/users` | User management |
| ↳ Configuration | `/admin/configuration` | System settings |
| ↳ Audit Log | `/admin/audit-log` | Action audit trail |

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
│         118 API Endpoints                                    │
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
│         • auth        - User authentication                  │
│         • admin       - User & system management             │
└─────────────────────────────────────────────────────────────┘
              │                               │
              ▼                               ▼
┌──────────────────────────┐    ┌──────────────────────────┐
│ SQLite Database          │    │ Google Authorized        │
│ ~/.catscan/catscan.db    │    │ Buyers API               │
│ (41 tables)              │    │                          │
└──────────────────────────┘    └──────────────────────────┘
```

### Database Schema

The database contains **41 tables** organized into logical groups:

| Group | Tables | Purpose |
|-------|--------|---------|
| **Creative Management** | 3 | creatives, clusters, thumbnail_status |
| **Campaign Management** | 5 | campaigns, ai_campaigns, creative_campaigns, etc. |
| **RTB Performance** | 7 | rtb_daily, rtb_funnel, rtb_quality, etc. |
| **Pretargeting** | 7 | pretargeting_configs, pretargeting_history, etc. |
| **User Auth** | 6 | users, user_sessions, audit_log, etc. |
| **Import Tracking** | 4 | import_history, daily_upload_summary, etc. |
| **Lookup Tables** | 6 | apps, publishers, geographies, etc. |

See **[DATA_MODEL.md](DATA_MODEL.md)** for complete schema documentation.

---

## CSV Format Requirements

Cat-Scan supports **5 CSV report types** from Google Authorized Buyers. Due to field incompatibilities in Google's reporting system, multiple reports are needed to get the full picture.

> **See [docs/CSV_REPORTS_GUIDE.md](docs/CSV_REPORTS_GUIDE.md) for complete setup instructions.**

### The 5 Report Types

| Report | Purpose | Key Fields | Required? |
|--------|---------|------------|-----------|
| **Performance Detail** | Creative/Size/App data | Creative ID, Size, App ID, Publisher | ✅ Yes |
| **RTB Funnel (Geo)** | Bid pipeline by country | Bid requests, Bids, Auctions won | ✅ Yes |
| **RTB Funnel (Publishers)** | Bid pipeline by publisher | Publisher ID + Bid metrics | ✅ Yes |
| **Bid Filtering** | Why bids were filtered | Filtering reasons, Lost bids | Optional |
| **Quality Signals** | Traffic quality data | Non-human traffic rate, Viewability | Optional |

### Why Multiple Reports?

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

Cat-Scan provides **118 API endpoints** across multiple routers. Key endpoints include:

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/creatives` | List creatives with filtering |
| POST | `/collect/sync` | Sync from Google API |
| GET | `/campaigns` | List campaigns |
| POST | `/campaigns/auto-cluster` | AI clustering |
| GET | `/analytics/waste` | Waste analysis |
| GET | `/analytics/size-coverage` | Size coverage gaps |
| GET | `/analytics/publisher-waste` | Publisher inefficiency |
| POST | `/performance/import-csv` | Import CSV |
| GET | `/settings/pretargeting` | Get pretargeting configs |
| PATCH | `/settings/pretargeting/{id}` | Update pretargeting |

**Full API documentation:** http://localhost:8000/docs (Swagger UI)

---

## Services

### Docker (Recommended)

```bash
docker compose build
docker compose up -d
```

### Systemd (Production)

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

### Manual Startup

```bash
# Terminal 1: API
./venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Dashboard
cd dashboard && npm run dev
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

Create `.env` in project root:

```bash
GOOGLE_APPLICATION_CREDENTIALS=~/.catscan/credentials/google-credentials.json
DATABASE_PATH=~/.catscan/catscan.db
```

---

## Documentation

| Document | Purpose |
|----------|---------|
| **[INSTALL.md](INSTALL.md)** | Detailed installation guide |
| **[DATA_MODEL.md](DATA_MODEL.md)** | Complete database schema (41 tables) |
| **[docs/CSV_REPORTS_GUIDE.md](docs/CSV_REPORTS_GUIDE.md)** | CSV report setup |
| **[docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md)** | Google API setup |
| **[COMPLETION_PLAN.md](COMPLETION_PLAN.md)** | Project roadmap |

---

## Project Status

### Production Ready ✅

- **Live deployment** at [scan.rtb.cat](https://scan.rtb.cat) on AWS
- Creative sync from Google API (600+ creatives)
- Multi-seat buyer account support
- Waste analysis with recommendations
- CSV import (CLI, UI, and Gmail auto-import)
- Campaign clustering
- RTB funnel visualization
- Video thumbnail generation
- User authentication with role-based access
- Audit logging

### Roadmap

1. **Automated Configuration** - Paid feature for hands-free pretargeting updates
2. **Enhanced Analytics** - Platform/Environment dimension support
3. **MCP Integration Guide** - Documentation for AI tool integration
4. **Performance at Scale** - Virtual scrolling, caching improvements

---

## Known Issues

| Issue | Workaround |
|-------|------------|
| Port 8000 stuck | `sudo lsof -ti:8000 \| xargs -r sudo kill -9` |
| No video thumbnails | Run `./venv/bin/python cli/qps_analyzer.py generate-thumbnails` |
| Dashboard not updating | Run `npm run build` in dashboard/ |
| uvicorn "module not found" | Use `./venv/bin/python -m uvicorn` instead of `uvicorn` directly |

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
