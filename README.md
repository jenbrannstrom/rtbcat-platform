# Cat-Scan QPS Optimizer & Creative Intelligence Tool

**Version:** 0.9.0 | **Phase:** Production | **Last Updated:** January 2026

An **open-source** QPS optimization tool for Google Authorized Buyers. Cat-Scan helps RTB bidders improve QPS efficiency by learning which data-streams the bidder prefers to bid on, and fine-tune Pretargeting to allow more bid-requests through to the bidder for preferred placements/apps.

**100% free and open source.** Self-host on your own infrastructure or use our hosted version at scan.rtb.cat.

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
| **RTB Bidstream** | Visualize bid pipeline: bid_requests → bids → auctions_won → impressions |
| **Campaign Clustering** | AI-powered grouping by destination URL, region, advertiser, language |
| **CSV Import** | Auto-import performance data from Google reports |
| **MCP Support** | APIs to enable MCP access for your own choice of AI |
| **Video Thumbnails** | Visualize creatives clearly: extract from VAST XML or generate via ffmpeg |
| **Multi-Language** | Internationalization (i18n) with 11 languages: EN, PL, ZH, RU, UK, ES, DA, FR, NL, HE, AR |
| **OAuth-Only Login** | Google OAuth via OAuth2 Proxy (no passwords stored) |
| **Per-User Access Control** | Role + service account access scoping |

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
                         ┌─────────────────────────────────────┐
                         │         Nginx Reverse Proxy         │
                         │         (Port 443 - HTTPS)          │
                         │         SSL via Let's Encrypt       │
                         └─────────────────────────────────────┘
                                          │
                    ┌─────────────────────┴─────────────────────┐
                    │                                           │
                    ▼                                           ▼
