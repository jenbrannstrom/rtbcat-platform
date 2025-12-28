# Cat-Scan Project Handover

**Date:** December 8, 2025
**Version:** 23.0
**Status:** Production-Ready with Active Development

---

## Executive Summary

**Cat-Scan** is a privacy-first QPS (Queries Per Second) optimization platform for Google Authorized Buyers. It helps RTB bidders eliminate wasted QPS by analyzing bid request traffic patterns and creative inventory gaps.

### Core Value Proposition

> **Intelligence without assumptions. Facts that drive action.**

Cat-Scan identifies 20-40% QPS waste by detecting:
1. **Size mismatch** - Receiving bid requests for creative sizes you don't have
2. **Config inefficiency** - Pretargeting configs with poor win rates
3. **Fraud signals** - Suspicious patterns for human review (high CTR, clicks > impressions)
4. **Zero engagement** - Creatives spending money with no user interaction

---

## What Works Now

### Core Features (Production Ready)

| Feature | Status | Description |
|---------|--------|-------------|
| **Creative Management** | Complete | Sync 600+ creatives from Google Authorized Buyers API |
| **Multi-Seat Support** | Complete | Manage multiple buyer accounts under one bidder |
| **Waste Analysis Dashboard** | Complete | Visual waste percentage, QPS savings estimates |
| **CSV Import** | Complete | Import performance data from Google reports |
| **Gmail Auto-Import** | Complete | Automatic scheduled report ingestion (daily cron) |
| **Campaign Clustering** | Complete | AI-powered grouping by URL, advertiser, language |
| **RTB Funnel Analysis** | Complete | Reached queries → Bids → Impressions funnel |
| **Video Thumbnails** | Complete | Extract from VAST XML or generate via ffmpeg |

### Dashboard Pages

| Page | URL | Purpose |
|------|-----|---------|
| Home | `/` | Redirects to `/waste-analysis` |
| **Waste Analysis** | `/waste-analysis` | Main dashboard - RTB funnel, pretargeting configs, size coverage |
| Setup | `/setup` | Unified setup: API credentials, Gmail import, data retention |
| Creatives | `/creatives` | Browse all synced creatives with filters |
| Campaigns | `/campaigns` | AI-clustered campaign groups |
| Campaign Detail | `/campaigns/[id]` | Individual campaign performance |
| Import | `/import` | Manual CSV upload for performance data |
| Connect | `/connect` | Legacy credential upload (redirects to /setup) |
| Settings | `/settings` | Settings hub |
| Seats | `/settings/seats` | Manage buyer seat display names |
| Retention | `/settings/retention` | Data retention policies |

### Waste Analysis Page Sections (`/waste-analysis`)

The main dashboard contains these sections:

1. **Account Endpoints Header** - RTB endpoint URLs, QPS allocations per region (US West, US East, Asia), sync button
2. **RTB Funnel Card** - Reached queries → Win rate → Impressions visualization with QPS/IPS metrics
3. **Pretargeting Configs** - Expandable cards per billing_id showing:
   - Win rate & waste percentage with color-coded indicators
   - Included geos, formats, sizes, platforms (as pills)
   - Config breakdown panel (tabs: By Size, By Geo, By Publisher, By Creative)
4. **Size Analysis** - Size coverage heatmap, gap detection (requires CSV with size dimension)
5. **Period Selector** - 7/14/30 day toggle affecting all metrics

---

## Technical Architecture

```
┌─────────────────────────────────────────────────────────────┐
│           Next.js Dashboard (Port 3000)                      │
│           Location: /dashboard                               │
│           Framework: Next.js 14 + React + TailwindCSS        │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ HTTP/JSON API
                              ▼
┌─────────────────────────────────────────────────────────────┐
│         FastAPI Backend (Port 8000)                          │
│         Location: /creative-intelligence                     │
│         Language: Python 3.11 + FastAPI + SQLite             │
│                                                              │
│         Key Modules:                                         │
│         • api/main.py        - FastAPI app & middleware      │
│         • api/routers/       - Modular API routers (10)      │
│         • storage/           - SQLite database layer         │
│         • collectors/        - Google API clients            │
│         • analytics/         - RTB funnel, waste analysis    │
│         • services/          - Business logic services       │
│         • cli/               - CLI tools (qps_analyzer.py)   │
└─────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌──────────────────────────┐    ┌──────────────────────────┐
│ SQLite Database          │    │ Google Authorized        │
│ ~/.catscan/catscan.db    │    │ Buyers API               │
│                          │    │                          │
│ Tables:                  │    │ • Creatives list         │
│ • rtb_daily (fact table) │    │ • Buyer seats            │
│ • creatives              │    │ • Pretargeting configs   │
│ • campaigns              │    └──────────────────────────┘
│ • buyer_seats            │
│ • fraud_signals          │
│ • waste_signals          │
│ • import_history         │
└──────────────────────────┘
```

