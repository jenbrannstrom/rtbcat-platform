# Chapter 13: Health Monitoring and Diagnostics

*Audience: DevOps, platform engineers*

## Health endpoints

### `/api/health`: liveness

Returns basic API status, git SHA, and version. Used by the deploy workflow
and external monitoring.

```bash
curl -sS https://your-deployment.example.com/api/health | jq .
```

### `/system/data-health`: data completeness

Returns data health status per buyer, including freshness state for each
report type. Accepts `days`, `buyer_id`, and `availability_state` parameters.

Used by the setup checklist and the runtime health gate.

## System Status page (`/settings/system`)

The UI shows:

| Check | What it monitors |
|-------|-----------------|
| Python | Runtime version and availability |
| Node | Next.js build and SSR status |
| FFmpeg | Video thumbnail generation capability |
| Database | Postgres connection and row counts |
| Thumbnails | Batch generation status and queue |
| Disk space | VM disk usage |

## Runtime health scripts

These scripts are the operational backbone for verifying the system works
end-to-end.

### `diagnose_v1_buyer_report_coverage.sh`

Diagnoses why a specific buyer has missing CSV coverage.

```bash
export CATSCAN_CANARY_EMAIL="user.com"
scripts/diagnose_v1_buyer_report_coverage.sh \
  --buyer-id <BUYER_ID> \
  --timeout 180 \
  --days 14
```

Checks (in order):
1. Seat mapping: buyer_id -> bidder_id
2. Import matrix: pass/fail/not_imported by CSV type
3. Data freshness: imported/missing cell coverage
4. Import history: recent import rows
5. Gmail status: unread count, last reason, latest metric date

Result: PASS or FAIL with specific diagnosis.

### `run_v1_runtime_health_strict_dispatch.sh`

Runs the full runtime health gate, which checks:

- API health
- Data health (freshness and dimension coverage)
- Conversion health and readiness
- QPS startup latency
- QPS page SLO summary
- Optimizer economics and models
- Model endpoint validation
- Score+propose workflow
- Proposal lifecycle
- Rollback dry-run

Each check returns PASS, FAIL, or BLOCKED (with reason).

### CI workflow: `v1-runtime-health-strict.yml`

Runs the strict gate in CI. Triggered manually via workflow_dispatch.

```bash
gh workflow run v1-runtime-health-strict.yml \
  --ref unified-platform \
  -f api_base_url="https://your-deployment.example.com/api" \
  -f buyer_id="<BUYER_ID>" \
  -f canary_profile="balanced" \
  -f canary_timeout_seconds="180"
```

## Canary authentication

Runtime scripts authenticate using environment variables:

| Variable | Purpose |
|----------|---------|
| `CATSCAN_CANARY_EMAIL` | X-Email header for direct API calls (VM-local) |
| `CATSCAN_BEARER_TOKEN` | Bearer token (CI environment, stored in GitHub secrets) |
| `CATSCAN_SESSION_COOKIE` | OAuth2 Proxy session cookie (CI environment) |

From the VM host, use `CATSCAN_CANARY_EMAIL` with `http://localhost:8000`.
From CI (external), use `CATSCAN_BEARER_TOKEN` or `CATSCAN_SESSION_COOKIE`
with `https://your-deployment.example.com/api`.

## Interpreting results

| Status | Meaning |
|--------|---------|
| **PASS** | Check succeeded, system healthy |
| **FAIL** | Check failed, investigate immediately |
| **BLOCKED** | Check could not complete due to a dependency (e.g., no data for this buyer, missing endpoint). Not necessarily a code bug. |

## Related

- [Deployment](12-deployment.md): deploy verification
- [Troubleshooting](15-troubleshooting.md): when health checks fail
- For media buyers: [Data Import](09-data-import.md) explains the data
  freshness grid in buyer-friendly terms.
