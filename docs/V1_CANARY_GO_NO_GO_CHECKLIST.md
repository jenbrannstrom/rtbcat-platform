# v1 Canary Go/No-Go Checklist

**Last updated:** 2026-02-28  
**Owner:** QA + SRE + Backend  
**Applies to:** Cat-Scan v1 candidate release

## 0. Quick Smoke Command

Run the scripted smoke gate before manual checklist review:

```bash
CATSCAN_API_BASE_URL=http://127.0.0.1:8000 \
CATSCAN_BUYER_ID=<buyer_id> \
CATSCAN_CANARY_RUN_WORKFLOW=1 \
make v1-canary-smoke
```

Set `CATSCAN_ROLLBACK_BILLING_ID=<billing_id>` and `CATSCAN_ROLLBACK_SNAPSHOT_ID=<snapshot_id>` to include rollback dry-run check.

Equivalent direct wrapper command:

```bash
CATSCAN_API_BASE_URL=http://127.0.0.1:8000 \
CATSCAN_BUYER_ID=<buyer_id> \
CATSCAN_CANARY_RUN_WORKFLOW=1 \
bash scripts/run_v1_canary_smoke.sh
```

Optional stricter gate:

```bash
CATSCAN_CANARY_REQUIRE_HEALTHY_READINESS=1 \
CATSCAN_MAX_DIMENSION_MISSING_PCT=20 \
make v1-canary-smoke
```

Phase 0 local gate command:

```bash
make phase0-gate
```

## 1. Pre-Canary Gate (Must Pass)

1. Latest migration set applied without error in target environment.
2. API health returns `healthy` on `/health`.
3. Dashboard production build succeeds.
4. Core optimizer/conversion test suites pass in CI.
5. No open Sev-1/Sev-2 defects in v1 scope.

## 2. Data Integrity Gate

1. `/system/data-health` returns optimizer readiness payload.
2. `rtb_quality` freshness state is not `unavailable` for canary buyer.
3. Bidstream dimension coverage (platform/environment/transaction_type) is populated.
4. No critical ingestion drift in last 24h.

## 3. Conversion Ingestion Gate

1. `/conversions/health` returns non-error response.
2. `/conversions/ingestion/stats?days=7` returns accepted/rejected counters.
3. DLQ list/replay/discard endpoints respond as expected.
4. If webhook security is enabled, HMAC + freshness checks pass fixture validation.

## 4. Optimizer Workflow Gate

For at least one canary buyer:

1. Active model exists in `/optimizer/models`.
2. Model validation endpoint passes:
   - `POST /optimizer/models/{model_id}/validate`
3. One-shot workflow runs:
   - `POST /optimizer/workflows/score-and-propose`
4. Proposal lifecycle succeeds:
   - approve -> apply(queue) -> sync
5. Proposal history is readable:
   - `GET /optimizer/proposals/{proposal_id}/history`

## 5. Rollback Gate

1. Snapshot retrieval works for impacted billing ID:
   - `GET /settings/pretargeting/snapshots?billing_id={billing_id}`
2. Rollback dry-run returns expected diff:
   - `POST /settings/pretargeting/{billing_id}/rollback` (`dry_run=true`)
3. Rollback execute succeeds in controlled test:
   - `POST /settings/pretargeting/{billing_id}/rollback` (`dry_run=false`)

## 6. Runtime Observability Gate

1. Error rates remain within normal range during canary window.
2. Conversion webhook reject spike alerts are clear/understood.
3. No sustained 5xx from optimizer/conversion routes.
4. Audit trail entries appear for optimizer setup and proposal actions.

## 7. Go/No-Go Decision

Mark each item pass/fail. Release is **GO** only if all critical gates pass:

1. Data integrity
2. Conversion ingestion
3. Optimizer workflow
4. Rollback validation

If any critical gate fails, outcome is **NO-GO** and rollback procedures are triggered.
