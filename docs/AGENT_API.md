# Outside Agent API

Use this API when an external agent needs to pull buyer-scoped precomputed stats
and write an email summary.

## Auth Model

Outside agents use revocable app tokens:

- standard token header: `Authorization: Bearer cat_agent_...`
- edge-gated token header: `X-CatScan-Agent-Token: cat_agent_...`
- optional edge gate: NGINX Basic Auth on `/api/agent/v1/*`
- tokens are stored as SHA-256 hashes, never plaintext
- plaintext is returned only once when the token is created
- each token is bound to a normal Cat-Scan user
- buyer isolation comes from `user_buyer_seat_permissions`
- each token is hard-scoped to one `buyer_id`
- current scope: `agent:stats:read`

Do not give outside agents the legacy `CATSCAN_API_KEY`. That key authenticates
as a sudo automation user and is for trusted internal operations only.

## Edge Gate

For public production deployments, enable NGINX Basic Auth in front of the
agent API so commodity bots do not reach FastAPI.

Set this runtime env value on the VM or in the GSM-backed runtime env:

```bash
CATSCAN_AGENT_API_HTPASSWD='agent:$apr1$...'
```

On GCP, store that htpasswd line in Secret Manager as:

```text
catscan-agent-api-htpasswd
```

`scripts/refresh_gcp_vm_runtime_env.sh` reads that optional secret and writes
`CATSCAN_AGENT_API_HTPASSWD` into `/etc/catscan.env` and `/opt/catscan/.env`.

Generate the htpasswd value from a secure operator machine:

```bash
openssl passwd -apr1
```

Then store it as:

```text
agent:<generated-hash>
```

When `scripts/apply_gcp_nginx_auth_contract.sh` runs, it writes
`/etc/nginx/catscan-agent-api.htpasswd` and adds Basic Auth to
`/api/agent/v1/*`.

When Basic Auth is enabled, use Basic Auth for the edge gate and pass the app
token in `X-CatScan-Agent-Token`. Do not put both Basic Auth and Bearer auth in
the `Authorization` header.

```bash
curl -u "agent:${CATSCAN_AGENT_BASIC_PASSWORD}" \
  -H "X-CatScan-Agent-Token: ${CATSCAN_AGENT_TOKEN}" \
  "https://YOUR_HOST/api/agent/v1/stats-summary?buyer_id=1487810529"
```

## Provision

Create or reuse a read-only app user with buyer-seat grants, then mint an agent
token.

Via the provisioning script:

```bash
POSTGRES_DSN='postgresql://...' \
python scripts/provision_creative_audit_agent.py \
  --skip-db-role \
  --app-email creative-audit-agent-1487810529@example.com \
  --buyer-id 1487810529 \
  --create-api-token \
  --api-token-name 'Daily summary agent - 1487810529'
```

The script prints `Agent API token: cat_agent_...` once. Store it in Secret
Manager or the external agent platform's secret store.

Via API as a sudo user:

```bash
curl -X POST https://YOUR_HOST/api/agent/v1/tokens \
  -H 'Content-Type: application/json' \
  -H 'Cookie: rtbcat_session=<sudo-session>' \
  -d '{
    "name": "Daily summary agent - 1487810529",
    "user_id": "AGENT_USER_ID",
    "buyer_id": "1487810529",
    "scopes": ["agent:stats:read"],
    "expires_in_days": 90
  }'
```

## Pull Stats

Validate auth:

```bash
curl https://YOUR_HOST/api/agent/v1/me \
  -H "Authorization: Bearer ${CATSCAN_AGENT_TOKEN}"
```

With NGINX Basic Auth enabled:

```bash
curl -u "agent:${CATSCAN_AGENT_BASIC_PASSWORD}" \
  -H "X-CatScan-Agent-Token: ${CATSCAN_AGENT_TOKEN}" \
  https://YOUR_HOST/api/agent/v1/me
```

Pull a summary payload:

```bash
curl "https://YOUR_HOST/api/agent/v1/stats-summary?buyer_id=1487810529&days=7&top_limit=10" \
  -H "Authorization: Bearer ${CATSCAN_AGENT_TOKEN}"
```

With NGINX Basic Auth enabled:

```bash
curl -u "agent:${CATSCAN_AGENT_BASIC_PASSWORD}" \
  -H "X-CatScan-Agent-Token: ${CATSCAN_AGENT_TOKEN}" \
  "https://YOUR_HOST/api/agent/v1/stats-summary?buyer_id=1487810529&days=7&top_limit=10"
```

For a one-buyer agent user, `buyer_id` may be omitted. Sudo or multi-buyer
agents must pass `buyer_id` explicitly.

## Response Contract

`GET /api/agent/v1/stats-summary` returns:

- `buyer`: buyer seat identity
- `period`: days, start date, end date
- `totals`: reached queries, impressions, bids, spend, clicks, win rate, CTR
- `top_publishers`
- `top_geos`
- `top_configs`
- `top_apps`
- `email_summary`: subject, bullets, and markdown ready for an email body
- `data_sources`: the precomputed tables used

The endpoint reads only precomputed tables:

- `home_seat_daily`
- `home_publisher_daily`
- `home_geo_daily`
- `home_config_daily`
- `rtb_app_daily`

It does not read raw report tables and does not mutate state.

## Manage Tokens

List metadata, without plaintext secrets:

```bash
curl https://YOUR_HOST/api/agent/v1/tokens \
  -H 'Cookie: rtbcat_session=<sudo-session>'
```

Revoke:

```bash
curl -X DELETE https://YOUR_HOST/api/agent/v1/tokens/TOKEN_ID \
  -H 'Cookie: rtbcat_session=<sudo-session>'
```

Agent tokens cannot create, list, or revoke agent tokens.

## Operational Notes

- Use one token per external agent or workflow.
- Prefer one buyer-scoped app user per client-facing agent.
- Rotate tokens at least every 90 days.
- Store tokens only in a secrets manager.
- Audit actions:
  - `agent_token_create`
  - `agent_token_revoke`
  - `agent_stats_summary_read`
