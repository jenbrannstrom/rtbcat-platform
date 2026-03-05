# Hoofdstuk 11: Architectuuroverzicht

*Doelgroep: DevOps, platform-engineers*

## Systeemtopologie

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

## Containerindeling

Productie draait op een enkele GCP VM (`catscan-vm`, zone
`asia-southeast1-b`) met `docker-compose.gcp.yml`.

| Container | Image | Poort | Rol |
|-----------|-------|-------|-----|
| `catscan-api` | `asia-southeast1-docker.pkg.dev/.../api:sha-XXXXXXX` | 8000 | FastAPI-backend |
| `catscan-dashboard` | `asia-southeast1-docker.pkg.dev/.../dashboard:sha-XXXXXXX` | 3000 | Next.js-frontend |
| `oauth2-proxy` | standaard oauth2-proxy image | 4180 | Google OAuth2-authenticatie |
| `cloudsql-proxy` | Google Cloud SQL Auth Proxy | 5432 | Postgres-verbindingsproxy |
| `nginx` | standaard nginx met configuratie | 80/443 | Reverse proxy, TLS, routing |

## Auth-vertrouwensketen

```
Browser → nginx → OAuth2 Proxy → stelt X-Email header in → nginx → API
```

1. De browser bereikt nginx.
2. nginx routeert `/oauth2/*` naar OAuth2 Proxy.
3. OAuth2 Proxy authenticeert via Google en stelt de `X-Email`-header in.
4. Vervolgverzoeken gaan door nginx met de `X-Email`-header intact.
5. De API leest `X-Email` en vertrouwt deze (wanneer `OAUTH2_PROXY_ENABLED=true`).

**Belangrijk:** De API vertrouwt `X-Email` uitsluitend van intern verkeer. Externe
verzoeken met een vervalste `X-Email`-header worden door nginx geweigerd.

## Waarom twee databases

Cat-Scan gebruikt zowel Postgres als BigQuery voor verschillende doeleinden:

| Aspect | Postgres (Cloud SQL) | BigQuery |
|--------|---------------------|----------|
| **Rol** | Operationele database: bedient de applicatie | Datawarehouse: slaat ruwe data op, voert batchanalyses uit |
| **Kostenmodel** | Vaste hostingkosten, onbeperkt aantal queries | Betaling per query op basis van gescande data |
| **Latentie** | Reactietijden in milliseconden | 1--3 seconden overhead, zelfs voor eenvoudige queries |
| **Gelijktijdigheid** | Verwerkt honderden API-verbindingen | Niet gebouwd voor gelijktijdige dashboard-verversingen |
| **Data** | Vooraf geaggregeerde samenvattingen, configuraties, gebruikersdata | Ruwe granulaire rijen (miljoenen per dag) |

Het patroon: BigQuery is het archiefmagazijn; Postgres is het winkelschap.
Je stuurt klanten niet naar het magazijn om zelf te zoeken.

## Belangrijke codebase-structuur

```
/api/routers/       FastAPI route handlers (118+ endpoints)
/services/          Business logic layer
/storage/           Database access (Postgres repos, BigQuery clients)
/dashboard/src/     Next.js 14 frontend (App Router)
/scripts/           Operational and diagnostic scripts
docs.rtb.cat/       Public documentation portal
```

De backend volgt een **Router -> Service -> Repository**-patroon. Routers
verwerken HTTP; services bevatten bedrijfslogica; repositories voeren SQL uit.

## Gerelateerd

- [Deployment](12-deployment.md): hoe het systeem wordt uitgerold
- [Databasebeheer](14-database.md): Postgres-specifieke details
- [Integraties](17-integrations.md): verbindingen met externe services
