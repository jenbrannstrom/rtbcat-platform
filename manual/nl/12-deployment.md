# Hoofdstuk 12: Deployment

*Doelgroep: DevOps, platform-engineers*

## CI/CD-pipeline

```
Push to unified-platform
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

### Waarom deployment handmatig is

Automatische deployment bij een push is uitgeschakeld na een incident in januari 2026, waarbij automatische deploys conflicteerden met handmatige SSH-deploys. Dit leidde tot corrupte containers en dataverlies. De deploy-workflow vereist nu:

1. Handmatige trigger via de GitHub Actions UI ("Run workflow")
2. Expliciete selectie van het doelomgeving (staging of productie)
3. Het invoeren van `DEPLOY` als bevestiging
4. Een optioneel redenveld voor de audittrail

### Image-tags

Images worden getagd met de verkorte git-SHA: `sha-XXXXXXX`. De deploy-stap gebruikt `GITHUB_SHA` om de tag samen te stellen, zodat de gedeployde versie altijd overeenkomt met een specifieke commit.

## Hoe te deployen

1. Controleer of de build geslaagd is: `gh run list --workflow=build-and-push.yml --limit=1`
2. Trigger de deployment:
   ```bash
   gh workflow run deploy.yml \
     --ref unified-platform \
     -f target=production \
     -f confirm=DEPLOY \
     -f reason="your reason here"
   ```
3. Monitor: `gh run watch <run_id> --exit-status`
4. Verifieer: `curl -sS https://scan.rtb.cat/api/health | jq -r '.git_sha,.version'`

## Een deployment verifieren

Het `/api/health`-endpoint retourneert:

```json
{
  "git_sha": "94e9cbb0",
  "version": "sha-94e9cbb"
}
```

Vergelijk `git_sha` met de commit die je bedoelde te deployen.

## Post-deploy contractcontrole

Na de deployment voert de workflow `scripts/contracts_check.py` uit binnen de API-container. Dit valideert dat datacontracten (niet-onderhandelbare regels van import tot API-uitvoer) worden nageleefd. Als de controle mislukt:

- Met `ALLOW_CONTRACT_FAILURE=false` (standaard): de deploy wordt als mislukt gemarkeerd.
- Met `ALLOW_CONTRACT_FAILURE=true` (tijdelijke bypass): de deploy slaagt met een waarschuwing. Deze bypass moet na onderzoek worden verwijderd.

## Staging vs. productie

| Omgeving | VM-naam | Domein |
|----------|---------|--------|
| Staging | `catscan-production-sg2` | (intern) |
| Productie | `catscan-production-sg` | `scan.rtb.cat` |

Deploy eerst naar staging, verifieer, en deploy dan naar productie.

## Rollback

Om terug te draaien, deploy je een eerder bekende goede commit:

1. Identificeer de laatste goede SHA vanuit het git-log of eerdere deploy-runs.
2. Check die SHA uit op unified-platform (of gebruik `--ref` met de commit).
3. Trigger de deploy-workflow.

Er is geen apart rollback-mechanisme. Het is simpelweg het deployen van een oudere versie.

## Gerelateerd

- [Architectuuroverzicht](11-architecture.md): wat er gedeployd wordt
- [Gezondheidsmonitoring](13-health-monitoring.md): verifieren dat de deploy gelukt is