### Database Schema (v22)

**Core Tables:**

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `rtb_daily` | THE fact table for all CSV imports | `metric_date`, `creative_id`, `billing_id`, `reached_queries`, `impressions` |
| `creatives` | Creative inventory from API | `id`, `format`, `canonical_size`, `approval_status` |
| `campaigns` | User-defined campaign groupings | `id`, `name`, `seat_id` |
| `creative_campaigns` | Creative → Campaign mapping | `creative_id`, `campaign_id` |
| `buyer_seats` | Buyer accounts under a bidder | `buyer_id`, `bidder_id`, `display_name` |
| `fraud_signals` | Detected fraud patterns | `creative_id`, `signal_type`, `evidence` |
| `waste_signals` | Evidence-based waste detection | `creative_id`, `signal_type`, `evidence` |

---

## Quick Start

### For Developers

```bash
# 1. Clone and setup
git clone https://github.com/yourorg/rtbcat-platform.git
cd rtbcat-platform
./setup.sh

# 2. Start Backend (Terminal 1)
cd creative-intelligence
source venv/bin/activate
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

# 3. Start Dashboard (Terminal 2)
cd dashboard
npm run dev

# 4. Open browser
open http://localhost:3000
```

### Using Systemd Services

```bash
# API service
sudo systemctl start rtbcat-api
sudo systemctl status rtbcat-api
sudo journalctl -u rtbcat-api -f

# Dashboard service (if configured)
sudo systemctl start rtbcat-dashboard
```

### Key CLI Commands

```bash
cd creative-intelligence
source venv/bin/activate

# Import performance CSV
python cli/qps_analyzer.py import /path/to/report.csv

# Validate CSV before import
python cli/qps_analyzer.py validate /path/to/report.csv

# View database summary
python cli/qps_analyzer.py summary

# Generate waste analysis report
python cli/qps_analyzer.py full-report --days 7

# Generate video thumbnails
python cli/qps_analyzer.py generate-thumbnails --limit 100
```

---

## Key API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check with config status |
| GET | `/stats` | Database statistics |
| GET | `/creatives` | List creatives with filters |
| GET | `/creatives/{id}` | Get specific creative |
| POST | `/collect/sync` | Sync creatives from Google API |
| GET | `/campaigns` | List AI-generated campaigns |
| POST | `/campaigns/auto-cluster` | Auto-cluster creatives |
| GET | `/seats` | List all buyer seats |
| POST | `/seats/discover` | Discover seats from Google API |
| GET | `/analytics/waste` | Get waste analysis report |
| GET | `/analytics/spend-stats` | Get spend/CPM stats |
| GET | `/analytics/rtb-funnel/configs` | Get pretargeting config performance |
| POST | `/performance/import-csv` | Import performance CSV |
| POST | `/config/credentials` | Upload service account JSON key |

Full API docs: http://localhost:8000/docs

---

## Priority Next Steps

### High Priority (P0)

1. **Production Deployment**
   - Set up cloud server (AWS t3.medium recommended: ~$35/month)
   - Configure domain and SSL
   - Set up automated backups

2. **Complete Gmail Auto-Import Integration**
   - Test daily cron job reliability
   - Add failure alerting
   - Implement automatic database import after download

3. **Multi-Account Support**
   - Backend: Account switching logic
   - Frontend: Account selector dropdown in header
   - Database: Per-account data isolation

### Medium Priority (P1)

4. **RTB Troubleshooting API Integration**
   - Implement `adexchangebuyer2` v2beta1 client
   - Fetch bid metrics, filtered bid reasons
   - Add to funnel analysis view

5. **Performance at Scale**
   - Virtual scrolling for 1000+ creatives
   - Query result caching (Redis or in-memory)
   - Lazy thumbnail loading

6. **Pretargeting Recommendations**
   - Generate suggested config changes based on waste analysis
   - Export recommendations to pretargeting API format
   - Track recommendation success over time

### Low Priority (P2)

7. **Enhanced Fraud Detection**
   - Machine learning model for pattern detection
   - Publisher/app blocklist recommendations
   - Integration with third-party fraud vendors

8. **Historical Analytics**
   - Trend charts (waste % over time)
   - Campaign performance comparison
   - Configurable data retention

---

## Known Issues

### Critical

| Issue | Impact | Workaround |
|-------|--------|------------|
| API Port Conflict | Service fails to start | `sudo lsof -ti:8000 \| xargs -r sudo kill -9 && sudo systemctl restart rtbcat-api` |

### Medium

