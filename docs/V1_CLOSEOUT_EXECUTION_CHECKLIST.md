# V1 Closeout Execution Checklist (Ops Template)

Use this template to execute and capture final closeout evidence for v1.

## 1. Preconditions

- [ ] Repository secrets configured (at least one):
  - `CATSCAN_CANARY_BEARER_TOKEN`
  - `CATSCAN_CANARY_SESSION_COOKIE`
- [ ] Target branch confirmed (default: `unified-platform`)
- [ ] Target environment/API URL confirmed (default: `https://scan.rtb.cat/api`)
- [ ] Buyer scope confirmed (`buyer_id`) for evidence runs

## 2. Dispatch Payloads (Exact)

Fast path (recommended, avoids CLI quoting mistakes):

```bash
scripts/run_v1_closeout_deployed_dispatch.sh --buyer-id <BUYER_ID> --run-byom
```

Equivalent via `make`:

```bash
CATSCAN_BUYER_ID=<BUYER_ID> make v1-closeout-dispatch
```

### 2.1 Deployed closeout (strict/prod)

Workflow: `.github/workflows/v1-closeout-deployed.yml`

`gh workflow run`:

```bash
gh workflow run v1-closeout-deployed.yml \
  --ref unified-platform \
  -f api_base_url=https://scan.rtb.cat/api \
  -f buyer_id=<BUYER_ID> \
  -f model_id= \
  -f canary_profile=balanced \
  -f qps_page_slo_since_hours=24 \
  -f allow_blocked=false
```

Equivalent REST dispatch payload:

```json
{
  "ref": "unified-platform",
  "inputs": {
    "api_base_url": "https://scan.rtb.cat/api",
    "buyer_id": "<BUYER_ID>",
    "model_id": "",
    "canary_profile": "balanced",
    "qps_page_slo_since_hours": "24",
    "allow_blocked": "false"
  }
}
```

`gh api` example:

```bash
gh api repos/jenbrannstrom/rtbcat-platform/actions/workflows/v1-closeout-deployed.yml/dispatches \
  -X POST \
  -f ref=unified-platform \
  -f inputs[api_base_url]=https://scan.rtb.cat/api \
  -f inputs[buyer_id]=<BUYER_ID> \
  -f inputs[model_id]= \
  -f inputs[canary_profile]=balanced \
  -f inputs[qps_page_slo_since_hours]=24 \
  -f inputs[allow_blocked]=false
```

### 2.2 Deployed closeout (diagnostic/restricted network)

Use only for environments where blocked network checks should be recorded, not failed.

```json
{
  "ref": "unified-platform",
  "inputs": {
    "api_base_url": "https://scan.rtb.cat/api",
    "buyer_id": "<BUYER_ID>",
    "model_id": "",
    "canary_profile": "balanced",
    "qps_page_slo_since_hours": "24",
    "allow_blocked": "true"
  }
}
```

### 2.3 BYOM API/e2e regression (manual dispatch)

Workflow: `.github/workflows/v1-byom-api-regression.yml`

`gh workflow run`:

```bash
gh workflow run v1-byom-api-regression.yml --ref unified-platform
```

Equivalent REST dispatch payload:

```json
{
  "ref": "unified-platform"
}
```

`gh api` example:

```bash
gh api repos/jenbrannstrom/rtbcat-platform/actions/workflows/v1-byom-api-regression.yml/dispatches \
  -X POST \
  -f ref=unified-platform
```

## 3. Evidence Collection Checklist

### 3.1 Deployed closeout run

- [ ] Run URL captured: `https://github.com/jenbrannstrom/rtbcat-platform/actions/runs/<RUN_ID>`
- [ ] Job summary reviewed (`V1 Closeout Deployed Report`)
- [ ] Artifact `v1-closeout-deployed-report` downloaded
- [ ] `v1_closeout_last_run.json` attached to closeout evidence pack
- [ ] Gate outcomes:
  - [ ] `Deployed canary go/no-go` = `PASS`
  - [ ] `Deployed QPS strict SLO canary` = `PASS`

### 3.2 BYOM API/e2e regression run

- [ ] Run URL captured: `https://github.com/jenbrannstrom/rtbcat-platform/actions/runs/<RUN_ID>`
- [ ] Workflow conclusion = `success`
- [ ] Failing tests (if any) triaged/resolved before closure

### 3.3 Buyer-scoped QPS SLO evidence

Collect API evidence snapshot (replace token mode as needed):

```bash
curl -sS \
  -H "Authorization: Bearer ${CATSCAN_CANARY_BEARER_TOKEN}" \
  "https://scan.rtb.cat/api/system/ui-metrics/page-load/summary?buyer_id=<BUYER_ID>&since_hours=24&min_samples=1&api_rollup_limit=10&bucket_hours=6&bucket_limit=8" \
  | tee /tmp/v1_qps_slo_summary_<BUYER_ID>.json
```

- [ ] `sample_count >= 1` (or agreed minimum)
- [ ] `p95_first_row_ms <= 6000`
- [ ] `p95_hydrated_ms <= 8000`
- [ ] API rollup includes startup paths used by canary checks

## 4. Closeout Sign-Off Record

- Date (UTC): `____________________`
- Branch / commit: `____________________`
- Buyer scope: `____________________`
- Deployed closeout run URL: `____________________`
- BYOM regression run URL: `____________________`
- SLO evidence file/link: `____________________`
- Final decision:
  - [ ] Close v1 plan as complete
  - [ ] Keep operational pending with follow-up actions

## 5. Follow-Up If Not Complete

- [ ] Open/append issue with blocking evidence
- [ ] Link affected workflow run URLs
- [ ] Define owner + ETA for rerun
