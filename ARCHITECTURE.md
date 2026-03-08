# Cat-Scan Architecture

Last updated: March 7, 2026

This document describes the architecture that exists in this repo now. It is not a design wish list.

## What the system is

Cat-Scan is a split web application:
- Next.js frontend for operators
- FastAPI backend for ingestion, analytics, auth, and control flows
- Postgres as the serving database
- optional GCS and BigQuery paths for raw export, archive, and precompute support

The product sits beside Google Authorized Buyers. It does not sit inside the bidder.

## High-level layout

```text
Browser
  |
  +--> Reverse proxy / auth layer
  |      - local/self-host: Caddy or nginx
  |      - GCP path: external nginx + oauth2-proxy wiring
  |
  +--> Next.js dashboard (:3000)
  |
  +--> FastAPI API (:8000)
           |
           +--> Postgres serving database
           |      - local Postgres or Cloud SQL
           |
           +--> Cloud SQL Proxy (GCP path)
           |
           +--> Google Authorized Buyers API
           |      - creatives
           |      - buyer seats
           |      - endpoints
           |      - pretargeting configs
           |
           +--> Gmail API
           |      - scheduled report import
           |
           +--> Optional raw-data path
                  - GCS
                  - BigQuery
```

## Frontend

Frontend code lives in [`dashboard/src`](dashboard/src).

Current route shape:
- top-level routes such as `/creatives`, `/campaigns`, `/import`, `/qps/*`, `/waste-analysis`, `/settings/*`, `/admin/*`
- buyer-scoped routes under `/{buyerId}/...` for the same main views

Important current pages:
- `/creatives`
- `/creatives/click-macros`
- `/creatives/attribution-readiness`
- `/campaigns`
- `/import`
- `/history`
- `/qps/geo`
- `/qps/publisher`
- `/qps/size`
- `/waste-analysis`
- `/settings/accounts`
- `/settings/retention`
- `/settings/system`
- `/admin`, `/admin/users`, `/admin/configuration`, `/admin/audit-log`

Core frontend responsibilities:
- operator UI
- buyer-context routing and seat selection
- auth session handling on the client side
- import flows and readiness views
- pretargeting review/apply/rollback flows
- creative inspection, clustering, and diagnostics

## Backend

The API entry point is [`api/main.py`](api/main.py).

The backend is organized around routers plus service/repository layers.

### Router groups in current runtime

Registered router groups include:
- auth bootstrap, password auth, OAuth proxy, Authing
- system
- creatives, live creative fetch, creative cache
- creative language and geo-linguistic analysis
- seats and seat admin
- campaigns
- settings and pretargeting actions
- analytics home, waste, traffic, spend, QPS, RTB bidstream
- recommendations
- uploads and performance import
- collect/sync
- Gmail import
- retention
- conversions
- optimizer models, scoring, proposals, economics, workflows
- precompute
- troubleshooting
- admin

That is materially larger than the older simplified router list in the previous docs.

### Service shape

The codebase has moved away from a monolithic store-first pattern.

Current direction:
- routers handle HTTP and auth boundaries
- services hold business logic
- repositories hold SQL and persistence details
- `PostgresStore` remains as a compatibility layer in some paths, but the repo/service split is real and already in use across major domains

Relevant directories:
- [`services`](services)
- [`storage/postgres_repositories`](storage/postgres_repositories)
- [`api/routers`](api/routers)

## Data model

The canonical serving schema lives in [`storage/postgres_schema.sql`](storage/postgres_schema.sql).

Current count in that file:
- `41` tables

The main data domains are:
- creatives and campaign clustering
- buyer seats and permissions
- RTB delivery facts
- RTB bidstream facts
- bid filtering facts
- import history and ingestion runs
- precompute and serving tables
- pretargeting configs, changes, snapshots, and rollback
- auth, users, sessions, audit log
- conversion events and attribution joins
- creative analysis, including language and geo-linguistic results

The schema docs in [`DATA_MODEL.md`](DATA_MODEL.md) should be read as a field and table reference, not as a deployment source of truth.

## Import and ingestion path

Cat-Scan depends on five Authorized Buyers CSV report types.

Current ingestion entry points:
- Gmail auto-import via [`scripts/gmail_import.py`](scripts/gmail_import.py)
- manual upload via the uploads/import routes
- importer logic via [`importers/unified_importer.py`](importers/unified_importer.py)

Current imported fact families:
- `rtb_daily`
- `rtb_bidstream`
- `rtb_bid_filtering`
- related lineage, freshness, and precompute tables

This is still necessary because Google does not expose the required reporting dimensions in one API or one export shape.

## External integrations

### Google Authorized Buyers

Used for:
- creative sync
- buyer seat discovery
- RTB endpoint discovery
- pretargeting reads and writes

### Gmail

Used for:
- reading scheduled CSV reports
- driving the main import path for QPS and performance data

### Conversions

The repo now has real conversion ingestion and attribution plumbing.

Current state:
- AppsFlyer is the primary implemented path
- the codebase also contains normalization and taxonomy support for Adjust, Branch, generic postbacks, RedTrack, and Voluum-style sources
- readiness and diagnostics are ahead of proven production usage for most of those sources

So the safe statement is:
- conversion ingestion exists
- AppsFlyer is the most mature path in this repo
- broader connector support is partly implemented, not equally validated

### AI-assisted creative analysis

Current state:
- language detection and geo-linguistic mismatch analysis are implemented in backend and UI
- these features are optional
- production deploys can disable them with feature flags
- language analysis supports Gemini, Claude, and Grok, though real-world provider quality still needs operator validation

## Deployment modes

### Local/self-host mode

Typical shape:
- local or external Postgres
- `./run.sh` for API and dashboard
- optional Caddy or nginx in front

### GCP mode

Current compose file: [`docker-compose.gcp.yml`](docker-compose.gcp.yml)

Typical shape:
- `cloud-sql-proxy`
- API container
- dashboard container
- Cloud SQL for Postgres
- external reverse proxy/auth in front of the app

This is the deployment path the repo has been optimized around most heavily.

## Auth model

Cat-Scan supports:
- email/password
- Google login via OAuth proxy integration
- Authing OIDC

Session and role enforcement happen in the app layer, not just in the reverse proxy.

See [`docs/AUTHENTICATION.md`](docs/AUTHENTICATION.md).

## What is not accurate anymore in older docs

The following older ideas should be considered retired:
- a small 15-router backend surface
- a 21-page frontend
- `storage/schema.py` as the source of truth
- `storage/repositories/` as the active repo directory name
- `cli/qps_analyzer.py` as a real current tool
- S3 as a primary current archive path

Those appeared in the earlier architecture doc. They do not describe the repo as it exists now.