| Issue | Impact | Workaround |
|-------|--------|------------|
| Video thumbnails need ffmpeg | 91% of videos show no thumbnail | Run `python cli/qps_analyzer.py generate-thumbnails --limit 100` |
| Date serialization | SQLite returns strings | API handles both string and datetime formats |
| Dashboard hot reload | Changes not reflected | Run `npm run build` after backend changes |

### Low

| Issue | Impact | Workaround |
|-------|--------|------------|
| Empty seats on first load | Seats show 0 creatives | Refresh page after API startup |
| Two dashboard directories | Confusion during development | Main dashboard is `/dashboard/`, ignore `/creative-intelligence/dashboard/` |

---

## File Structure

```
rtbcat-platform/
├── creative-intelligence/      # Python backend
│   ├── api/
│   │   ├── main.py             # FastAPI app & middleware
│   │   ├── dependencies.py     # Shared dependencies
│   │   └── routers/            # Modular API routers
│   │       ├── system.py       # Health, stats, thumbnails
│   │       ├── creatives.py    # Creative management
│   │       ├── seats.py        # Buyer seat management
│   │       ├── settings.py     # RTB endpoints, pretargeting
│   │       ├── uploads.py      # CSV file uploads
│   │       ├── analytics.py    # Waste analysis, RTB funnel
│   │       ├── config.py       # Configuration endpoints
│   │       ├── gmail.py        # Gmail auto-import
│   │       ├── recommendations.py  # AI recommendations
│   │       └── retention.py    # Data retention settings
│   ├── storage/
│   │   └── sqlite_store.py     # Database layer
│   ├── collectors/
│   │   ├── creatives/          # Google Creatives API client
│   │   ├── pretargeting/       # Pretargeting configs client
│   │   ├── endpoints/          # RTB endpoints client
│   │   └── seats.py            # Buyer seats discovery
│   ├── services/
│   │   └── waste_analyzer.py   # Waste analysis service
│   ├── analytics/
│   │   └── rtb_funnel_analyzer.py
│   ├── cli/
│   │   └── qps_analyzer.py     # CLI tools
│   ├── config/
│   │   └── config_manager.py   # Encrypted credential storage
│   └── requirements.txt
│
├── dashboard/                   # Next.js frontend
│   ├── src/
│   │   ├── app/                # Page routes
│   │   ├── components/         # React components
│   │   └── lib/                # API client, utilities
│   └── package.json
│
├── docs/
│   ├── HANDOVER.md             # This file
│   ├── SETUP_GUIDE.md          # User setup instructions
│   ├── CAT_SCAN_README.md      # Feature documentation
│   └── phases/                 # Historical development phases
│
├── INSTALL.md                  # Installation guide
├── README.md                   # Project overview
├── setup.sh                    # One-command setup script
└── docker-compose.yml          # Docker configuration
```

---

## Configuration Files

### Data Directory: `~/.catscan/`

```
~/.catscan/
├── catscan.db              # SQLite database
├── catscan.db-wal          # Write-ahead log (WAL mode)
├── thumbnails/             # Generated video thumbnails
├── imports/                # Downloaded CSV reports
├── logs/                   # Import and sync logs
└── credentials/
    ├── google-credentials.json    # RTB API service account
    ├── gmail-oauth-client.json    # Gmail API OAuth client
    └── gmail-token.json           # Gmail API token (auto-generated)
```

### Systemd Service: `/etc/systemd/system/rtbcat-api.service`

```ini
[Unit]
Description=Cat-Scan Creative Intelligence API
After=network.target

[Service]
Type=simple
User=YOUR_USER
WorkingDirectory=/path/to/rtbcat-platform/creative-intelligence
ExecStart=/path/to/venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

---

## Development Guidelines

### Code Quality

```bash
cd creative-intelligence
source venv/bin/activate

# Format code
black .
isort .

# Lint
ruff check .

# Type check
mypy .

# Run tests
pytest tests/ -v

# All checks
black . && isort . && ruff check . && pytest
```

### Database Maintenance

```bash
# Enable WAL mode (important for concurrent access)
sqlite3 ~/.catscan/catscan.db "PRAGMA journal_mode=WAL;"

# Check database health
sqlite3 ~/.catscan/catscan.db "PRAGMA integrity_check;"

# Reclaim space after deletions
sqlite3 ~/.catscan/catscan.db "VACUUM;"

