# Claude Prompt: Gmail + Import Hotfix and Smoke Validation (VM2 -> VM1)

Use this prompt as-is in Claude.

---

You are operating on the RTBcat/Cat-Scan infra. Execute these steps in order, do not skip verification. Work in a code-review + ops-debug mindset: show findings first, then fixes, then proof.

## Goal

1. Confirm whether Gmail data import reached BigQuery and whether precompute results reached Postgres.
2. Fix CSV import errors seen by user:
- `Chunk upload failed (HTTP 413)`
- `Import failed` with 0 rows and poor error visibility.
3. Ensure Gmail Cloud Scheduler endpoint is reachable (not blocked by OAuth2 nginx routing).
4. Apply and verify on VM2 first, then promote same pattern to VM1 (production).

## Constraints

- Do not use destructive git commands.
- Do not revert unrelated local changes.
- Prefer non-interactive commands.
- If you hit infra auth/network limits, state exact blocker and provide next command for operator.

## Files expected to contain fixes already (verify they exist)

- `terraform/gcp/startup.sh`
- `terraform/gcp_sg_vm2/startup.sh`
- `terraform/gcp_sg_vm2/nginx-catscan.conf`
- `dashboard/src/lib/chunked-uploader.ts`
- `api/routers/performance.py`
- `dashboard/src/components/import/ImportResultCard.tsx`

## Step 1: Verify code deltas are present

Run and summarize:

```bash
git diff -- \
  terraform/gcp/startup.sh \
  terraform/gcp_sg_vm2/startup.sh \
  terraform/gcp_sg_vm2/nginx-catscan.conf \
  dashboard/src/lib/chunked-uploader.ts \
  api/routers/performance.py \
  dashboard/src/components/import/ImportResultCard.tsx
```

Check for these exact intents:

1. Nginx has `client_max_body_size 200m;`
2. Nginx has explicit `location = /api/gmail/import/scheduled` proxy to API
3. OAuth2 skip routes include `/api/gmail/import/scheduled`
4. Chunk size in frontend is `512 * 1024`
5. Backend import response falls back to first error when `error_message` is empty
6. Import result card shows `errors[0]` when `error` missing

## Step 2: Deploy to VM2 and validate imports/Gmail

### 2.1 Sync code to VM2 and restart app stack

Use your standard deploy flow for VM2 (image/tag or in-place if required). Ensure nginx config on VM2 contains:

- `client_max_body_size 200m;`
- `location = /api/gmail/import/scheduled { ... }`

Then:

```bash
sudo nginx -t && sudo systemctl reload nginx
sudo docker compose -f /opt/catscan/docker-compose.gcp.yml ps
```

### 2.2 VM2 smoke for import and auth

```bash
curl -k -i https://vm2.scan.rtb.cat/health
curl -k -i https://vm2.scan.rtb.cat/api/auth/check
```

### 2.3 VM2 check nginx route exists

```bash
sudo nginx -T | grep -n "api/gmail/import/scheduled"
sudo nginx -T | grep -n "client_max_body_size"
```

### 2.4 VM2 validate scheduler endpoint behavior

Without secret (should fail 403):

```bash
curl -k -i -X POST https://vm2.scan.rtb.cat/api/gmail/import/scheduled
```

With secret (should queue import, 200 JSON):

```bash
curl -k -i -X POST https://vm2.scan.rtb.cat/api/gmail/import/scheduled \
  -H "X-Gmail-Import-Secret: $GMAIL_IMPORT_SECRET"
```

### 2.5 VM2 manual CSV upload re-test

Re-test user file paths from UI and capture exact API response payload.

Expected improvements:

- 413 should no longer occur.
- If import fails, UI should now display first backend row/fatal error, not generic `Import failed`.

## Step 3: Confirm data pipeline status (BQ + Postgres)

### 3.1 BigQuery freshness and row counts

```bash
bq query --use_legacy_sql=false '
SELECT "raw_facts" AS table_name, MIN(metric_date) AS min_date, MAX(metric_date) AS max_date, COUNT(*) AS rows FROM `rtbcat_analytics.raw_facts`
UNION ALL
SELECT "rtb_daily", MIN(metric_date), MAX(metric_date), COUNT(*) FROM `rtbcat_analytics.rtb_daily`
UNION ALL
SELECT "rtb_bidstream", MIN(metric_date), MAX(metric_date), COUNT(*) FROM `rtbcat_analytics.rtb_bidstream`
UNION ALL
SELECT "rtb_bid_filtering", MIN(metric_date), MAX(metric_date), COUNT(*) FROM `rtbcat_analytics.rtb_bid_filtering`
'
```

### 3.2 Postgres precompute freshness on VM

```bash
sudo docker exec catscan-api sh -lc 'psql "$POSTGRES_SERVING_DSN" -c "
SELECT '\''home_config_daily'\'' AS t, MAX(metric_date) AS max_date, COUNT(*) AS rows FROM home_config_daily
UNION ALL
SELECT '\''home_geo_daily'\'', MAX(metric_date), COUNT(*) FROM home_geo_daily
UNION ALL
SELECT '\''home_publisher_daily'\'', MAX(metric_date), COUNT(*) FROM home_publisher_daily
UNION ALL
SELECT '\''home_size_daily'\'', MAX(metric_date), COUNT(*) FROM home_size_daily
UNION ALL
SELECT '\''rtb_daily'\'', MAX(metric_date), COUNT(*) FROM rtb_daily
UNION ALL
SELECT '\''rtb_bidstream'\'', MAX(metric_date), COUNT(*) FROM rtb_bidstream
UNION ALL
SELECT '\''rtb_bid_filtering'\'', MAX(metric_date), COUNT(*) FROM rtb_bid_filtering;
"'
```

### 3.3 If stale, trigger refresh and re-check

```bash
curl -k -i -X POST https://vm2.scan.rtb.cat/api/precompute/refresh/scheduled \
  -H "X-Precompute-Refresh-Secret: $PRECOMPUTE_REFRESH_SECRET"
```

Then rerun Postgres query above.

## Step 4: Promote to VM1 (Production)

After VM2 passes all checks, apply the same runtime/config pattern to VM1:

1. same app image/tag
2. same nginx fixes (`client_max_body_size`, dedicated Gmail scheduler route)
3. same scheduler endpoint verification
4. same BQ/Postgres freshness checks

Production smoke gates:

```bash
curl -k -i https://scan.rtb.cat/health
curl -k -i https://scan.rtb.cat/api/auth/check
curl -k -i -X POST https://scan.rtb.cat/api/gmail/import/scheduled
curl -k -i -X POST https://scan.rtb.cat/api/gmail/import/scheduled -H "X-Gmail-Import-Secret: $GMAIL_IMPORT_SECRET"
```

## Required output format (strict)

Return exactly these sections:

1. **Findings**
- ordered by severity
- include file/path and command evidence

2. **Fixes Applied**
- VM2 first, VM1 second
- include exact changed files and effective runtime commands

3. **Verification Evidence**
- BQ table freshness summary
- Postgres table freshness summary
- import test outcomes (including whether 413 resolved)
- Gmail scheduled endpoint status

4. **Remaining Risks / Follow-ups**
- open items only

If any command fails due auth/network, include the full failing command and next operator action.
