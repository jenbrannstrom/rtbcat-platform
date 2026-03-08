# Kapitel 12: Udrulning

*Målgruppe: DevOps, platformingeniører*

## CI/CD-pipeline

```
Push to main
         │
         ▼
build-and-push.yml (automatic)
  ├── Run contract & recovery tests
  ├── Build API image
  ├── Build Dashboard image
  └── Push to Artifact Registry
         │
         ▼ (manual trigger)
deploy.yml (workflow_dispatch)
  ├── SSH into VM via IAP tunnel
  ├── git pull on VM
  ├── docker compose pull (prebuilt images)
  ├── docker compose up -d --force-recreate
  ├── Health check (60s wait + curl localhost:8000/health)
  └── Post-deploy contract check
```

### Hvorfor udrulning er manuel

Automatisk udrulning ved push blev deaktiveret efter en hændelse i januar 2026, hvor automatiske udrulninger kolliderede med manuelle SSH-udrulninger, hvilket ødelagde containere og forårsagede datatab. Udrulningsworkflowet kræver nu:

1. Manuel aktivering via GitHub Actions-brugerfladen ("Run workflow")
2. Eksplicit valg af mål (staging eller produktion)
3. Indtastning af `DEPLOY` som bekræftelse
4. Valgfrit begrundelsefelt til revisionsloggen

### Image-tags

Images tagges med det korte git-SHA: `sha-XXXXXXX`. Udrulningstrinnet bruger `GITHUB_SHA` til at konstruere tagget, så den udrullede version altid svarer til et bestemt commit.

## Sådan udrulles

1. Bekræft at buildet er bestået: `gh run list --workflow=build-and-push.yml --limit=1`
2. Aktivér udrulning:
   ```bash
   gh workflow run deploy.yml \
     --ref main \
     -f target=production \
     -f confirm=DEPLOY \
     -f reason="your reason here"
   ```
3. Overvåg: `gh run watch <run_id> --exit-status`
4. Verificér: `curl -sS https://your-deployment.example.com/api/health | jq -r '.git_sha,.version'`

## Verificering af en udrulning

Endpointet `/api/health` returnerer:

```json
{
  "git_sha": "94e9cbb0",
  "version": "sha-94e9cbb"
}
```

Sammenlign `git_sha` med det commit, du havde til hensigt at udrulle.

## Kontrakttjek efter udrulning

Efter udrulning kører workflowet `scripts/contracts_check.py` inde i API-containeren. Dette validerer, at datakontrakterne (ufravigelige regler fra import til API-output) overholdes. Hvis tjekket fejler:

- Med `ALLOW_CONTRACT_FAILURE=false` (standard): udrulningen markeres som fejlet.
- Med `ALLOW_CONTRACT_FAILURE=true` (midlertidig omgåelse): udrulningen lykkes med en advarsel. Denne omgåelse skal fjernes efter undersøgelse.

## Staging vs. produktion

| Miljø | VM-navn | Domæne |
|-------|---------|--------|
| Staging | `catscan-vm` | (intern) |
| Produktion | `catscan-vm` | `your-deployment.example.com` |

Udrul til staging først, verificér, og udrul derefter til produktion.

## Tilbagerulning

For at rulle tilbage udrulles et tidligere kendt-godt commit:

1. Identificér det seneste gode SHA fra git-loggen eller tidligere udrulningskørsler.
2. Checkout dette SHA på main (eller brug `--ref` med committet).
3. Aktivér udrulningsworkflowet.

Der er ingen dedikeret tilbagerulningsmekanisme. Det er blot udrulning af en ældre version.

## Relateret

- [Arkitekturoversigt](11-architecture.md): hvad der udrulles
- [Sundhedsovervågning](13-health-monitoring.md): verificering af at udrulningen lykkedes
