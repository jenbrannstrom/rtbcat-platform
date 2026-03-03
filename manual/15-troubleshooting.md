# Chapter 15: Troubleshooting Runbook

*Audience: DevOps, platform engineers*

## Login loop

**Symptoms:** User hits the login page, authenticates, gets redirected back
to the login page, loop repeats indefinitely.

**Root cause pattern:** Any database failure causes
`_get_or_create_oauth2_user()` to fail silently. `/auth/check` returns
`{authenticated: false}`. The frontend redirects to `/oauth2/sign_in`. Loop.

**Common triggers:**
- Cloud SQL Proxy container died or was restarted without restarting the API
- Network partition between VM and Cloud SQL instance
- Cloud SQL instance maintenance or restart

**Detection:**
- Browser: redirect counter triggers after 2 redirects in 30 seconds, showing
  an error/retry UI instead of looping
- API: `/auth/check` returns HTTP 503 (not 200) when the database is
  unreachable, with `auth_error` in the response
- Logs: look for connection refused or timeout errors in catscan-api logs

**Fix:**
1. Check Cloud SQL Proxy: `sudo docker ps | grep cloudsql`
2. If down: `sudo docker compose -f docker-compose.gcp.yml restart cloudsql-proxy`
3. Wait 10 seconds, then restart the API:
   `sudo docker compose -f docker-compose.gcp.yml restart api`
4. Verify: `curl -sS http://localhost:8000/health`

**Prevention:** The three-layer fix (applied Feb 2026):
1. Backend propagates DB errors via `request.state.auth_error`
2. `/auth/check` returns 503 when DB is unreachable
3. Frontend has redirect counter (max 2 in 30s) + error/retry UI

## Data-freshness timeout

**Symptoms:** `/uploads/data-freshness` returns 500, times out, or the
runtime health gate shows BLOCKED on data health.

**Root cause pattern:** The data-freshness query scans large tables
(`rtb_daily` at 84M rows, `rtb_bidstream` at 21M rows). If the query plan
degrades to a sequential scan instead of using indexes, it can take 160+
seconds.

**Detection:**
1. Hit the endpoint directly from the VM:
   ```bash
   curl -sS --max-time 60 -H 'X-Email: cat-scan@rtb.cat' \
     'http://localhost:8000/uploads/data-freshness?days=14&buyer_id=<ID>'
   ```
2. If it times out or returns 500, check the query plan:
   ```bash
   sudo docker exec catscan-api python -c "
   import os, psycopg
   conn = psycopg.connect(os.environ['POSTGRES_DSN'])
   for r in conn.execute('EXPLAIN (ANALYZE, BUFFERS) <query>').fetchall():
       print(list(r.values())[0])
   "
   ```
3. Look for `Parallel Seq Scan` on large tables. This is the problem.

**Fix pattern:**
- Rewrite GROUP BY queries as `generate_series + EXISTS` to force index
  lookups. See [Database Operations](14-database.md) for the pattern.
- Ensure `SET LOCAL statement_timeout` is used (not `SET` + `RESET`).
- Check that indexes `(buyer_account_id, metric_date DESC)` exist on all
  target tables.

## Gmail import failure

**Symptoms:** Data freshness grid shows "missing" cells for recent dates.
Import history has no recent entries.

**Detection:**
```bash
curl -sS -H 'X-Email: cat-scan@rtb.cat' \
  http://localhost:8000/gmail/status
```

Check: `last_reason`, `unread` count, `latest_metric_date`.

**Common causes:**
- Gmail OAuth token expired: re-authorize at `/settings/accounts` > Gmail tab
- Cloud SQL Proxy down: Gmail import writes to Postgres, so DB must be
  reachable
- Large `unread` count (30+): import may be stuck processing or the mailbox
  has a backlog

**Fix:**
1. If `last_reason` shows an error: restart the import job from the UI or API
2. If the token expired: re-authorize Gmail integration
3. If Cloud SQL is down: fix the database connection first (see login loop)

## Container restart ordering

**Symptom:** API logs show "connection refused" to port 5432 on startup.

**Cause:** The API container started before Cloud SQL Proxy was ready.

**Fix:** Restart with correct ordering:
```bash
sudo docker compose -f docker-compose.gcp.yml up -d cloudsql-proxy
sleep 10
sudo docker compose -f docker-compose.gcp.yml up -d api
```

Or restart everything (compose handles dependencies):
```bash
sudo docker compose -f docker-compose.gcp.yml up -d --force-recreate
```

## SET statement_timeout syntax error

**Symptom:** Endpoint returns 500 with error:
`syntax error at or near "$1" LINE 1: SET statement_timeout = $1`

**Cause:** psycopg3 converts `%s` to `$1` for server-side parameter binding,
but PostgreSQL's `SET` command does not support parameter placeholders.

**Fix:** Use f-string with validated integer:
```python
# Wrong:
conn.execute("SET statement_timeout = %s", (timeout_ms,))

# Right:
timeout_ms = max(int(statement_timeout_ms), 1)  # validated int
conn.execute(f"SET LOCAL statement_timeout = {timeout_ms}")
```

## Runtime health gate failure

**Symptom:** `v1-runtime-health-strict.yml` workflow fails.

**Triage:**
1. Check the workflow logs: `gh run view <id> --log-failed`
2. Look for FAIL vs. BLOCKED:
   - **FAIL** = something broke, investigate
   - **BLOCKED** = dependency missing (no data, no endpoint), may be
     pre-existing
3. Common pre-existing BLOCKED reasons:
   - "rtb_quality_freshness state is unavailable": no quality data for
     this buyer/period
   - "proposal has no billing_id": data setup issue
   - "QPS page API rollup missing required paths": analytics endpoint
     not populated yet
4. Compare against previous runs to identify regressions vs. pre-existing
   issues.

## Related

- [Health Monitoring](13-health-monitoring.md): monitoring tools
- [Database Operations](14-database.md): query and index details
- [Deployment](12-deployment.md): deploying fixes
