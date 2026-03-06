# Deploy Checklist

This checklist is the release gate for production deploys.

## 1) Deploy latest `unified-platform`

Use the manual GitHub workflow:

- `.github/workflows/deploy.yml`
- target: `staging` first, then `production`

The workflow already hard-fails on:

- unhealthy `/health`
- deployed SHA/version mismatch
- Artifact Registry auth regression (`Unauthenticated request`)
- secrets-health unhealthy or probe unavailable (when `SECRETS_HEALTH_STRICT=true`)

## 2) Verify migration status (production)

Run:

```bash
scripts/check_prod_postgres_migrations.sh --status-only
scripts/check_prod_postgres_migrations.sh --audit-only
```

Required:

- migration `062_rtb_fact_query_indexes` is applied
- no migration drift/mismatch in audit output

## 3) Verify secrets health

The deploy workflow runs `scripts/verify_secrets_health.sh` automatically.
It probes secrets health directly inside the container (no HTTP auth needed).

Exit codes:

| Code | Meaning | Strict=false | Strict=true |
|------|---------|-------------|-------------|
| 0 | healthy | pass | pass |
| 2 | probe unavailable | warning | hard-fail |
| 3 | unhealthy | warning | hard-fail |

To verify manually on the VM:

```bash
sudo bash /opt/catscan/scripts/verify_secrets_health.sh --container catscan-api
```

Strict mode is controlled by the `SECRETS_HEALTH_STRICT` env var (set in `.env` on the VM
and as a repo variable for the deploy workflow).

## 4) Verify Cloud SQL backup posture

Required checks:

- Cloud SQL deletion protection is enabled.
- Automated backups are enabled with PITR.
- Latest logical export exists in backup bucket.

Commands:

```bash
gcloud sql instances describe catscan-production-serving \
  --project catscan-prod-202601 \
  --format='yaml(settings.deletionProtectionEnabled,settings.backupConfiguration)'

gcloud sql operations list \
  --instance=catscan-production-serving \
  --project=catscan-prod-202601 \
  --limit=5 --sort-by=~startTime \
  --filter='operationType=EXPORT'

gcloud storage ls gs://catscan-sql-backups-449322304772/catscan-production-serving/
```

Automation:

- `.github/workflows/cloudsql-logical-backup.yml` runs a daily export to GCS.

## 5) Verify runtime health + SLO readiness

Run:

```bash
scripts/run_v1_runtime_health_unblock_check.sh --buyer-id <PROD_BUYER_ID> --since-hours 168 --skip-strict
```

Required highlights:

- `/system/data-health` passes
- `/optimizer/economics/efficiency` passes
- QPS page SLO summary passes (P95 budgets)

## 6) Run strict runtime gate

Run:

```bash
scripts/run_v1_runtime_health_strict_dispatch.sh --buyer-id <PROD_BUYER_ID> --profile balanced
```

Required:

- strict run exits `0`
- no `BLOCKED` / `FAIL` outcomes for required checks

Temporary waiver note (March 5, 2026):

- `CATSCAN_RUNTIME_HEALTH_MAX_HOME_ENDPOINT_EFFICIENCY_LATENCY_MS=30000` may be used only while 168h QPS page SLO history still contains pre-fix `/analytics/home/endpoint-efficiency` outliers.
- Waiver expiry: **March 12, 2026**.
- Workflow guardrail variable: `CATSCAN_RUNTIME_HEALTH_ENDPOINT_EFFICIENCY_BUDGET_WAIVER_EXPIRES_ON` (defaults to `2026-03-12`).
- On/after expiry, restore `CATSCAN_RUNTIME_HEALTH_MAX_HOME_ENDPOINT_EFFICIENCY_LATENCY_MS=12000` and rerun:

```bash
scripts/run_v1_runtime_health_strict_dispatch.sh --buyer-id <PROD_BUYER_ID> --profile balanced --since-hours 168
```

## 7) Release decision

Release only if all of the following are true:

- deploy workflow succeeds without warnings that indicate auth/secrets regressions
- migration/audit checks are clean
- secrets health is clean with strict mode enabled
- runtime health strict gate is green
