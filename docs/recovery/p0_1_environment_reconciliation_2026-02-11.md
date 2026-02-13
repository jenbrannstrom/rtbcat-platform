# P0.1 Environment Reconciliation

**Execution Date:** 2026-02-11
**Execution Window:** 11:54:15 UTC — 12:00:56 UTC
**Local HEAD:** 821c287 (`unified-platform`)
**Constraints:** Read-only. No code changes, no deploys, no imports, no schema changes.

---

## Step 1: SHA Verification

### Container APP_VERSION (env var)

| VM | Hostname | APP_VERSION | Check Time (UTC) |
|----|----------|-------------|-------------------|
| catscan-production-sg | scan.rtb.cat | `sha-02d1f53` | 2026-02-11T11:54:15Z |
| catscan-production-sg2 | vm2.scan.rtb.cat | `sha-02d1f53` | 2026-02-11T11:55:07Z |

**FACT: Both VMs run identical SHA `sha-02d1f53`.**

### /api/health (external)

| VM | URL | HTTP Status | Version | Latency |
|----|-----|-------------|---------|---------|
| sg | `https://scan.rtb.cat/api/health` | 200 (OAuth2 proxy sign-in page) | N/A | 1.410s |
| sg2 | `https://vm2.scan.rtb.cat/api/health` | 200 | `sha-02d1f53` | 1.147s |

**FACT: VM1 (sg) /api/health is behind OAuth2 Proxy and returns a sign-in page externally. VM2 (sg2) returns the health JSON directly.**
**FACT: VM2 health confirms `sha-02d1f53`, git_sha `02d1f536`.**

### Container filesystem check

| VM | .git_sha file | git rev-parse | grep home_analytics_service.py line 414 |
|----|---------------|---------------|----------------------------------------|
| sg | not present | git not in container | `"observed_query_rate_qps_avg": round(observed_qps, 2),` |
| sg2 | not present | git not in container | `"observed_query_rate_qps_avg": round(observed_qps, 2),` |

**FACT: Both containers have identical code at line 414. No `.git_sha` marker file. No git binary in container image.**

---

## Step 2: Drift Assessment

**Result: NO DRIFT.**

Both VMs run `sha-02d1f53`. Code is identical. No deploy needed.

**Note:** Local repo HEAD (`821c287`) is 8 commits ahead of deployed (`02d1f53`). Commits in local but NOT deployed:

```
821c287 Normalize contract catalog as app-wide normative spec
a8e6d8f Add app-wide data pipeline recovery plan with phased gates
9f65ba3 Separate endpoint-observed QPS from funnel proxy in efficiency panel
02d1f53 Show config-delay spinner inline in warning banner  <-- DEPLOYED
```

Key undeployed commit: `9f65ba3` (semantic fix for C-API-001).

---

## Step 3: Deploy Decision

**No deploy executed.** Both VMs are at the same SHA. Per instructions: "If sg2 is behind, deploy latest unified-platform SHA to sg2 only." Condition not met — no action taken.

---

## Step 4: Targeted Checks (Both VMs)

### C-API-001: Semantic Field Check

| VM | endpoint_delivery_state present | funnel_proxy_qps present | observed_query_rate_qps_avg (old) present | C-API-001 |
|----|--------------------------------|-------------------------|------------------------------------------|-----------|
| sg | false | false | true (line 414) | **FAIL** |
| sg2 | false | false | true (line 414) | **FAIL** |

**FACT: Both VMs fail C-API-001. Semantic fix (commit 9f65ba3) is NOT deployed on either VM.**

### /api/health Payload

| VM | Check Time (UTC) | status | version | configured | database_exists |
|----|-------------------|--------|---------|------------|-----------------|
| sg | 2026-02-11T12:00:46Z | healthy | sha-02d1f53 | true | true |
| sg2 | 2026-02-11T12:00:56Z | healthy | sha-02d1f53 | true | true |

**FACT: Both VMs report healthy status.**

### Endpoint-Efficiency Timing (buyer=6574658621, days=7)

Method: direct SQL from inside container (same as P0 baseline — HTTP auth bypass).

| VM | Latency (s) | rtb_endpoints_current rows | proxy_qps_avg | SLO (<0.5s) |
|----|-------------|---------------------------|---------------|-------------|
| sg | 0.107 | 0 | 6299.49 | **PASS** |
| sg2 | 0.091 | 0 | 6299.49 | **PASS** |

**FACT: Both VMs return identical data (shared database). Query latency well within SLO.**

---

## Step 5: Summary

| Check | sg | sg2 | Match |
|-------|-----|------|-------|
| APP_VERSION | sha-02d1f53 | sha-02d1f53 | YES |
| Code line 414 | observed_query_rate_qps_avg | observed_query_rate_qps_avg | YES |
| C-API-001 | FAIL | FAIL | YES |
| Health status | healthy | healthy | YES |
| Efficiency SLO | PASS (0.107s) | PASS (0.091s) | YES |
| rtb_endpoints_current | 0 rows | 0 rows | YES |

**Environment state: CONSISTENT. No drift. No deploy needed.**
**C-API-001 remains FAIL on both VMs (requires deploying 9f65ba3, which is Phase 4 scope).**

---

## Commands Executed

```bash
# SHA verification - VM1
gcloud compute ssh catscan-production-sg --zone=asia-southeast1-b --tunnel-through-iap \
  --command="sudo docker exec catscan-api printenv APP_VERSION; \
             sudo docker exec catscan-api grep -n 'endpoint_delivery_state\|observed_query_rate_qps\|funnel_proxy_qps' \
             /app/services/home_analytics_service.py"
# Timestamp: 2026-02-11T11:54:15Z

# SHA verification - VM2
gcloud compute ssh catscan-production-sg2 --zone=asia-southeast1-b --tunnel-through-iap \
  --command="sudo docker exec catscan-api printenv APP_VERSION; \
             sudo docker exec catscan-api grep -n 'endpoint_delivery_state\|observed_query_rate_qps\|funnel_proxy_qps' \
             /app/services/home_analytics_service.py"
# Timestamp: 2026-02-11T11:55:07Z

# External health checks
curl -s -w '\nHTTP %{http_code} %{time_total}s' "https://scan.rtb.cat/api/health"
# Timestamp: 2026-02-11T11:56:27Z — Result: OAuth2 proxy sign-in page

curl -s -w '\nHTTP %{http_code} %{time_total}s' "https://vm2.scan.rtb.cat/api/health"
# Timestamp: 2026-02-11T11:59:25Z — Result: 200 sha-02d1f53

# Targeted checks - VM1 (inside container)
gcloud compute ssh catscan-production-sg --zone=asia-southeast1-b --tunnel-through-iap \
  --command="sudo docker exec -e PYTHONPATH=/app -w /app catscan-api python3 /tmp/p0_1_check.py"
# Timestamp: 2026-02-11T12:00:46Z

# Targeted checks - VM2 (inside container)
gcloud compute ssh catscan-production-sg2 --zone=asia-southeast1-b --tunnel-through-iap \
  --command="sudo docker exec -e PYTHONPATH=/app -w /app catscan-api python3 /tmp/p0_1_check.py"
# Timestamp: 2026-02-11T12:00:56Z
```
