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

## 2) Verify migration status (production)

Run:

```bash
scripts/check_prod_postgres_migrations.sh --status-only
scripts/check_prod_postgres_migrations.sh --audit-only
```

Required:

- migration `062_rtb_fact_query_indexes` is applied
- no migration drift/mismatch in audit output

## 3) Verify secrets health before strict mode

Run on production API:

```bash
curl -sS https://scan.rtb.cat/api/system/secrets-health
```

Required:

- `healthy=true`
- `missing_required_keys=[]`

Then enable strict mode in production env:

```bash
SECRETS_HEALTH_STRICT=true
```

Redeploy after changing env.

## 4) Verify runtime health + SLO readiness

Run:

```bash
scripts/run_v1_runtime_health_unblock_check.sh --buyer-id <PROD_BUYER_ID> --since-hours 168 --skip-strict
```

Required highlights:

- `/system/data-health` passes
- `/optimizer/economics/efficiency` passes
- QPS page SLO summary passes (P95 budgets)

## 5) Run strict runtime gate

Run:

```bash
scripts/run_v1_runtime_health_strict_dispatch.sh --buyer-id <PROD_BUYER_ID> --profile balanced
```

Required:

- strict run exits `0`
- no `BLOCKED` / `FAIL` outcomes for required checks

## 6) Release decision

Release only if all of the following are true:

- deploy workflow succeeds without warnings that indicate auth/secrets regressions
- migration/audit checks are clean
- secrets health is clean with strict mode enabled
- runtime health strict gate is green
