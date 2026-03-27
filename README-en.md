# Cat-Scan

![Google Authorized Buyers](https://img.shields.io/badge/Google%20Authorized%20Buyers-compatible-4285F4?logo=google&logoColor=white)
![Version](https://img.shields.io/badge/version-v0.9.4-blue)
![License](https://img.shields.io/badge/license-MIT-brightgreen)
![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![Node.js](https://img.shields.io/badge/node.js-18%2B-339933?logo=nodedotjs&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-frontend-000000?logo=nextdotjs&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-14%2B-4169E1?logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)
![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)
[![Stars](https://gitee.com/jenbrannstrom/rtbcat-platform/badge/star.svg)](https://gitee.com/jenbrannstrom/rtbcat-platform/stargazers)
[![Forks](https://gitee.com/jenbrannstrom/rtbcat-platform/badge/fork.svg)](https://gitee.com/jenbrannstrom/rtbcat-platform/members)

[中文](README.md)

Cat-Scan is a QPS control plane for Google Authorized Buyers.

It does not replace the bidder. It gives the bidder and the operator a better view of what is happening, then helps adjust the levers Google actually exposes: pretargeting configs, seat-level traffic mix, creative hygiene, and reporting.

Google already does a lot of waste reduction on its side. That is real. Cat-Scan exists for the last layer you can still control on your side.

What it does today:
- imports Google Authorized Buyers CSV reports from Gmail or manual upload
- syncs creatives, seats, endpoints, and pretargeting data from the Authorized Buyers API
- shows QPS, bidstream, publisher, geo, size, and config-level waste signals
- groups creatives into campaigns from destination patterns
- recommends and applies pretargeting changes, with rollback and audit history
- supports multi-seat operation with user roles and seat-scoped access

What it does not do today:
- it does not have enough public deployment data to claim a typical percentage improvement
- it does not magically know advertiser value or lifetime value without external conversion data
- it does not replace bidder-side logic; it complements it

## The problem in one picture

![QPS Funnel](https://docs.rtb.cat/assets/qps-funnel.svg)

## Why this exists

Authorized Buyers gives you a lot of traffic and only a limited set of controls.

The bidder sees the firehose it receives. Google sees its own side of the exchange. Neither side gives you a clean control plane for understanding where QPS is wasted, where spend actually concentrates, or which pretargeting configs are carrying dead weight.

Cat-Scan fills that gap.

The current optimizer logic is simple on purpose:
- follow the bids
- follow the spend
- cut dead weight
- treat post-click data as the missing signal until it is actually connected

That logic is described in [docs/OPTIMIZATION_LOGIC.md](docs/OPTIMIZATION_LOGIC.md).

## Current scope

### Built and usable
- Gmail and manual CSV ingestion for the five core Authorized Buyers report types
- creative sync from Authorized Buyers
- QPS analysis by publisher, geo, and size
- config and campaign views
- pretargeting recommendations, apply flow, rollback, and audit trail
- import history, data freshness, and retention controls
- multi-user auth with seat-scoped access
- campaign clustering from destination URLs and creative metadata
- click-macro audit and AppsFlyer readiness diagnostics

### Built but optional
- AI-assisted language detection and geo-linguistic mismatch analysis in the creative modal
- provider choice for language analysis (Gemini, Claude, or Grok)
- these features require explicit provider configuration and are disabled by default in production deploys

### Under active build
- conversion ingestion and attribution, with AppsFlyer first
- stronger optimizer decisions once conversion and value data are connected

## What it looks like

### QPS and efficiency at a glance

See allocated versus observed QPS per config, and overall utilization across your seat.

<p float="left">
<img src="docs/screenshots/allocated-vs-actual-qps.png" width="320" alt="Allocated vs actual QPS per pretargeting config" />
<img src="docs/screenshots/utilization.png" width="380" alt="Seat-level utilization and efficiency summary" />
</p>

### Win rates and waste per config

Each pretargeting config shows reached queries, win rate, and waste percentage. Edit QPS limits or pause configs directly.

<p float="left">
<img src="docs/screenshots/win-rates.png" width="320" alt="Win rates and waste by pretargeting config" />
<img src="docs/screenshots/edit-pause-qps.png" width="480" alt="Edit QPS limits and pause configs inline" />
</p>

### Creative management

Browse synced creatives by approval status, spend tier, and format. Filter to disapproved creatives to find what is blocking signal.

<p float="left">
<img src="docs/screenshots/creative-metrics.png" width="420" alt="Creative grid with spend, impressions, and approval status" />
<img src="docs/screenshots/disapproved-creatives.png" width="380" alt="Disapproved creatives filtered view" />
</p>

### Click macro audit

Google requires click macro support. This table shows which creatives include it and which do not.

![Click macro coverage audit](docs/screenshots/click-macro-audit.png)

### Campaign clustering

Creatives are grouped automatically by destination URL. This surfaces which campaigns target the same audience and where spend overlaps.

![Auto-clustered campaigns by destination](docs/screenshots/auto-clustering.png)

### Publisher block/allow

See publishers ranked by spend, impressions, and win rate. Block underperformers directly.

![Publisher list with block controls](docs/screenshots/block-allow-pubs.png)

### Staged changes with confirmation

Changes you make are staged first. Nothing is sent to Google until you review the list and click "Yes, Push to Google." A snapshot is created automatically so you can roll back if needed.

![Change preview before pushing to Google](docs/screenshots/change-preview.png)

### Data retention

Control how long raw and summary data is kept. Auto-aggregation compresses old data without losing trend visibility.

![Data retention settings](docs/screenshots/data-retention-config.png)

## Quick start

```bash
git clone https://github.com/jenbrannstrom/rtbcat-platform.git
cd rtbcat-platform
cp .env.example .env
# set POSTGRES_DSN and POSTGRES_SERVING_DSN in .env first
./setup.sh
./run.sh
```

Open `http://localhost:3000`.

Requirements:
- Python 3.11+
- Node.js 18+
- Postgres 14+
- `ffmpeg` optional, for video thumbnails

`./setup.sh` expects Postgres connection strings before it can initialize the schema. More setup detail is in [INSTALL.md](INSTALL.md).

## Install model

The install is split on purpose.

1. Boot the app.
2. Add Gmail import.
3. Verify the data path.
4. Add Google write access only when you actually want live pretargeting changes.

That keeps a fresh install useful without forcing high-risk credentials on day one.

Authentication and first-admin bootstrap are documented in [docs/AUTHENTICATION.md](docs/AUTHENTICATION.md).

## Main routes

These are the routes that matter for an operator.

| Area | Route | Purpose |
|---|---|---|
| Home | `/` | Top-level status and summary |
| Setup | `/setup` | First-run checks and onboarding |
| Creatives | `/creatives` | Creative list and review |
| Click macros | `/creatives/click-macros` | Click macro audit |
| Attribution readiness | `/creatives/attribution-readiness` | Seat-level AppsFlyer readiness |
| Campaigns | `/campaigns` | Campaign and cluster views |
| Import | `/import` | Manual uploads, Gmail status, import history |
| History | `/history` | Change and import history |
| QPS by publisher | `/qps/publisher` | Publisher-side QPS and waste |
| QPS by geo | `/qps/geo` | Geo-side QPS and waste |
| QPS by size | `/qps/size` | Size coverage and waste |
| Waste analysis | `/waste-analysis` | Waste and inefficiency analysis |
| Settings | `/settings` | Main settings entry |
| Connected accounts | `/settings/accounts` | Google API, Gmail, and optional AI provider config |
| Retention | `/settings/retention` | Retention controls |
| System | `/settings/system` | Runtime, DB, thumbnails, health |
| Admin | `/admin` | Users, config, audit log |

Buyer-scoped equivalents also exist under `/{buyerId}/...`.

## Architecture in one paragraph

The frontend is Next.js. The backend is FastAPI. The serving database is Postgres. In the GCP deployment path, Cloud SQL is reached through `cloud-sql-proxy`. Raw export and archive paths can use GCS and BigQuery, but the operator-facing app runs from Postgres. Reverse proxy and auth depend on deployment mode: local/dev can use Caddy, while the GCP path expects external Nginx and OAuth proxy wiring.

The full technical layout is in [ARCHITECTURE.md](ARCHITECTURE.md).

## The five CSV reports

Cat-Scan still depends on five separate Authorized Buyers reports because Google does not let you combine all required fields in one export.

Required reports:
1. `catscan-bidsinauction`
2. `catscan-quality`
3. `catscan-pipeline-geo`
4. `catscan-pipeline`
5. `catscan-bid-filtering`

Why five:
- bid requests and pretargeting config are not available in the same report
- creative-level and publisher-level views also split across incompatible report shapes

The importer joins those reports into a usable dataset. Details are in [DATA_MODEL.md](DATA_MODEL.md) and [importers/README.md](importers/README.md).

## API surface

The API is larger than a short README table can capture. The current router surface includes:
- auth and bootstrap
- system and health
- creatives, live creative fetch, creative cache
- language and geo-linguistic analysis
- seats and seat admin
- campaigns
- settings and pretargeting flows
- analytics home, waste, traffic, spend, RTB bidstream, and QPS
- uploads, Gmail, retention, precompute, troubleshooting
- conversions and optimizer routes
- admin

Run locally and use `http://localhost:8000/docs` for the current OpenAPI surface.

## Deployment

There are two real deployment modes in this repo.

### Local or simple self-host
- Next.js on port `3000`
- FastAPI on port `8000`
- local Postgres or external Postgres
- optional Caddy reverse proxy

### GCP path
- external reverse proxy and auth in front
- `cloud-sql-proxy` sidecar
- FastAPI container
- Next.js container
- Postgres serving database in Cloud SQL
- optional GCS / BigQuery pipeline for raw and archival data

Start with [INSTALL.md](INSTALL.md). For release/build rules, use [docs/VERSIONING.md](docs/VERSIONING.md).

## Documentation

| Document | Use it for |
|---|---|
| [INSTALL.md](INSTALL.md) | local install, production install, Gmail setup |
| [SECURITY.md](SECURITY.md) | security policy and deployment precautions |
| [ARCHITECTURE.md](ARCHITECTURE.md) | current system layout |
| [DATA_MODEL.md](DATA_MODEL.md) | Postgres schema and import model |
| [docs/OPTIMIZATION_LOGIC.md](docs/OPTIMIZATION_LOGIC.md) | what the optimizer uses and what it still lacks |
| [METRICS_GUIDE.md](METRICS_GUIDE.md) | metric definitions |
| [ROADMAP.md](ROADMAP.md) | what is built, what is partial, what comes next |
| [CHANGELOG.md](CHANGELOG.md) | release history |
| [CONTRIBUTING.md](CONTRIBUTING.md) | contribution flow |

## Security model

The rule is simple:
- code can be public
- data and credentials cannot

Keep private:
- `.env`
- service-account keys
- Gmail tokens
- Postgres credentials
- `terraform.tfvars`
- local databases, imports, and thumbnails under `~/.catscan/`

The repo preflight and secret scanning are designed around that assumption. See [SECURITY.md](SECURITY.md).

## Current status

Release engineering is in good shape.

As of `v0.9.4`:
- the OSS preflight passes
- the full Python suite passes in this repo
- dashboard build and lint pass

What still needs more proof:
- measured efficiency uplift across multiple real deployments
- end-to-end conversion-driven optimization at production scale
- provider-agnostic language analysis instead of a single optional AI path

## Contributing

Run the basics before you open a change:

```bash
./venv/bin/ruff check .
./venv/bin/pytest -q
cd dashboard && npm run lint && npm run build
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for the rest.

## License

MIT. See [LICENSE](LICENSE).
