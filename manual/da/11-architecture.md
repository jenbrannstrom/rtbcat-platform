# Kapitel 11: Arkitekturoversigt

*Målgruppe: DevOps, platformsingeniører*

## Systemtopologi

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

## Container-layout

Produktion kører på en enkelt GCP VM (`catscan-vm`, zone
`asia-southeast1-b`) med `docker-compose.gcp.yml`.

| Container | Image | Port | Rolle |
|-----------|-------|------|-------|
| `catscan-api` | `asia-southeast1-docker.pkg.dev/.../api:sha-XXXXXXX` | 8000 | FastAPI-backend |
| `catscan-dashboard` | `asia-southeast1-docker.pkg.dev/.../dashboard:sha-XXXXXXX` | 3000 | Next.js-frontend |
| `oauth2-proxy` | standard oauth2-proxy-image | 4180 | Google OAuth2-autentificering |
| `cloudsql-proxy` | Google Cloud SQL Auth Proxy | 5432 | Postgres-forbindelsesproxy |
| `nginx` | standard nginx med konfiguration | 80/443 | Reverse proxy, TLS, routing |

## Autentificeringstillidskaede

```
Browser → nginx → OAuth2 Proxy → sætter X-Email header → nginx → API
```

1. Browseren rammer nginx.
2. nginx dirigerer `/oauth2/*` til OAuth2 Proxy.
3. OAuth2 Proxy autentificerer via Google og sætter `X-Email`-headeren.
4. Efterfølgende anmodninger passerer gennem nginx med `X-Email` intakt.
5. API'et læser `X-Email` og stoler på den (når `OAUTH2_PROXY_ENABLED=true`).

**Vigtigt:** API'et stoler kun på `X-Email` fra intern trafik. Eksterne
anmodninger med en forfalsket `X-Email`-header afvises af nginx.

## Hvorfor to databaser

Cat-Scan bruger både Postgres og BigQuery til forskellige formål:

| Hensyn | Postgres (Cloud SQL) | BigQuery |
|--------|---------------------|----------|
| **Rolle** | Operationel database: betjener appen | Data warehouse: gemmer rådata, kører batch-analyser |
| **Omkostningsmodel** | Fast hostingomkostning, ubegrænset antal forespørgsler | Betaling pr. forespørgsel baseret på scannet data |
| **Latens** | Millisekunders svartider | 1--3 sekunders overhead selv for simple forespørgsler |
| **Samtidige forbindelser** | Håndterer hundredvis af API-forbindelser | Ikke bygget til samtidige dashboard-opdateringer |
| **Data** | Præaggregerede oversigter, konfigurationer, brugerdata | Rå granulære rækker (millioner per dag) |

Mønsteret er: BigQuery er arkivlageret; Postgres er butikshylden.
Du sender ikke kunder ud for at rode i lageret.

## Central kodebasestruktur

```
/api/routers/       FastAPI route handlers (118+ endpoints)
/services/          Business logic layer
/storage/           Database access (Postgres repos, BigQuery clients)
/dashboard/src/     Next.js 14 frontend (App Router)
/scripts/           Operational and diagnostic scripts
docs.rtb.cat/       Public documentation portal
```

Backenden følger et **Router -> Service -> Repository**-mønster. Routere
håndterer HTTP; services indeholder forretningslogik; repositories udfører SQL.

## Relateret

- [Udrulning](12-deployment.md): hvordan systemet udrulles
- [Databaseoperationer](14-database.md): Postgres-specifikke detaljer
- [Integrationer](17-integrations.md): forbindelser til eksterne tjenester
