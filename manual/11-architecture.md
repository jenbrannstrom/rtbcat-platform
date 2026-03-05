# Chapter 11: Architecture Overview

*Audience: DevOps, platform engineers*

## System topology

```
                                    Internet
                                       │
                                 ┌─────┴─────┐
                                 │   nginx    │  :443 (TLS termination)
                                 └──┬──────┬──┘
                                    │      │
                          ┌─────────┘      └─────────┐
                          │                          │
                  ┌───────┴────────┐       ┌─────────┴─────────┐
                  │  OAuth2 Proxy  │       │  Next.js Dashboard │  :3000
                  │  (Google SSO)  │       │  (static + SSR)    │
                  └───────┬────────┘       └───────────────────┘
                          │
                  ┌───────┴────────┐
                  │   FastAPI API  │  :8000
                  │  (118+ routes) │
                  └───────┬────────┘
                          │
              ┌───────────┴───────────┐
              │                       │
    ┌─────────┴──────────┐   ┌────────┴────────┐
    │ Cloud SQL Proxy    │   │   BigQuery       │
    │ (Postgres sidecar) │   │ (batch analytics)│
    └─────────┬──────────┘   └─────────────────┘
              │
    ┌─────────┴──────────┐
    │  Cloud SQL         │
    │  (Postgres 15)     │
    └────────────────────┘
```

## Container layout

Production runs on a single GCP VM (`catscan-vm`, zone
`asia-southeast1-b`) using `docker-compose.gcp.yml`.

| Container | Image | Port | Role |
|-----------|-------|------|------|
| `catscan-api` | `asia-southeast1-docker.pkg.dev/.../api:sha-XXXXXXX` | 8000 | FastAPI backend |
| `catscan-dashboard` | `asia-southeast1-docker.pkg.dev/.../dashboard:sha-XXXXXXX` | 3000 | Next.js frontend |
| `oauth2-proxy` | stock oauth2-proxy image | 4180 | Google OAuth2 authentication |
| `cloudsql-proxy` | Google Cloud SQL Auth Proxy | 5432 | Postgres connection proxy |
| `nginx` | stock nginx with config | 80/443 | Reverse proxy, TLS, routing |

## Auth trust chain

```
Browser → nginx → OAuth2 Proxy → sets X-Email header → nginx → API
```

1. Browser hits nginx.
2. nginx routes `/oauth2/*` to OAuth2 Proxy.
3. OAuth2 Proxy authenticates via Google, sets `X-Email` header.
4. Subsequent requests pass through nginx with `X-Email` intact.
5. API reads `X-Email` and trusts it (when `OAUTH2_PROXY_ENABLED=true`).

**Important:** The API only trusts `X-Email` from internal traffic. External
requests with a forged `X-Email` header are rejected by nginx.

## Why two databases

Cat-Scan uses both Postgres and BigQuery for different roles:

| Concern | Postgres (Cloud SQL) | BigQuery |
|---------|---------------------|----------|
| **Role** | Operational database: serves the app | Data warehouse: stores raw data, runs batch analytics |
| **Cost model** | Fixed hosting cost, unlimited queries | Pay per query based on data scanned |
| **Latency** | Millisecond responses | 1--3 second overhead even for simple queries |
| **Concurrency** | Handles hundreds of API connections | Not built for concurrent dashboard refreshes |
| **Data** | Pre-aggregated summaries, configs, user data | Raw granular rows (millions per day) |

The pattern: BigQuery is the archive warehouse; Postgres is the store shelf.
You don't send customers to rummage through the warehouse.

## Key codebase structure

```
/api/routers/       FastAPI route handlers (118+ endpoints)
/services/          Business logic layer
/storage/           Database access (Postgres repos, BigQuery clients)
/dashboard/src/     Next.js 14 frontend (App Router)
/scripts/           Operational and diagnostic scripts
/docs/              Architecture docs and AI agent logs
```

The backend follows a **Router -> Service -> Repository** pattern. Routers
handle HTTP; services contain business logic; repositories execute SQL.

## Related

- [Deployment](12-deployment.md): how the system gets deployed
- [Database Operations](14-database.md): Postgres specifics
- [Integrations](17-integrations.md): external service connections
