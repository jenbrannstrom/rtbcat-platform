# Creative Audit Agent Access

Use this setup for an automation agent that audits creative language/country
mismatches with least privilege.

## Access model

Provision two separate credentials:

| Credential | Purpose | Privilege |
|------------|---------|-----------|
| Postgres role | Direct SQL reads for audit/reporting | `SELECT` only on buyer-scoped `agent_read` views |
| Cat-Scan app user | Calls refresh and language-scan API endpoints | `read` role plus explicit buyer-seat read grants |
| Agent API token | Pulls precomputed HTTP stats for email summaries | `agent:stats:read`, bound to the app user and optional buyer hard-scope |

Do not use the Postgres read-only role to trigger refreshes. Refreshes and
language scans write cache/analysis rows, so they should run through the app
API where auth, seat scope, and service configuration are enforced.

## Per-buyer reporting model

For customized client reports, use buyer-seat scope as the report boundary:

| Pattern | When to use |
|---------|-------------|
| One central reporting agent with all active buyers | Internal batch job generates every client's report and filters each query by `buyer_id` |
| One app user per buyer | A client-specific integration or workflow should only see one buyer seat |

The API already enforces buyer-seat visibility for non-sudo users. A per-buyer
app user should have role `read` and exactly one `user_buyer_seat_permissions`
grant.

The direct Postgres role created by this script is scoped to `agent_read` views
by default. Do not give direct raw-table DB credentials to clients. Direct SQL
access should use the `agent_read` schema, which filters rows by database-role
buyer grants stored in `agent_private.buyer_role_grants`.

## Provision

Run from the API host with `POSTGRES_DSN` or `DATABASE_URL` set to an admin or
owner connection string. Apply migrations first so the `agent_read` schema
exists:

```bash
python scripts/postgres_migrate.py
```

Then provision the buyer-scoped DB role and app user:

```bash
python scripts/provision_creative_audit_agent.py \
  --db-user catscan_creative_audit_agent \
  --app-email creative-audit-agent@example.com \
  --buyer-id 1487810529
```

If the agent needs direct SQL access to more than one Postgres database, run
the same command once per database with `POSTGRES_DSN` pointed at that database.

For all active buyer seats:

```bash
python scripts/provision_creative_audit_agent.py \
  --db-user catscan_creative_audit_agent \
  --app-email creative-audit-agent@example.com \
  --all-active-buyers
```

The script prints generated DB and app passwords unless passwords are supplied
through:

```bash
CATSCAN_CREATIVE_AUDIT_DB_PASSWORD=...
CATSCAN_CREATIVE_AUDIT_APP_PASSWORD=...
```

Rerunning without those variables generates new passwords and rotates both
credentials.

For an HTTP-only external agent, also create a bearer token:

```bash
python scripts/provision_creative_audit_agent.py \
  --skip-db-role \
  --app-email creative-audit-agent-1487810529@example.com \
  --buyer-id 1487810529 \
  --create-api-token
```

The token can call:

```bash
curl "https://YOUR_HOST/api/agent/v1/stats-summary?buyer_id=1487810529&days=7" \
  -H "Authorization: Bearer ${CATSCAN_AGENT_TOKEN}"
```

If NGINX Basic Auth is enabled for `/api/agent/v1/*`, use:

```bash
curl -u "agent:${CATSCAN_AGENT_BASIC_PASSWORD}" \
  -H "X-CatScan-Agent-Token: ${CATSCAN_AGENT_TOKEN}" \
  "https://YOUR_HOST/api/agent/v1/stats-summary?buyer_id=1487810529&days=7"
```

For one app user per buyer, run the script once per buyer with a buyer-specific
email:

```bash
python scripts/provision_creative_audit_agent.py \
  --app-email creative-audit-agent-1487810529@example.com \
  --db-user catscan_creative_audit_agent_1487810529 \
  --buyer-id 1487810529
```

Create an all-buyer internal DB role for a trusted report generator:

```bash
python scripts/provision_creative_audit_agent.py \
  --skip-app-user \
  --db-user catscan_creative_audit_agent \
  --all-active-buyers
```

Use `--db-all-buyers` only for trusted internal jobs that should automatically
see every buyer through `agent_read` views. Use `--grant-raw-public-read` only
for emergency/internal debugging; raw `public` table access is not buyer
isolated.

