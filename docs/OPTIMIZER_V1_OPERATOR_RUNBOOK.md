# Optimizer v1 Operator Runbook

**Last updated:** 2026-03-01  
**Scope:** Score -> propose -> approve -> apply for QPS optimization with guarded rollback.

## 1. Preconditions

Before running optimizer actions, verify:

1. Buyer seat is connected and selected.
2. `/system/data-health` shows acceptable readiness (report completeness, quality freshness).
3. At least one active optimizer model exists (`/optimizer/models`).
4. Monthly hosting cost is configured if Effective CPM is required (`/settings/optimizer/setup`).
5. If conversion optimization is expected, `/conversions/readiness` is `ready` (or explicitly reviewed).

## 2. Health Checks (Read-Only)

Run these checks for the target buyer:

1. `GET /optimizer/economics/effective-cpm?buyer_id={buyer_id}&days=14`
2. `GET /optimizer/economics/efficiency?buyer_id={buyer_id}&days=14`
3. `GET /optimizer/economics/assumed-value?buyer_id={buyer_id}&days=14`
4. `GET /conversions/readiness?buyer_id={buyer_id}&days=14&freshness_hours=72`
5. `GET /conversions/health?buyer_id={buyer_id}`
6. `GET /conversions/ingestion/stats?buyer_id={buyer_id}&days=7`
7. `GET /conversions/security/status`

If readiness is not `ready`, do not apply live changes. Continue with score/proposal review only.

## 3. Standard Workflow

BYOM model contract reference: `docs/BYOM_MODEL_INTEGRATION_GUIDE.md`

### 3.1 Validate model endpoint

1. `POST /optimizer/models/{model_id}/validate?buyer_id={buyer_id}&timeout_seconds=10`
2. Require `valid=true` before running external API models.

### 3.2 Run score + propose

1. `POST /optimizer/workflows/score-and-propose?model_id={model_id}&buyer_id={buyer_id}&days=14&min_confidence=0.3&max_delta_pct=0.3`
2. Review `scores_written` and `proposals_created`.

### 3.3 Review proposals

1. `GET /optimizer/proposals?buyer_id={buyer_id}&status=draft`
2. Check each proposal for:
   - `billing_id`
   - `current_qps`, `proposed_qps`, `delta_qps`
   - `rationale`
   - `projected_impact`

### 3.4 Approve and apply

1. Approve: `POST /optimizer/proposals/{proposal_id}/approve?buyer_id={buyer_id}`
2. Apply in queue mode first: `POST /optimizer/proposals/{proposal_id}/apply?buyer_id={buyer_id}&mode=queue`
3. Sync apply status: `POST /optimizer/proposals/{proposal_id}/sync-apply-status?buyer_id={buyer_id}`
4. Verify history trail: `GET /optimizer/proposals/{proposal_id}/history?buyer_id={buyer_id}`

Use `mode=live` only after queue-mode behavior is stable.

## 4. Rollback Procedure

If a proposal causes unexpected spend, win-rate collapse, or inventory quality drop:

1. Identify affected `billing_id` from proposal/apply details.
2. Fetch snapshots:
   - `GET /settings/pretargeting/snapshots?billing_id={billing_id}&limit=20`
3. Dry-run rollback:
   - `POST /settings/pretargeting/{billing_id}/rollback` with body:
   - `{"snapshot_id": <id>, "dry_run": true}`
4. Execute rollback:
   - `POST /settings/pretargeting/{billing_id}/rollback`
   - `{"snapshot_id": <id>, "dry_run": false}`
5. Re-check:
   - `GET /optimizer/proposals/{proposal_id}/history?buyer_id={buyer_id}`
   - `GET /optimizer/economics/efficiency?buyer_id={buyer_id}&days=7`

## 5. Security Controls (Webhook Ingestion)

Conversion webhook hardening controls are env-driven:

Reference setup guide: `docs/CONVERSION_CONNECTORS_SETUP_GUIDE.md`

1. HMAC validation:
   - `CATSCAN_*_WEBHOOK_HMAC_SECRET`
   - Rotation windows supported via multiple values in one env var (`old,new` or `old;new`).
2. Freshness guard:
   - `CATSCAN_CONVERSIONS_ENFORCE_FRESHNESS=1`
   - `CATSCAN_CONVERSIONS_MAX_SKEW_SECONDS=900`
3. Optional ingress rate limit:
   - `CATSCAN_CONVERSIONS_WEBHOOK_RATE_LIMIT_ENABLED=1`
   - `CATSCAN_CONVERSIONS_WEBHOOK_RATE_LIMIT_PER_MINUTE=240`
   - `CATSCAN_CONVERSIONS_WEBHOOK_RATE_LIMIT_WINDOW_SECONDS=60`
4. Security posture visibility:
   - `GET /conversions/security/status` (non-secret control state for auth/HMAC/freshness/rate-limit)

Recommended canary command for full webhook security suite:

```bash
CATSCAN_CANARY_WEBHOOK_SECRET=<generic_or_shared_secret_if_enabled> \
CATSCAN_CANARY_WEBHOOK_HMAC_SECRET=<generic_or_shared_hmac_secret> \
CATSCAN_CANARY_WEBHOOK_RATE_LIMIT_PER_WINDOW=1 \
CATSCAN_CANARY_WEBHOOK_RATE_LIMIT_WINDOW_SECONDS=60 \
CATSCAN_CANARY_MIN_SECURED_WEBHOOK_SOURCES=1 \
make v1-canary-webhook-security
```

## 6. Operational Notes

1. Keep human approval mandatory in v1; do not auto-apply proposals.
2. Prefer queue apply mode for first pass on any new model.
3. Treat high rejected conversion postbacks as a data-quality incident.
4. If model validation is intermittent, pause applies and fallback to rules model.
5. Use `GET /conversions/pixel` only for lightweight web-event instrumentation; treat repeated pixel rejections as connector incidents and inspect DLQ.

## 7. CI-Driven Closeout (GitHub Actions)

### 7.1 Required repository secrets

At least one of these must be configured for deployed canary auth:

1. `CATSCAN_CANARY_BEARER_TOKEN`
2. `CATSCAN_CANARY_SESSION_COOKIE`

### 7.2 Manual deployed closeout workflow

Workflow: `.github/workflows/v1-closeout-deployed.yml`

Dispatch inputs:

1. `api_base_url` (required, default `https://scan.rtb.cat/api`)
2. `buyer_id` (optional)
3. `model_id` (optional)
4. `canary_profile` (`safe|balanced|aggressive`, default `balanced`)
5. `qps_page_slo_since_hours` (required, default `24`)
6. `allow_blocked` (`true|false`, default `false`)

Recommended production dispatch values:

1. `canary_profile=balanced`
2. `qps_page_slo_since_hours=24`
3. `allow_blocked=false`

Recommended staging/restricted-network dispatch values:

1. `allow_blocked=true` (records blocked checks instead of hard-failing)

### 7.3 Workflow outputs and evidence

1. Job summary: rendered from `/tmp/v1_closeout_last_run.json`.
2. Artifact name: `v1-closeout-deployed-report`.
3. Artifact files:
   - `/tmp/v1_closeout_last_run.md`
   - `/tmp/v1_closeout_last_run.json`

### 7.4 Related CI workflows

1. `.github/workflows/v1-closeout-quick.yml`:
   - push/PR quick profile gate for core closeout checks.
2. `.github/workflows/v1-byom-api-regression.yml`:
   - push/PR BYOM optimizer API/e2e regression in dependency-provisioned runner.
