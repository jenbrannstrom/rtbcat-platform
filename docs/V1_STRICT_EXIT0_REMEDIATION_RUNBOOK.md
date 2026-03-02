# V1 Strict Exit-0 Remediation Runbook

**Last updated:** 2026-03-02 00:40 UTC  
**Scope buyer:** `1487810529`  
**Latest strict evidence run:** `22558379655` (15 PASS / 0 FAIL / 5 BLOCKED, exit `2`)

## 1. Objective

Reach strict deployed closeout pass (`exit 0`) for:

```bash
scripts/run_v1_closeout_deployed_dispatch.sh --buyer-id 1487810529 --allow-blocked false --run-byom
```

Strict pass requires all deployed canary checks to be PASS (no BLOCKED, no FAIL).

## 2. Current Blockers (Strict Run `22558379655`)

| Check | Current status | Owner | Exit-0 condition |
|---|---|---|---|
| Data health | BLOCKED (`/system/data-health` HTTP 500 timeout) | Ops + Backend | Endpoint returns HTTP 200 within timeout |
| Optimizer economics | BLOCKED (`/optimizer/economics/efficiency` HTTP 500 timeout) | Ops + Backend | Endpoint returns HTTP 200 within timeout |
| Conversion readiness | BLOCKED (`state=unavailable/not_ready`) | Ops + Data/Buyer | `state=ready`, accepted events present |
| Optimizer models | BLOCKED (no active model) | Buyer Operator | At least 1 active model for buyer |
| Proposal lifecycle | BLOCKED (cascade from no model/proposal) | Buyer Operator | Proposal lifecycle checks run and pass |

## 3. Authentication Baseline (for all checks)

Canary token now maps to `X-Email` identity (not Bearer auth token).

```bash
export CATSCAN_CANARY_EMAIL="${CATSCAN_CANARY_BEARER_TOKEN}"
```

Sanity check:

```bash
curl -sS -m 20 \
  -H "X-Email: ${CATSCAN_CANARY_EMAIL}" \
  "https://scan.rtb.cat/api/health"
```

## 4. Workstream A: Clear 500 Timeout Blocks (Ops + Backend)

Probe latency and status externally:

```bash
for path in \
  "/system/data-health?buyer_id=1487810529" \
  "/optimizer/economics/efficiency?buyer_id=1487810529&days=14"
do
  echo "=== ${path}"
  curl -sS -o /tmp/strict_probe.json -m 30 \
    -w "http=%{http_code} connect=%{time_connect}s ttfb=%{time_starttransfer}s total=%{time_total}s\n" \
    -H "X-Email: ${CATSCAN_CANARY_EMAIL}" \
    "https://scan.rtb.cat/api${path}"
  head -c 300 /tmp/strict_probe.json; echo
done
```

If either endpoint is still `500` or timing out, triage on production VM:

```bash
CLOUDSDK_PYTHON_SITEPACKAGES=1 gcloud compute ssh catscan-production-sg \
  --zone=asia-southeast1-b --tunnel-through-iap -- \
  "sudo docker ps --format 'table {{.Names}}\t{{.Status}}' | head -n 20"

CLOUDSDK_PYTHON_SITEPACKAGES=1 gcloud compute ssh catscan-production-sg \
  --zone=asia-southeast1-b --tunnel-through-iap -- \
  "sudo docker logs --tail 200 catscan-api"

CLOUDSDK_PYTHON_SITEPACKAGES=1 gcloud compute ssh catscan-production-sg \
  --zone=asia-southeast1-b --tunnel-through-iap -- \
  "sudo docker restart catscan-api"
```

Exit criterion:

1. `/api/system/data-health` returns `200`.
2. `/api/optimizer/economics/efficiency` returns `200`.
3. No repeated timeout/worker errors in `catscan-api` logs.

## 5. Workstream B: Make Conversion Readiness Pass (Ops + Data/Buyer)

Check conversion health/readiness/stats:

```bash
curl -sS -m 20 -H "X-Email: ${CATSCAN_CANARY_EMAIL}" \
  "https://scan.rtb.cat/api/conversions/health?buyer_id=1487810529"

curl -sS -m 20 -H "X-Email: ${CATSCAN_CANARY_EMAIL}" \
  "https://scan.rtb.cat/api/conversions/readiness?buyer_id=1487810529&days=14&freshness_hours=72"

curl -sS -m 20 -H "X-Email: ${CATSCAN_CANARY_EMAIL}" \
  "https://scan.rtb.cat/api/conversions/ingestion/stats?buyer_id=1487810529&days=14"
```

If accepted conversions are zero, ingest at least one test event:

```bash
curl -i -sS -m 20 \
  "https://scan.rtb.cat/api/conversions/pixel?buyer_id=1487810529&source_type=pixel&event_name=canary_purchase&event_value=1&currency=USD&event_ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

Then re-check readiness/stats (above).

Exit criterion:

1. `readiness.state=ready`.
2. `accepted_total > 0`.
3. Ingestion lag is known and within threshold.

## 6. Workstream C: Configure Active Model (Buyer Operator)

List models:

```bash
curl -sS -m 20 -H "X-Email: ${CATSCAN_CANARY_EMAIL}" \
  "https://scan.rtb.cat/api/optimizer/models?buyer_id=1487810529&include_inactive=true&limit=50"
```

If no active model exists, create a minimal rules model:

```bash
curl -sS -m 20 -X POST \
  -H "X-Email: ${CATSCAN_CANARY_EMAIL}" \
  -H "Content-Type: application/json" \
  "https://scan.rtb.cat/api/optimizer/models" \
  -d '{
    "buyer_id": "1487810529",
    "name": "strict-canary-rules",
    "description": "Rules model for strict closeout precondition",
    "model_type": "rules",
    "is_active": true,
    "input_schema": {},
    "output_schema": {}
  }'
```

If model exists but is inactive:

```bash
curl -sS -m 20 -X POST \
  -H "X-Email: ${CATSCAN_CANARY_EMAIL}" \
  "https://scan.rtb.cat/api/optimizer/models/<MODEL_ID>/activate?buyer_id=1487810529"
```

Exit criterion:

1. At least one active model is returned for buyer `1487810529`.
2. Score+propose creates a proposal in canary workflow.
3. Proposal lifecycle check can run against a real proposal id.

## 7. Final Validation Sequence

Run strict:

```bash
scripts/run_v1_closeout_deployed_dispatch.sh --buyer-id 1487810529 --allow-blocked false --run-byom
```

Interpretation:

1. `success` conclusion with deployed closeout report showing PASS for both deployed steps = strict exit-0 achieved.
2. Any `BLOCKED` in strict run = precondition still unresolved.

If strict fails, run evidence mode to capture diagnostics while keeping CI signal usable:

```bash
scripts/run_v1_closeout_deployed_dispatch.sh --buyer-id 1487810529 --allow-blocked true --run-byom
```
