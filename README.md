# Cat-Scan QPS Optimizer & Creative Intelligence Tool

**Version:** 0.9.2 | **Runtime Build ID:** `sha-<gitsha>` | **Last Updated:** February 2026

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





*The Logic:*

The advertiser's profit = what they earn from ads − what they spend on ads − what it costs to 
  run the operation.
                                                                                                
  We can't see their earnings. So the question becomes: from what we CAN see, which signals tell
   us "this traffic is making them money" vs "this traffic is costing them money"?

  Here's what we have today, ranked by how useful each actually is:

  What we have and what it tells us:

  Metric: Bids / Bid Rate
  What it tells us: "The bidder chose to bid on this traffic." Their own system — which knows
    their campaigns, budgets, and targeting — decided this was worth spending money on.
  Usefulness for profit optimization: High. This is the strongest signal we have. If the bidder
    bids on 80% of traffic from publisher X but only 2% from publisher Y, the bidder is telling
    us publisher X is valuable. We should send more like X, less like Y.
  ────────────────────────────────────────
  Metric: Win Rate
  What it tells us: "They bid AND won." They valued this traffic enough to outbid competitors.
  Usefulness for profit optimization: High. High win rate = they're pricing aggressively = they
    really want this inventory. Low win rate = either they're being outbid (price sensitivity)
  or
     the auction is too competitive (diminishing returns).
  ────────────────────────────────────────
  Metric: Spend concentration
  What it tells us: Where the money actually goes. If 90% of spend lands on 3 out of 10 configs,

    those 3 are where the bidder sees value.
  Usefulness for profit optimization: High. Money doesn't lie. Follow the spend.
  ────────────────────────────────────────
  Metric: Bid-to-win ratio
  What it tells us: They bid but lost. How often?
  Usefulness for profit optimization: Medium-High. A segment where they bid 10,000 times but
  only
     win 100 means they want this traffic but can't afford it at market price. That's useful —
  it
     means they value it, they're just being outcompeted. Might be worth increasing QPS to give
    them more shots.
  ────────────────────────────────────────
  Metric: Reached but not bid
  What it tells us: Traffic reached the bidder, bidder said "no thanks."
  Usefulness for profit optimization: Medium. Tells us the bidder doesn't want it, but not WHY.
    Could be budget exhaustion (temporary), frequency cap (user-specific), or no matching
    campaign (structural). Without the reason, we can only observe the pattern.
  ────────────────────────────────────────
  Metric: CTR
  What it tells us: Users clicked.
  Usefulness for profit optimization: Medium. Means the creative resonated in that placement.
  But
     as we discussed — clicks can be junk. Useful in combination with other signals, not alone.
  ────────────────────────────────────────
  Metric: Viewability
  What it tells us: The ad was actually seen by a human.
  Usefulness for profit optimization: Medium. A non-viewable impression has zero chance of
    generating profit. Cutting non-viewable inventory is free money.
  ────────────────────────────────────────
  Metric: IVT / Fraud rate
  What it tells us: Traffic is bots, not humans.
  Usefulness for profit optimization: Medium. Obvious — zero bots will ever buy a product. But
    fraud rates are usually low enough that this is a hygiene issue, not a primary optimization
    lever.
  ────────────────────────────────────────
  Metric: Spend trend over time
  What it tells us: Increasing or decreasing?
  Usefulness for profit optimization: Medium. An advertiser ramping up spend is finding profit.
    One pulling back is not. Useful for confidence scoring, not  for segment-level optimization.
  ────────────────────────────────────────
  Metric: Impressions without clicks
  What it tells us: Ad shown, nobody cared.
  Usefulness for profit optimization: Low-Medium. Could be brand awareness (intentional), could
    be bad placement. Ambiguous without knowing campaign intent.

  The gap — what we're missing that would actually change things:

  Missing metric: No-bid reason
  Why it matters: If we knew WHY the bidder passes on 99% of traffic, we could stop sending it.
    "Floor too high" → target cheaper publishers. "Budget exhausted" → reduce QPS in late-day
    hours. "No matching campaign for this geo" → exclude that geo from pretargeting. This single

    data point would be more valuable than everything else combined.
  Source: Bidder logs (CSV export)
  ────────────────────────────────────────
  Missing metric: Bid price per segment
  Why it matters: The bidder's own assessment of what traffic is worth, in dollars. If they bid
    $3 CPM on Philippines Android gaming apps but $0.05 on Brazil desktop news sites, we know
    exactly where they see profit.
  Source: Bidder logs (CSV export)
  ────────────────────────────────────────
  Missing metric: Post-click outcome
  Why it matters: Did the click become money? An install, a deposit, a purchase? This is the
    ultimate signal. Everything else is proxy.
  Source: MMP postback (Phase 2 — built, needs customer to connect)

  The honest answer:

  With what we have TODAY (no bidder data, no MMP connection), the best optimization we can do
  is:

  1. Follow the bids. Shift QPS toward segments where the bidder actually bids. If they ignore
    99% of traffic from a config, that config's QPS is wasted.
  2. Follow the spend. Configs and geos where the advertiser spends the most are where they see
    value. Protect those. Starve the ones with zero spend.
  3. Kill the dead weight. Three configs with zero traffic, zero bids, zero impressions — those
    are consuming QPS that could go to performing configs.
  4. Cut fraud and non-viewable inventory. Not the biggest lever, but it's free improvement.

  The moment a customer connects their MMP or gives us a bid-price CSV dump, everything changes
  — we go from "follow the proxy signals" to "optimize for actual outcomes."