## Google Secret Manager

Yes, use Google Secret Manager (GSM) for the generated credentials. Recommended
secret layout:

| Secret | Consumer |
|--------|----------|
| `catscan-creative-audit-db-password-BUYER_ID` | Per-buyer SQL report job using `agent_read` |
| `catscan-creative-audit-app-password-BUYER_ID` | Per-buyer app/API workflow |
| `catscan-creative-audit-db-password-internal` | Trusted all-buyer internal report job |
| `catscan-creative-cache-refresh-secret` | Scheduler or trusted internal refresh job |
| `catscan-precompute-refresh-secret` | Scheduler or trusted internal refresh job |

Example:

```bash
printf '%s' 'DB_PASSWORD' | gcloud secrets create catscan-creative-audit-db-password-1487810529 --data-file=-
printf '%s' 'APP_PASSWORD' | gcloud secrets create catscan-creative-audit-app-password-1487810529 --data-file=-
```

For rotation, add a new secret version after rerunning the provisioning script:

```bash
printf '%s' 'NEW_PASSWORD' | gcloud secrets versions add catscan-creative-audit-db-password-1487810529 --data-file=-
```

Industry-standard defaults:

- Use one secret per credential and environment.
- Grant the runtime service account `roles/secretmanager.secretAccessor` only
  for the secrets it needs.
- Keep scheduler refresh secrets separate from app-user credentials.
- Prefer per-buyer app users for any client-specific integration.
- Prefer `agent_read` SQL views over raw table access.
- Do not store generated passwords in `.env`, tickets, logs, or report output.
- Rotate credentials when operators or client integrations change.

## SQL views

Direct SQL agents should use these views:

| View | Purpose |
|------|---------|
| `agent_read.accessible_buyers` | Buyer seats visible to the current database role |
| `agent_read.creative_language_country_signals` | Creative language, country, spend, and latest geo-linguistic analysis signals |
| `agent_read.creative_scan_queue` | Creatives that need language/geo scans, retries, refreshes, or review |
| `agent_read.buyer_daily_report_summary` | Buyer-level report completeness and mismatch counts |
| `agent_read.creative_performance_issues` | Creative inefficiency signals for report candidates |

## Read mismatch data

Preferred API:

```bash
curl -c /tmp/catscan-agent.cookie \
  -H "Content-Type: application/json" \
  -X POST "https://YOUR_HOST/api/auth/login" \
  -d '{"email":"creative-audit-agent@example.com","password":"APP_PASSWORD"}'

curl -b /tmp/catscan-agent.cookie \
  "https://YOUR_HOST/api/creatives/language-flag-coverage?buyer_id=1487810529&language_state=red&geo_state=red&limit=1000"
```

Useful filters:

| Query parameter | Use |
|-----------------|-----|
| `buyer_id` | Required for seat-scoped read users unless they have exactly one seat |
| `language_state=red` | Deterministic language/country mismatch |
| `geo_state=red` | AI/heuristic geo-linguistic mismatch |
| `days=7` | Serving-country lookback window |
| `search=CREATIVE_ID` | Narrow to one creative or campaign text match |

## Trigger scans and refreshes

Queue language and geo-linguistic scans for matching creatives:

```bash
curl -b /tmp/catscan-agent.cookie \
  -X POST "https://YOUR_HOST/api/creatives/language-flag-coverage/refresh?buyer_id=1487810529&refresh_limit=500&force=true&days=7"
```

Refresh active creative live-cache data with the scheduler secret:

```bash
curl -X POST \
  -H "X-Creative-Cache-Refresh-Secret: ${CREATIVE_CACHE_REFRESH_SECRET}" \
  "https://YOUR_HOST/api/creatives/cache/refresh/scheduled?days=7&limit=1000"
```

Refresh precomputed serving tables with the scheduler secret:

```bash
curl -X POST \
  -H "X-Precompute-Refresh-Secret: ${PRECOMPUTE_REFRESH_SECRET}" \
  "https://YOUR_HOST/api/precompute/refresh/scheduled"
```

Full Google sync endpoints such as `POST /api/seats/sync-all` require seat
admin or sudo access and should not be granted to a read-only audit agent.
Keep those on a scheduler or a separate operator account.