# Backup database
sqlite3 ~/.catscan/catscan.db ".backup ~/backups/catscan_$(date +%Y%m%d).db"
```

### Adding New Features

1. **Backend changes**: Edit files in `/creative-intelligence/`
2. **Frontend changes**: Edit files in `/dashboard/src/`
3. **Database schema changes**:
   - Create migration script in `/creative-intelligence/scripts/`
   - Update `reset_database.py` with new schema
   - Document in this handover

### API Router Architecture

The FastAPI backend uses a modular router architecture. Each router handles a specific domain:

| Router | File | Endpoints | Purpose |
|--------|------|-----------|---------|
| **system** | `routers/system.py` | `/health`, `/stats`, `/thumbnails/*` | Health checks, database stats, video thumbnails |
| **creatives** | `routers/creatives.py` | `/creatives/*`, `/collect/*` | Creative CRUD, API sync |
| **seats** | `routers/seats.py` | `/seats/*` | Buyer seat discovery and management |
| **settings** | `routers/settings.py` | `/settings/*` | RTB endpoints, pretargeting configs |
| **uploads** | `routers/uploads.py` | `/uploads/*` | CSV file uploads |
| **analytics** | `routers/analytics.py` | `/analytics/*` | Waste analysis, RTB funnel, spend stats |
| **config** | `routers/config.py` | `/config/*` | Configuration and credentials |
| **gmail** | `routers/gmail.py` | `/gmail/*` | Gmail OAuth and auto-import |
| **recommendations** | `routers/recommendations.py` | `/recommendations/*` | AI-powered recommendations |
| **retention** | `routers/retention.py` | `/retention/*` | Data retention policies |

**Adding a new endpoint:**
1. Identify the appropriate router or create a new one in `api/routers/`
2. Add the router to `api/routers/__init__.py`
3. Import and include the router in `api/main.py`

---

## Mental Model: Understanding Cat-Scan

### The RTB Funnel

```
Google Offers:     29.5 BILLION bid requests (341K QPS)
                         ↓ 99.92% filtered by pretargeting
Reaches Bidder:        24.8 MILLION (287 QPS)
                         ↓ Bidder bids ~7x per query
Bids Submitted:       183.5 MILLION
                         ↓ 66% don't win
IMPRESSIONS WON:        8.4 MILLION
```

**Key insight:** The 99.92% filter is pretargeting working correctly. Cat-Scan focuses on the **66% waste** in traffic that reaches your bidder but doesn't convert.

### Control Hierarchy

1. **Endpoint Zones** - Which geographic regions receive bid requests (US-East, US-West, EU, Asia)
2. **Pretargeting Configs** - The primary lever for QPS efficiency (sizes, geos, platforms)
3. **Bidder Logic** - Not controlled by Cat-Scan (coordinate with bidder team)

### Data Sources

| Source | What It Provides | Update Method |
|--------|------------------|---------------|
| Google RTB API | Creative metadata (what the ad IS) | On-demand sync |
| CSV Export | Performance data (how it PERFORMED) | Manual import or Gmail auto-import |

**There is no Google Reporting API.** Performance metrics must come from CSV exports.

---

## Key Domain Terminology

| Term | Definition |
|------|------------|
| **QPS** | Queries Per Second - bid requests received |
| **Reached Queries** | Bid requests that passed pretargeting filters |
| **Billing ID** | Pretargeting configuration identifier |
| **Waste Rate** | `(reached_queries - impressions) / reached_queries × 100` |
| **Win Rate** | `impressions / reached_queries × 100` |
| **Seat / Buyer ID** | Sub-account under a bidder |
| **Canonical Size** | Normalized IAB size (e.g., "300x250") |

---

## Resources & Links

- **Google Authorized Buyers UI**: https://authorized-buyers.google.com/
- **Real-Time Bidding API Docs**: https://developers.google.com/authorized-buyers/apis/guides/rtb-api
- **Pretargeting Configs Guide**: https://developers.google.com/authorized-buyers/apis/guides/rtb-api/pretargeting-configs
- **Geo ID Reference**: https://storage.googleapis.com/adx-rtb-dictionaries/geo-table.csv
- **Vertical ID Reference**: https://storage.googleapis.com/adx-rtb-dictionaries/publisher-verticals.txt

---

## Changelog Summary

| Version | Date | Key Changes |
|---------|------|-------------|
| 23.0 | Dec 8, 2025 | Modular router architecture: refactored main.py into 10 router modules |
| 22.0 | Dec 6, 2025 | Unified dashboard, schema alignment, Avg CPM badge |
| 21.0 | Dec 5, 2025 | RTB Funnel Analysis, Gmail auto-import |
| 12.0 | Dec 3, 2025 | Schema cleanup: `performance_data` → `rtb_daily` |
| 11.0 | Dec 2, 2025 | Decision Intelligence, evidence-based waste signals |
| 9.7 | Dec 1, 2025 | Onboarding flow, `/connect` page |
| 8.5 | Nov 30, 2025 | Seat hierarchy cleanup, performance optimization |

---

## Contact & Support

- **Documentation**: `/docs/` folder
- **CLI Help**: `python cli/qps_analyzer.py --help`
- **API Docs**: http://localhost:8000/docs

---

**Built for RTB bidders who want to improve QPS efficiency.**

*Last updated: December 8, 2025*