*Missing Gold:*

What data does the bidder have that we don't?

  The bidder knows things Google never tells us in their CSV reports:
  - "I bid $1.20 on this request" (we never see bid prices)
  - "I declined this request because the floor was too high" (we never see no-bid reasons)
  - "I've used 80% of today's budget" (we never see budget status)

  This data would be gold for Cat-Scan's optimizer — if we knew why the bidder said no to 95% of
   requests, we could tune pretargeting to stop sending those requests in the first place.

We will build an ingestion part for anyone that sees the benefit of adding the bidder's metrics. Then CatScan can perform much better

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

### Security-First Install Sequence (First Principles)

Treat setup as four separate capabilities:

1. **Boot capability**: App can start and users can log in.
2. **Ingestion capability**: App can import daily CSV performance data from Gmail.
3. **Analysis capability**: App can compute metrics from imported data.
4. **Google write capability**: App can modify live Authorized Buyers pretargeting via API.

For safety-first single-tenant installs, enable them in this order:

1. **Provision infrastructure and minimum secrets** (DB + runtime secrets only).
2. **Start app without AB service-account key** so the app is operational but cannot change Google RTB configs.
3. **Bootstrap first admin explicitly** using the bootstrap token flow (production) in **[AUTHENTICATION.md](docs/AUTHENTICATION.md)**.
4. **Set up daily CSV ingestion from Gmail**:
   - create Gmail OAuth client credentials,
   - run Gmail OAuth authorization (`scripts/gmail_auth.py`) once,
   - upload/store Gmail secrets,
   - configure scheduler/import label.
5. **Verify ingestion is working** (new daily CSV emails are imported and visible in dashboard metrics).
6. **Only then add AB API credentials** (service-account JSON) when you are ready to allow live Google config actions (pause/activate/apply changes).

What can be automated vs manual:

- **Automatable**: infra provisioning, startup, secret creation/upload, bootstrap API call, scheduler wiring, health checks.
- **Manual (by design)**: Gmail OAuth browser consent and any Google-side permission approvals.

This sequence keeps a fresh install useful but low-risk: no live Google write access until explicitly enabled.

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

MCP Chrome setup (browser-based inspection) uses `scripts/chrome-cdp.sh` and `scripts/mcp-chromium-cdp.sh`.

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

See **[DATA_MODEL.md](DATA_MODEL.md)** for the canonical schema and multi-bidder architecture documentation.

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
| 2 | **catscan-quality** | Quality/config data | Pretargeting config (Billing ID), Reached queries, Impressions | `rtb_daily` |
| 3 | **catscan-pipeline-geo** | Bidstream by region | Country, Bid requests, Bids | `rtb_bidstream` |
| 4 | **catscan-pipeline** | Bidstream by publisher | Publisher ID + Bid metrics | `rtb_bidstream` |
| 5 | **catscan-bid-filtering** | Bid filtering reasons | Bid filtering status, Filtered bids | `rtb_bid_filtering` |

### Why 5 Reports?

Google's limitation: *"Billing ID is not compatible with [Bid requests]..."*

- In Cat-Scan UI/API, **Billing ID** is treated as **Pretargeting config ID** (`billing_id`)
- To get **Pretargeting config (Billing ID) + spend** → you lose bid request metrics
- To get **Bid request metrics** → you lose Billing ID
- **JOIN Strategy:** Cat-Scan joins CSV #1 and #2 on (Day, Creative ID) to reconstruct per-pretargeting-config (`billing_id`) bidstream metrics

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
Dimensions: Day, Hour, Buyer account ID, Pretargeting config (Billing ID), Creative ID, Region, Platform
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
# Smart import (auto-detects report type) - RECOMMENDED
./venv/bin/python -m qps.smart_importer /path/to/any-report.csv

# Show CSV report creation instructions
./venv/bin/python -m qps.smart_importer --help

# Import bidstream CSV specifically
./venv/bin/python -m qps.funnel_importer /path/to/bidstream-report.csv