┌─────────────────────────────────────┐    ┌─────────────────────────────────────┐
│   Next.js Dashboard (Port 3000)     │    │     FastAPI Backend (Port 8000)     │
│   /                                 │    │     /api/*                          │
└─────────────────────────────────────┘    └─────────────────────────────────────┘
                                                      │
                         ┌────────────────────────────┴────────────────────────────┐
                         │                                                         │
                         ▼                                                         ▼
          ┌──────────────────────────────┐                      ┌──────────────────────────────┐
          │ SQLite Database              │                      │ Google Authorized            │
          │ ~/.catscan/catscan.db        │                      │ Buyers API                   │
          └──────────────────────────────┘                      └──────────────────────────────┘
```

### API Routers

| Router | Purpose |
|--------|---------|
| `system` | Health, stats, thumbnails |
| `creatives` | Creative management & sync |
| `seats` | Buyer seat discovery |
| `settings` | RTB endpoints, pretargeting |
| `analytics` | Efficiency analysis, RTB bidstream |
| `config` | Configuration & credentials |
| `gmail` | Auto-import from Gmail |
| `recommendations` | AI recommendations |
| `retention` | Data retention policies |
| `uploads` | CSV file uploads |

### Database Schema

See **[DATA_MODEL.md](DATA_MODEL.md)** for the complete 41-table schema and multi-bidder architecture documentation.

---

## CSV Format Requirements

Cat-Scan requires **5 separate CSV reports** from Google Authorized Buyers due to field incompatibilities in Google's reporting system.

> **CRITICAL:** Set timezone to **UTC** for ALL reports! Non-UTC data is marked as legacy.
>
> **REQUIRED:** Include **Buyer account ID** in every report, or ensure the filename contains the seat ID.
>
> **Naming Convention:** `catscan-{type}-{account_id}-{period}-UTC`
> Example: `catscan-pipeline-1487810529-yesterday-UTC`

> **Create these reports in Google Authorized Buyers: Reporting → Scheduled Reports**

### The Required Reports

| # | Report | Purpose | Key Fields | Table |
|---|--------|---------|------------|-------|
| 1 | **catscan-bidsinauction** | Bid metrics by creative | Creative ID, Bids in auction, Auctions won | `rtb_daily` |
| 2 | **catscan-quality** | Quality/billing data | Billing ID, Reached queries, Impressions | `rtb_daily` |
| 3 | **catscan-pipeline-geo** | Bidstream by region | Country, Bid requests, Bids | `rtb_bidstream` |
| 4 | **catscan-pipeline** | Bidstream by publisher | Publisher ID + Bid metrics | `rtb_bidstream` |
| 5 | **catscan-bid-filtering** | Bid filtering reasons | Bid filtering status, Filtered bids | `rtb_bid_filtering` |

### Why 5 Reports?

Google's limitation: *"Billing ID is not compatible with [Bid requests]..."*

- To get **Billing ID + spend** → you lose bid request metrics
- To get **Bid request metrics** → you lose Billing ID
- **JOIN Strategy:** Cat-Scan joins CSV #1 and #2 on (Day, Creative ID) to reconstruct per-billing_id bidstream metrics

### Data Quality Flags

All data has a `data_quality` column:
- **`production`** - UTC data (real analytics)
- **`legacy`** - Pre-UTC data (wrong timezone, keep for development only)
- **`sample`** - Manually marked sample data

> **Note:** Run migrations 016 and 017 to add data_quality support and rename the legacy `rtb_funnel` table to `rtb_bidstream`.

### Quick Reference

**Report 1 - Bids in Auction (catscan-bidsinauction):**
```
Dimensions: Day, Hour, Buyer account ID, Creative ID, Region, Platform, Publisher ID
Metrics: Bids, Bids in auction, Auctions won
```

**Report 2 - Quality (catscan-quality):**
```
Dimensions: Day, Hour, Buyer account ID, Billing ID, Creative ID, Region, Platform
Metrics: Reached queries, Impressions, Clicks, Spend
```

**Report 3 - Bidstream Geo (catscan-pipeline-geo):**
```
Dimensions: Day, Hour, Buyer account ID, Region
Metrics: Bid requests, Inventory matches, Reached queries, Bids, Bids in auction, Auctions won, Impressions
```

**Report 4 - Bidstream Publishers (catscan-pipeline):**
```
Dimensions: Day, Hour, Buyer account ID, Region, Publisher ID, Publisher name
Metrics: Same as Report 3
```

**Report 5 - Bid Filtering (catscan-bid-filtering):**
```
Dimensions: Day, Hour, Buyer account ID, Bid filtering status, Creative ID
Metrics: Filtered bids
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

# Import bidstream CSV specifically
./venv/bin/python -m qps.funnel_importer /path/to/bidstream-report.csv

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

### Production Deployment (CI/CD)

Cat-Scan uses GitHub Actions for CI/CD. Pushing to `unified-platform` triggers:

1. **Build** — Docker images built in GitHub Actions
2. **Push** — Images pushed to Google Artifact Registry
3. **Deploy** — Pull images on VM (no building on VM)

```bash
# Deploy latest (on VM)
cd /opt/catscan
sudo docker-compose -f docker-compose.gcp.yml pull
sudo docker-compose -f docker-compose.gcp.yml up -d
```

See **[docs/GCP_CREDENTIALS_SETUP.md](docs/GCP_CREDENTIALS_SETUP.md)** for full CI/CD setup.

### Production Architecture (Nginx + SSL)

For production, use nginx as a reverse proxy with Let's Encrypt SSL:

```
Internet → nginx (443/HTTPS) → Dashboard (3000) + API (8000)
```

**Setup:**
```bash
# Install nginx and certbot
sudo apt install -y nginx certbot python3-certbot-nginx

# Create nginx config
sudo nano /etc/nginx/sites-available/catscan
```

**Nginx config (`/etc/nginx/sites-available/catscan`):**
```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Allow large CSV uploads for imports (avoid 413 errors)
    client_max_body_size 200m;

    # API routes
    location /api/ {
        proxy_pass http://127.0.0.1:8000/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Cookie $http_cookie;
        proxy_pass_header Set-Cookie;
    }

    # Dashboard (default)
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

**Enable and get SSL:**
```bash
sudo ln -s /etc/nginx/sites-available/catscan /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

# Get SSL certificate
sudo certbot --nginx -d your-domain.com
```

See **[docs/GCP_CREDENTIALS_SETUP.md](docs/GCP_CREDENTIALS_SETUP.md)** for complete GCP deployment instructions.

### Systemd Services

```bash
# Start services
sudo systemctl start catscan-api catscan-dashboard
sudo systemctl status catscan-api catscan-dashboard

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
| **[INSTALL.md](INSTALL.md)** | Detailed installation guide |
| **[docs/GCP_CREDENTIALS_SETUP.md](docs/GCP_CREDENTIALS_SETUP.md)** | GCP VM deployment with nginx + SSL |
| **[DATA_MODEL.md](DATA_MODEL.md)** | Complete database schema (41 tables) |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | System architecture |
| **[METRICS_GUIDE.md](METRICS_GUIDE.md)** | RTB metrics and optimization reference |
| **[ROADMAP.md](ROADMAP.md)** | Planned features and known bugs |

---

## Project Status

**Deployed:** Live at `scan.rtb.cat` on GCP (Google Cloud Platform)

### What Works (Production Ready)

- Creative sync from Google API
- Multi-seat buyer account support
- Efficiency analysis with recommendations
- CSV import (CLI and UI) with 5 report types
- Gmail auto-import (Cloud Scheduler or systemd timer)
- Campaign clustering
- RTB bidstream visualization (bid_requests → impressions)
- Video thumbnail generation
- UTC timezone standardization
- Data quality flagging (legacy vs production data)
- Per-billing_id bidstream metrics via JOIN strategy

### Roadmap

See **[ROADMAP.md](ROADMAP.md)** for planned features and known bugs.

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

## Versioning

The app version is managed via a single `VERSION` file at the repository root.

**To bump the version:**
1. Edit the `VERSION` file with the new version (e.g., `0.9.1`)
2. Commit and push - deployment automatically uses the new version

The version is displayed in:
- API health endpoint (`/health`)
- API docs (`/docs`)
- Dashboard sidebar footer

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
