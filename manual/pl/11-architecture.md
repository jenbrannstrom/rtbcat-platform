# Rozdział 11: Przegląd architektury

*Odbiorcy: DevOps, inżynierowie platformy*

## Topologia systemu

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

## Układ kontenerów

Produkcja działa na pojedynczej maszynie wirtualnej GCP (`catscan-vm`,
strefa `asia-southeast1-b`) z użyciem `docker-compose.gcp.yml`.

| Kontener | Obraz | Port | Rola |
|----------|-------|------|------|
| `catscan-api` | `asia-southeast1-docker.pkg.dev/.../api:sha-XXXXXXX` | 8000 | Backend FastAPI |
| `catscan-dashboard` | `asia-southeast1-docker.pkg.dev/.../dashboard:sha-XXXXXXX` | 3000 | Frontend Next.js |
| `oauth2-proxy` | standardowy obraz oauth2-proxy | 4180 | Uwierzytelnianie Google OAuth2 |
| `cloudsql-proxy` | Google Cloud SQL Auth Proxy | 5432 | Proxy połączenia z Postgres |
| `nginx` | standardowy nginx z konfiguracją | 80/443 | Reverse proxy, TLS, routing |

## Łańcuch zaufania uwierzytelniania

```
Browser → nginx → OAuth2 Proxy → sets X-Email header → nginx → API
```

1. Przeglądarka trafia do nginx.
2. nginx kieruje `/oauth2/*` do OAuth2 Proxy.
3. OAuth2 Proxy uwierzytelnia przez Google i ustawia nagłówek `X-Email`.
4. Kolejne żądania przechodzą przez nginx z nagłówkiem `X-Email`.
5. API odczytuje `X-Email` i ufa mu (gdy `OAUTH2_PROXY_ENABLED=true`).

**Ważne:** API ufa nagłówkowi `X-Email` wyłącznie z ruchu wewnętrznego.
Zewnętrzne żądania ze sfałszowanym nagłówkiem `X-Email` są odrzucane przez
nginx.

## Dlaczego dwie bazy danych

Cat-Scan wykorzystuje zarówno Postgres, jak i BigQuery do różnych celów:

| Aspekt | Postgres (Cloud SQL) | BigQuery |
|--------|---------------------|----------|
| **Rola** | Baza operacyjna: obsługuje aplikację | Hurtownia danych: przechowuje surowe dane, uruchamia analizy wsadowe |
| **Model kosztów** | Stały koszt hostingu, nieograniczone zapytania | Płatność za zapytanie na podstawie ilości przeskanowanych danych |
| **Opóźnienie** | Odpowiedzi w milisekundach | 1--3 sekundy narzutu nawet przy prostych zapytaniach |
| **Współbieżność** | Obsługuje setki połączeń API | Nie jest przystosowany do współbieżnych odświeżeń dashboardu |
| **Dane** | Wstępnie zagregowane podsumowania, konfiguracje, dane użytkowników | Surowe, granularne wiersze (miliony dziennie) |

Wzorzec: BigQuery to hurtownia archiwalna; Postgres to półka sklepowa.
Klientów nie wysyła się do przeszukiwania magazynu.

## Kluczowa struktura kodu źródłowego

```
/api/routers/       FastAPI route handlers (118+ endpoints)
/services/          Business logic layer
/storage/           Database access (Postgres repos, BigQuery clients)
/dashboard/src/     Next.js 14 frontend (App Router)
/scripts/           Operational and diagnostic scripts
/docs/              Architecture docs and AI agent logs
```

Backend stosuje wzorzec **Router -> Service -> Repository**. Routery
obsługują HTTP; serwisy zawierają logikę biznesową; repozytoria wykonują SQL.

## Powiązane

- [Wdrażanie](12-deployment.md): jak system jest wdrażany
- [Operacje bazodanowe](14-database.md): szczegóły dotyczące Postgres
- [Integracje](17-integrations.md): połączenia z zewnętrznymi usługami