# CLI tool (alternative interface)
PYTHONPATH=. ./venv/bin/python -m cli.qps_analyzer import /path/to/report.csv
PYTHONPATH=. ./venv/bin/python -m cli.qps_analyzer validate /path/to/report.csv
PYTHONPATH=. ./venv/bin/python -m cli.qps_analyzer summary
PYTHONPATH=. ./venv/bin/python -m cli.qps_analyzer full-report --days 7
PYTHONPATH=. ./venv/bin/python -m cli.qps_analyzer generate-thumbnails --limit 100
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
# Deploy a pinned image tag (recommended)
cd /opt/catscan
echo "IMAGE_TAG=sha-<commit>" | sudo tee -a .env
sudo docker compose -f docker-compose.gcp.yml pull
sudo docker compose -f docker-compose.gcp.yml up -d --no-build
```

See **[docs/GCP_CREDENTIALS_SETUP.md](docs/GCP_CREDENTIALS_SETUP.md)** for full CI/CD setup.

### Production Architecture (Caddy by Default, Nginx Optional)

For production, the docker stack uses Caddy as the reverse proxy with automatic HTTPS. Nginx is still supported as an optional alternative:

```
Internet → Caddy or nginx (443/HTTPS) → Dashboard (3000) + API (8000)
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
├── thumbnails/             # Generated video thumbnails
├── imports/                # Downloaded CSV reports
└── credentials/
    └── google-credentials.json
```

### Environment Variables

Create `.env` in the project root:

```bash
GOOGLE_APPLICATION_CREDENTIALS=~/.catscan/credentials/google-credentials.json

# Postgres serving (required)
POSTGRES_DSN=postgresql://user:pass@host:5432/rtbcat_serving
POSTGRES_SERVING_DSN=postgresql://user:pass@host:5432/rtbcat_serving

# Pipeline (CSV → Parquet → GCS → BigQuery)
CATSCAN_PIPELINE_ENABLED=true
CATSCAN_GCS_BUCKET=your-bucket
RAW_PARQUET_BUCKET=your-bucket
CATSCAN_BQ_DATASET=rtbcat_analytics
CATSCAN_BQ_PROJECT=your-project
```

### Local Development Note

Postgres is required for serving/analytics. The legacy `docker-compose.simple.yml`
is deprecated; use the Postgres-based compose files instead.

---

## Documentation

| Document | Purpose |
|----------|---------|
| **[INSTALL.md](INSTALL.md)** | Detailed installation guide |
| **[docs/SECURITY.md](docs/SECURITY.md)** | Security guide for forks and deployments |
| **[DATA_MODEL.md](DATA_MODEL.md)** | Complete database schema (41 tables) |
| **[ARCHITECTURE.md](ARCHITECTURE.md)** | System architecture |
| **[docs/LOCAL_DEV_DATABASE.md](docs/LOCAL_DEV_DATABASE.md)** | Local DB subset workflow + schema safety gates |
| **[METRICS_GUIDE.md](METRICS_GUIDE.md)** | RTB metrics and optimization reference |
| **[ROADMAP.md](ROADMAP.md)** | Planned features and known bugs |
| **[CHANGELOG.md](CHANGELOG.md)** | Version history and migration notes |

---

## Security (For Forks & Partners)

**Code is public. Data and credentials are private.**

When forking Cat-Scan for your organization:

| Keep Public | Keep Private (gitignored) |
|-------------|---------------------------|
| Application code | `.env` (credentials) |
| Docker configs | `terraform.tfvars` (secrets) |
| `*.example` files | `*.json` (service account keys) |
| Documentation | `~/.catscan/` (database, imports) |

### Quick Security Checklist

1. **Copy example files** - Never commit the real versions:
   ```bash
   cp .env.example .env
   cp terraform/terraform.tfvars.example terraform/terraform.tfvars
   ```

2. **Verify gitignore** - Ensure secrets aren't tracked:
   ```bash
   git ls-files | grep -E '\.(env|tfstate|db)$|terraform\.tfvars'
   # Should return empty
   ```

3. **Use GitHub Secrets** - For CI/CD, never hardcode in workflow files

See **[docs/SECURITY.md](docs/SECURITY.md)** for the complete security guide.

---

## Project Status

**Open Source:** Self-host on your own infrastructure

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
- Per-pretargeting-config (`billing_id`) bidstream metrics via JOIN strategy

### Roadmap

See **[ROADMAP.md](ROADMAP.md)** for planned features and known bugs.

---

## Known Issues

| Issue | Workaround |
|-------|------------|
| Port 8000 stuck | `sudo lsof -ti:8000 \| xargs -r sudo kill -9` |
| No video thumbnails | Run `PYTHONPATH=. ./venv/bin/python -m cli.qps_analyzer generate-thumbnails` |
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

Cat-Scan uses two version identifiers:

- `Release version` (human-readable): `VERSION` file (current: `0.9.2`)
- `Runtime build ID` (source of truth in deployed environments): image tag / git SHA (for example `sha-3b96ce6`)

In production, the UI footer and `/health` should show the SHA build ID. Use that value for exact deploy traceability.

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
