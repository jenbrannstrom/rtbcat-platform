# Cat-Scan: an Optimizer for Google Authorized Buyers Signals

**Release Version:** from `VERSION` (SemVer) | **Runtime Build ID:** image tag / git SHA (example: `sha-a4c50dc`) | **Last Updated:** March 5, 2026

An open-source tool that helps RTB bidders improve QPS efficiency on Google Authorized Buyers. Cat-Scan learns which bid-request streams your bidder prefers, then fine-tunes in an attempt to send more of what works and less of what doesn't.

100% free and open source. Self-host on your own infrastructure.

---

## The Problem

Google Authorized Buyers delivers hundreds of billions of bid requests per day.

![QPS Funnel: how bid requests flow through the Google AB pipeline](https://docs.rtb.cat/assets/qps-funnel.svg)

Illustration: Google Authorized Buyers can send your bidder hundreds of billions of bid requests per day. You only want part of that firehose.

Authorized Buyers gives you up to 10 pretargeting configs to filter that real-time bidding firehose.

But there is no Reporting API for these metrics, so you cannot programmatically answer basic questions:

- Which signal (QPS) does your bidder actually prefer vs declining to bid on?
- Which pretargeting configs are performing and which are poorly configured?
- Which creatives are underperforming and blocking better signal?

You're left with CSV exports and manual analysis. That doesn't scale.

## What Cat-Scan Does

Cat-Scan sits alongside your Google AB seat. Because Google has no reporting API for this data, Cat-Scan ingests scheduled CSV reports sent to a dedicated Gmail address, parses them, and normalizes them into a queryable dataset.
Google does provide an Authorized Buyers API for creative metadata, which Cat-Scan uses directly.

From there, it:

1. **Imports CSV performance data** automatically from Gmail (yes, it's messy, but there's no API alternative)
2. **Syncs creatives** from the Authorized Buyers API
3. **Identifies waste** including [size gaps, config inefficiencies](https://docs.rtb.cat/04-analyzing-waste/), and underperforming segments
4. **Recommends pretargeting changes** based on bid rate, spend concentration, and win rate signals
5. **Pushes config changes** to Google AB with rollback and historical tracking
6. **Exposes an MCP interface** so you can connect your own AI to the data and algo engine

**Efficiency improvement:** We don't have enough data yet to quantify the percentage. We need more deployments and real-world testing.



### MMP / Tracking Platform Integration (Under Construction)

Optimisation improves significantly when conversion data (installs, tutorial completed, level unlocked, first deposit made, etc.) from your MMP is ingested. Supported platforms include AppsFlyer, Adjust, Voluum, and RedTrack. That way your AI has a much better understanding of what signal to optimise for. See the **[ROADMAP](ROADMAP.md)** for progress on this feature.



### How the Optimizer Thinks

Cat-Scan deduces what the media buyer is trying to achieve based on creatives, spend, CPM, and clicks. The core logic: follow the bids, follow the spend, kill the dead weight.

For the full breakdown of available signals, what's missing, and how we plan to close the gap, see **[docs/OPTIMIZATION_LOGIC.md](docs/OPTIMIZATION_LOGIC.md)**.

### Campaign Clustering

Cat-Scan groups creatives automatically based on shared destination URLs. This reveals patterns: which campaigns target the same audience, where spend is concentrated, and where config overlap creates waste. Manual grouping is also supported. Future: AI image recognition to identify creative language and surface localisation issues.

---

## Quick Start

```bash
# Clone and set up
git clone https://github.com/jenbrannstrom/rtbcat-platform.git
cd rtbcat-platform
./setup.sh

# Start services
./run.sh

# Open http://localhost:3000
```

> **Linux note:** Run `./run.sh` from a terminal, not by double-clicking in the file manager.

### Requirements

- Python 3.11+
- Node.js 18+
- ffmpeg (optional, for video thumbnails)

See **[INSTALL.md](INSTALL.md)** for detailed instructions.

### Security-First Install Sequence

Treat setup as four separate capabilities, enabled in order:

1. **Boot:** App starts, users can log in. Provision DB + runtime secrets only.
2. **Ingestion:** CSV import from Gmail. Set up Gmail OAuth credentials and scheduler.
3. **Analysis:** Metrics computed from imported data. Verify ingestion is working first.
4. **Google write access:** Live pretargeting changes via API. Only add AB service-account credentials when you're ready for this.

This keeps a fresh install useful but low-risk: no live Google write access until explicitly enabled.

**Automatable:** infra provisioning, startup, secret creation, bootstrap API call, scheduler wiring, health checks.
**Manual by design:** Gmail OAuth browser consent and Google-side permission approvals.

See **[AUTHENTICATION.md](docs/AUTHENTICATION.md)** for the bootstrap token flow.

---

## Features

| Feature | Description |
|---------|-------------|
| **Creative Sync** | Fetch all creatives from Google Authorized Buyers API |
| **Multi-Seat Support** | Manage multiple buyer accounts under one bidder |
| **Efficiency Analysis** | Identify size gaps, config inefficiencies, optimisation opportunities |
| **RTB Bidstream** | Visualise bid pipeline: bid_requests → bids → auctions_won → impressions |
| **Campaign Clustering** | Grouping by destination URL, region, advertiser, language |
| **CSV Import** | Auto-import performance data from scheduled Google reports via Gmail |
| **MCP Support** | Connect your own AI to Cat-Scan's data and algo engine |
| **Video Thumbnails** | Extract from VAST XML or generate via ffmpeg |
| **11 Languages** | EN, PL, ZH, RU, UK, ES, DA, FR, NL, HE, AR |
| **OAuth-Only Login** | Google OAuth via OAuth2 Proxy. No passwords stored. |
| **Access Control** | Per-user role + service account scoping |

### Dashboard

| Page | URL | Purpose |
|------|-----|---------|
| Home | `/` | Main dashboard with stats |
| Setup | `/setup` | Connect API, Gmail, configure retention |
| Efficiency Analysis | `/efficiency-analysis` | Size coverage, config performance |
| Creatives | `/creatives` | Browse synced creatives |
| Campaigns | `/campaigns` | Clustered campaign groups |
| Import | `/import` | Manual CSV upload |
| History | `/history` | Import history |
| Settings | `/settings` | General settings |
| Seats | `/settings/seats` | Buyer seat management |
| Admin | `/admin` | Admin dashboard |

---

## Architecture

```
                         ┌─────────────────────────────────────┐
                         │     Caddy (default) or Nginx        │
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
          │ Postgres (serving)           │                      │ Google Authorized            │
          │ Cloud SQL / local Postgres   │                      │ Buyers API                   │
          └──────────────────────────────┘                      └──────────────────────────────┘
                         ▲
                         │
          ┌──────────────────────────────┐
          │ GCS + BigQuery (raw_facts)   │
          └──────────────────────────────┘
```

### API Routers

| Router | Purpose |
|--------|---------|
| `system` | Health, stats, thumbnails |
| `creatives` | Creative management and sync |
| `seats` | Buyer seat discovery |
| `settings` | RTB endpoints, pretargeting |
| `analytics` | Efficiency analysis, RTB bidstream |
| `config` | Configuration and credentials |
| `gmail` | Auto-import from Gmail |
| `recommendations` | Optimisation recommendations |
| `retention` | Data retention policies |
| `uploads` | CSV file uploads |

Full API docs are available at `/docs` when running locally.

See **[DATA_MODEL.md](DATA_MODEL.md)** for the database schema and multi-bidder architecture.

---

## CSV Reports

Cat-Scan requires **5 separate CSV reports** from Google Authorized Buyers. This is because of field incompatibilities in Google's reporting system: you can't get pretargeting config IDs and bid request metrics in the same report.

> **Set timezone to UTC for all reports.** Non-UTC data is flagged as legacy.
>
> **Include Buyer account ID** in every report, or ensure the filename contains the seat ID.
>
> **Naming:** `catscan-{type}-{account_id}-{period}-UTC`
>
> **Create in:** Google Authorized Buyers → Reporting → Scheduled Reports

### The 5 Reports

| # | Report | Purpose | Key Fields | Table |
|---|--------|---------|------------|-------|
| 1 | **catscan-bidsinauction** | Bid metrics by creative | Creative ID, Bids in auction, Auctions won | `rtb_daily` |
| 2 | **catscan-quality** | Quality and config data | Pretargeting config (Billing ID), Reached queries, Impressions | `rtb_daily` |
| 3 | **catscan-pipeline-geo** | Bidstream by region | Country, Bid requests, Bids | `rtb_bidstream` |
| 4 | **catscan-pipeline** | Bidstream by publisher | Publisher ID + Bid metrics | `rtb_bidstream` |
| 5 | **catscan-bid-filtering** | Bid filtering reasons | Bid filtering status, Filtered bids | `rtb_bid_filtering` |

### Why 5 Reports?

Google's limitation: "Billing ID is not compatible with Bid requests."

- To get pretargeting config + spend → you lose bid request metrics
- To get bid request metrics → you lose pretargeting config
- Cat-Scan joins reports #1 and #2 on (Day, Creative ID) to reconstruct per-config bidstream metrics

### Data Quality Flags

All data has a `data_quality` column:
- **`production`**: UTC data (real analytics)
- **`legacy`**: Pre-UTC data (wrong timezone, development only)
- **`sample`**: Manually marked sample data

> Run migrations 016 and 017 to add data_quality support and rename `rtb_funnel` to `rtb_bidstream`.

### Report Field Reference

**Report 1: Bids in Auction:**
```
Dimensions: Day, Hour, Buyer account ID, Creative ID, Region, Platform, Publisher ID
Metrics: Bids, Bids in auction, Auctions won
```

**Report 2: Quality:**
```
Dimensions: Day, Hour, Buyer account ID, Pretargeting config (Billing ID), Creative ID, Region, Platform
Metrics: Reached queries, Impressions, Clicks, Spend
```

**Report 3: Bidstream Geo:**
```
Dimensions: Day, Hour, Buyer account ID, Region
Metrics: Bid requests, Inventory matches, Reached queries, Bids, Bids in auction, Auctions won, Impressions
```

**Report 4: Bidstream Publishers:**
```
Dimensions: Day, Hour, Buyer account ID, Region, Publisher ID, Publisher name
Metrics: Same as Report 3
```

**Report 5: Bid Filtering:**
```
Dimensions: Day, Hour, Buyer account ID, Bid filtering status, Creative ID
Metrics: Filtered bids
```

> **Efficiency calculation:** Impressions / Reached Queries

---

## Importer CLI

```bash
# Unified CSV importer (recommended)
./venv/bin/python -m importers.unified_importer /path/to/report.csv
```

For importer internals and supported report types, see [`importers/README.md`](importers/README.md).

---

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/creatives` | List creatives |
| POST | `/collect/sync` | Sync from Google API |
| GET | `/campaigns` | List campaigns |
| POST | `/campaigns/auto-cluster` | Clustering |
| GET | `/analytics/home/funnel` | Home funnel analytics |
| POST | `/performance/import-csv` | Import CSV |

Full API docs: `http://localhost:8000/docs`

---

## Deployment

### CI/CD (GitHub Actions)

Pushing to `unified-platform` triggers: build → push to Artifact Registry → pull on VM.

```bash
# Deploy a pinned image tag
cd /opt/catscan
echo "IMAGE_TAG=sha-<commit>" | sudo tee -a .env
sudo docker compose -f docker-compose.gcp.yml pull
sudo docker compose -f docker-compose.gcp.yml up -d --no-build
```

### Production Stack

```
Internet → Caddy or Nginx (443/HTTPS) → Dashboard (3000) + API (8000)
```

Caddy is the default reverse proxy with automatic HTTPS. Nginx is supported as an alternative.

<details>
<summary>Nginx setup</summary>

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

`/etc/nginx/sites-available/catscan`:
```nginx
server {
    listen 80;
    server_name your-domain.com;
    client_max_body_size 200m;

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

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/catscan /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d your-domain.com
```

</details>

### Systemd

```bash
sudo systemctl start catscan-api catscan-dashboard
sudo systemctl status catscan-api catscan-dashboard
sudo journalctl -u catscan-api -f
```

### Docker

```bash
docker compose build api
docker compose up -d api
```

### Manual Startup

If `./run.sh` doesn't work:

```bash
# Terminal 1: API
./venv/bin/python -m uvicorn api.main:app --host 0.0.0.0 --port 8000

# Terminal 2: Dashboard
cd dashboard && npm run dev
```

> Use `./venv/bin/python -m uvicorn` instead of `uvicorn` directly. It's more reliable across environments (Flatpak, certain shells).

See **[docs/GCP_CREDENTIALS_SETUP.md](docs/GCP_CREDENTIALS_SETUP.md)** for full deployment instructions.

---

## Configuration

### Data Directory

```
~/.catscan/
├── thumbnails/             # Generated video thumbnails
├── imports/                # Downloaded CSV reports
└── credentials/
    └── google-credentials.json
```

### Environment Variables

Create `.env` in the project root:

```bash
GOOGLE_APPLICATION_CREDENTIALS=~/.catscan/credentials/google-credentials.json

# Postgres (required)
POSTGRES_DSN=postgresql://user:pass@host:5432/rtbcat_serving
POSTGRES_SERVING_DSN=postgresql://user:pass@host:5432/rtbcat_serving

# Pipeline (CSV → Parquet → GCS → BigQuery)
CATSCAN_PIPELINE_ENABLED=true
CATSCAN_GCS_BUCKET=your-bucket
RAW_PARQUET_BUCKET=your-bucket
CATSCAN_BQ_DATASET=rtbcat_analytics
CATSCAN_BQ_PROJECT=your-project
```

Postgres is required. The legacy `docker-compose.simple.yml` is deprecated.

---

## Documentation

| Document | Purpose |
|----------|---------|
| **[INSTALL.md](INSTALL.md)** | Installation guide |
| **[SECURITY.md](SECURITY.md)** | Vulnerability reporting policy + deployment security guide |
| **[DATA_MODEL.md](DATA_MODEL.md)** | Database schema (41 tables) |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | System architecture |
| **[docs/OPTIMIZATION_LOGIC.md](docs/OPTIMIZATION_LOGIC.md)** | How Cat-Scan analyses QPS signals |
| **[docs/LOCAL_DEV_DATABASE.md](docs/LOCAL_DEV_DATABASE.md)** | Local DB subset workflow |
| **[METRICS_GUIDE.md](METRICS_GUIDE.md)** | RTB metrics reference |
| **[docs/VERSIONING.md](docs/VERSIONING.md)** | Release and build version policy |
| **[ROADMAP.md](ROADMAP.md)** | Planned features and known bugs |
| **[CHANGELOG.md](CHANGELOG.md)** | Version history |
| **[CONTRIBUTING.md](CONTRIBUTING.md)** | Contribution workflow |
| **[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)** | Community standards |

---

## Security

**Code is public. Data and credentials are private.**

| Keep Public | Keep Private (gitignored) |
|-------------|---------------------------|
| Application code | `.env` (credentials) |
| Docker configs | `terraform.tfvars` (secrets) |
| `*.example` files | `*.json` (service account keys) |
| Documentation | `~/.catscan/` (database, imports) |

```bash
# Copy example files. Never commit the real versions.
cp .env.example .env
cp terraform/terraform.tfvars.example terraform/terraform.tfvars

# Verify secrets aren't tracked
git ls-files | grep -E '\.(env|tfstate|db)$|terraform\.tfvars'
# Should return empty
```

Use GitHub Secrets for CI/CD. See **[SECURITY.md](SECURITY.md)**.

---

## Status

### Production Ready

- Creative sync from Google API
- Multi-seat buyer account support
- Efficiency analysis with recommendations
- CSV import (CLI and UI) with 5 report types
- Gmail auto-import
- Campaign clustering
- RTB bidstream visualisation
- Video thumbnail generation
- UTC timezone standardisation
- Data quality flagging
- Per-config bidstream metrics via JOIN strategy

See **[ROADMAP.md](ROADMAP.md)** for what's planned.

---

## Known Issues

| Issue | Fix |
|-------|-----|
| Port 8000 stuck | `sudo lsof -ti:8000 \| xargs -r sudo kill -9` |
| No video thumbnails | Check ffmpeg install and run a thumbnail refresh from `/settings/system` |
| Dashboard not updating | `npm run build` |
| uvicorn "module not found" | Use `./venv/bin/python -m uvicorn` instead |

---

## Development

```bash
./venv/bin/black . && ./venv/bin/isort . && ./venv/bin/ruff check .
./venv/bin/pytest tests/ -v
./venv/bin/mypy .
```

---

## Versioning

- **Release version:** `VERSION` file (`X.Y.Z`), published with annotated git tag `vX.Y.Z`
- **Runtime build ID:** immutable image tag / commit SHA (`sha-<short_sha>`)
- **Health/API identity:** `/health` exposes `release_version`, `version` (build ID), and `git_sha`

See **[docs/VERSIONING.md](docs/VERSIONING.md)** for the enforced release flow.

---

## License

MIT License. See [LICENSE](LICENSE).

---

Built for RTB bidders who want to stop wasting QPS.
