# Hoofdstuk 13: Gezondheidsmonitoring en diagnostiek

*Doelgroep: DevOps, platform-engineers*

## Gezondheidsendpoints

### `/api/health`: liveness

Retourneert de basisstatus van de API, de git-SHA en de versie. Wordt gebruikt door de deploy-workflow en externe monitoring.

```bash
curl -sS https://your-deployment.example.com/api/health | jq .
```

### `/system/data-health`: datavolledigheid

Retourneert de gezondheidsstatus van data per koper, inclusief de versheidsgraad per rapporttype. Accepteert de parameters `days`, `buyer_id` en `availability_state`.

Wordt gebruikt door de setup-checklist en de runtime-gezondheidspoort.

## Systeemstatuspagina (`/settings/system`)

De UI toont:

| Controle | Wat het monitort |
|----------|-----------------|
| Python | Runtimeversie en beschikbaarheid |
| Node | Next.js-build en SSR-status |
| FFmpeg | Mogelijkheid voor het genereren van videominiaturen |
| Database | Postgres-verbinding en rijtelling |
| Miniaturen | Status en wachtrij van batchgeneratie |
| Schijfruimte | Schijfgebruik van de VM |

## Runtime-gezondheidsscripts

Deze scripts vormen de operationele ruggengraat om te verifieren dat het systeem end-to-end werkt.

### `diagnose_v1_buyer_report_coverage.sh`

Diagnosticeert waarom een specifieke koper ontbrekende CSV-dekking heeft.

```bash
export CATSCAN_CANARY_EMAIL="user.com"
scripts/diagnose_v1_buyer_report_coverage.sh \
  --buyer-id <BUYER_ID> \
  --timeout 180 \
  --days 14
```

Controles (in volgorde):
1. Seat-mapping: buyer_id -> bidder_id
2. Importmatrix: geslaagd/mislukt/niet_geimporteerd per CSV-type
3. Dataversheid: geimporteerde/ontbrekende celdekking
4. Importgeschiedenis: recente importrijen
5. Gmail-status: aantal ongelezen, laatste reden, recentste metriekdatum

Resultaat: PASS of FAIL met een specifieke diagnose.

### `run_v1_runtime_health_strict_dispatch.sh`

Voert de volledige runtime-gezondheidspoort uit, die het volgende controleert:

- API-gezondheid
- Datagezondheid (versheid en dimensiedekking)
- Conversiegezondheid en gereedheid
- QPS-opstartlatentie
- QPS-pagina SLO-samenvatting
- Optimizer-economie en modellen
- Validatie van modelendpoints
- Score+propose-workflow
- Voorstelcyclus
- Rollback dry-run

Elke controle retourneert PASS, FAIL of BLOCKED (met reden).

### CI-workflow: `v1-runtime-health-strict.yml`

Voert de strikte poort uit in CI. Handmatig getriggerd via workflow_dispatch.

```bash
gh workflow run v1-runtime-health-strict.yml \
  --ref unified-platform \
  -f api_base_url="https://your-deployment.example.com/api" \
  -f buyer_id="<BUYER_ID>" \
  -f canary_profile="balanced" \
  -f canary_timeout_seconds="180"
```

## Canary-authenticatie

Runtime-scripts authenticeren via omgevingsvariabelen:

| Variabele | Doel |
|-----------|------|
| `CATSCAN_CANARY_EMAIL` | X-Email-header voor directe API-aanroepen (VM-lokaal) |
| `CATSCAN_BEARER_TOKEN` | Bearer-token (CI-omgeving, opgeslagen in GitHub-secrets) |
| `CATSCAN_SESSION_COOKIE` | OAuth2 Proxy-sessiecookie (CI-omgeving) |

Vanaf de VM-host: gebruik `CATSCAN_CANARY_EMAIL` met `http://localhost:8000`.
Vanuit CI (extern): gebruik `CATSCAN_BEARER_TOKEN` of `CATSCAN_SESSION_COOKIE`
met `https://your-deployment.example.com/api`.

## Resultaten interpreteren

| Status | Betekenis |
|--------|-----------|
| **PASS** | Controle geslaagd, systeem gezond |
| **FAIL** | Controle mislukt, onmiddellijk onderzoeken |
| **BLOCKED** | Controle kon niet worden voltooid vanwege een afhankelijkheid (bijv. geen data voor deze koper, ontbrekend endpoint). Niet per se een codebug. |

## Gerelateerd

- [Deployment](12-deployment.md): deploymentverificatie
- [Probleemoplossing](15-troubleshooting.md): wanneer gezondheidscontroles falen
- Voor mediakopers: [Data-import](09-data-import.md) beschrijft het dataversheidsraster in kopervriendelijke termen.
