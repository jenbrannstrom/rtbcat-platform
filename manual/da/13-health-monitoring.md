# Kapitel 13: Sundhedsovervågning og diagnostik

*Målgruppe: DevOps, platformingeniører*

## Sundhedsendpoints

### `/api/health`: liveness

Returnerer grundlæggende API-status, git-SHA og version. Bruges af udrulningsworkflowet og ekstern overvågning.

```bash
curl -sS https://your-deployment.example.com/api/health | jq .
```

### `/system/data-health`: datafuldstændighed

Returnerer datasundhedsstatus pr. køber, herunder friskheds­tilstand for hver rapporttype. Accepterer parametrene `days`, `buyer_id` og `availability_state`.

Bruges af opsætningschecklisten og runtime-sundhedsgatewayed.

## Systemstatusside (`/settings/system`)

Brugerfladen viser:

| Tjek | Hvad det overvåger |
|------|-------------------|
| Python | Runtime-version og tilgængelighed |
| Node | Next.js-build og SSR-status |
| FFmpeg | Evne til generering af videominiaturer |
| Database | Postgres-forbindelse og rækkeantal |
| Miniaturer | Batchgenereringsstatus og kø |
| Diskplads | VM-diskforbrug |

## Runtime-sundhedsscripts

Disse scripts er det operationelle fundament for at verificere, at systemet fungerer end-to-end.

### `diagnose_v1_buyer_report_coverage.sh`

Diagnosticerer hvorfor en bestemt køber mangler CSV-dækning.

```bash
export CATSCAN_CANARY_EMAIL="user.com"
scripts/diagnose_v1_buyer_report_coverage.sh \
  --buyer-id <BUYER_ID> \
  --timeout 180 \
  --days 14
```

Tjek (i rækkefølge):
1. Sæde-mapping: buyer_id -> bidder_id
2. Importmatrix: bestået/fejlet/ikke_importeret pr. CSV-type
3. Datafriskhed: importeret/manglende celledækning
4. Importhistorik: seneste importrækker
5. Gmail-status: antal ulæste, seneste årsag, nyeste metrikdato

Resultat: PASS eller FAIL med specifik diagnose.

### `run_v1_runtime_health_strict_dispatch.sh`

Kører den fulde runtime-sundhedsgate, som kontrollerer:

- API-sundhed
- Datasundhed (friskhed og dimensionsdækning)
- Konverteringssundhed og parathed
- QPS-startlatens
- QPS-side SLO-resumé
- Optimeringsøkonomi og modeller
- Modelendpoint-validering
- Score+propose-workflow
- Forslagslivscyklus
- Tilbagerulning dry-run

Hvert tjek returnerer PASS, FAIL eller BLOCKED (med begrundelse).

### CI-workflow: `v1-runtime-health-strict.yml`

Kører den strenge gate i CI. Aktiveres manuelt via workflow_dispatch.

```bash
gh workflow run v1-runtime-health-strict.yml \
  --ref main \
  -f api_base_url="https://your-deployment.example.com/api" \
  -f buyer_id="<BUYER_ID>" \
  -f canary_profile="balanced" \
  -f canary_timeout_seconds="180"
```

## Canary-autentificering

Runtime-scripts autentificerer via miljøvariabler:

| Variabel | Formål |
|----------|--------|
| `CATSCAN_CANARY_EMAIL` | X-Email-header til direkte API-kald (VM-lokalt) |
| `CATSCAN_BEARER_TOKEN` | Bearer-token (CI-miljø, gemt i GitHub-secrets) |
| `CATSCAN_SESSION_COOKIE` | OAuth2 Proxy-sessionscookie (CI-miljø) |

Fra VM-værten bruges `CATSCAN_CANARY_EMAIL` med `http://localhost:8000`.
Fra CI (eksternt) bruges `CATSCAN_BEARER_TOKEN` eller `CATSCAN_SESSION_COOKIE`
med `https://your-deployment.example.com/api`.

## Fortolkning af resultater

| Status | Betydning |
|--------|-----------|
| **PASS** | Tjekket lykkedes, systemet er sundt |
| **FAIL** | Tjekket fejlede, undersøg straks |
| **BLOCKED** | Tjekket kunne ikke fuldføres på grund af en afhængighed (f.eks. ingen data for denne køber, manglende endpoint). Ikke nødvendigvis en kodefejl. |

## Relateret

- [Udrulning](12-deployment.md): verificering af udrulning
- [Fejlfinding](15-troubleshooting.md): når sundhedstjek fejler
- For mediekøbere: [Dataimport](09-data-import.md) forklarer datafriskheds­gitteret i købervenlige termer.
