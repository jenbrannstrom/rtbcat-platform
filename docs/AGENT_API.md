# Outside Agent API

Use this API when an external agent needs buyer-scoped, precomputed evidence
for summaries, creative review, or creative performance analysis.

## Auth Model

Outside agents use revocable app tokens:

- standard token header: `Authorization: Bearer cat_agent_...`
- edge-gated token header: `X-CatScan-Agent-Token: cat_agent_...`
- optional edge gate: NGINX Basic Auth on `/api/agent/v1/*`
- tokens are stored as SHA-256 hashes, never plaintext
- plaintext is returned only once when the token is created
- each token is bound to a normal Cat-Scan user
- buyer isolation comes from `user_buyer_seat_permissions`
- a token is hard-scoped to one `buyer_id`, or minted with
  `all_granted_buyers=true` (non-sudo users only) to cover every seat the
  user is granted — the seat grants then bound every request
- tokens for sudo users always require a single-buyer hard scope
- supported scopes:
  - `agent:stats:read` — stats summary and daily spend
  - `agent:creatives:read` — creative search and detail
  - `agent:creative-performance:read` — batch creative performance
  - `agent:assets:read` — creative asset references
- each read route enforces its own scope; `/me` accepts any valid token

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
  "https://YOUR_HOST/api/agent/v1/stats-summary?buyer_id=1111111111"
```

## Provision

Create or reuse a read-only app user with buyer-seat grants, then sign in as a
sudo user and open `https://YOUR_HOST/admin/agent-tokens`. The dashboard page
is the preferred issuance path: it validates the target, enforces scope and
buyer rules, writes an audit event, and reveals the plaintext token once.

For a multi-buyer research identity, grant the app user one seat permission
per allowed buyer and mint the token with `"all_granted_buyers": true`
(omit `buyer_id`). The token then stores no buyer hard-scope and every
request is bounded by the user's seat grants; each request must still name
one `buyer_id` explicitly.

Via the provisioning script (**deprecated** for token minting —
`--create-api-token` inserts directly into `agent_api_tokens`, bypassing API
validation and auditing; it now prints a deprecation warning):

```bash
POSTGRES_DSN='postgresql://...' \
python scripts/provision_creative_audit_agent.py \
  --skip-db-role \
  --app-email creative-audit-agent-1111111111@example.com \
  --buyer-id 1111111111 \
  --create-api-token \
  --api-token-name 'Daily summary agent - 1111111111'
```

The script prints `Agent API token: cat_agent_...` once. Store it in Secret
Manager or the external agent platform's secret store.

Alternatively, mint via the API as a sudo user:

```bash
curl -X POST https://YOUR_HOST/api/agent/v1/tokens \
  -H 'Content-Type: application/json' \
  -H 'Cookie: rtbcat_session=<sudo-session>' \
  -d '{
    "name": "Daily summary agent - 1111111111",
    "user_id": "AGENT_USER_ID",
    "buyer_id": "1111111111",
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
curl "https://YOUR_HOST/api/agent/v1/stats-summary?buyer_id=1111111111&days=7&top_limit=10" \
  -H "Authorization: Bearer ${CATSCAN_AGENT_TOKEN}"
```

With NGINX Basic Auth enabled:

```bash
curl -u "agent:${CATSCAN_AGENT_BASIC_PASSWORD}" \
  -H "X-CatScan-Agent-Token: ${CATSCAN_AGENT_TOKEN}" \
  "https://YOUR_HOST/api/agent/v1/stats-summary?buyer_id=1111111111&days=7&top_limit=10"
```

For a one-buyer agent user, `buyer_id` may be omitted. Sudo or multi-buyer
agents must pass `buyer_id` explicitly.

Pull date-explicit spend rows:

```bash
curl "https://YOUR_HOST/api/agent/v1/daily-spend?buyer_id=2222222222&start_date=2026-07-01&end_date=2026-07-13" \
  -H "Authorization: Bearer ${CATSCAN_AGENT_TOKEN}"
```

`include_empty=true` is the default. It returns one row for every requested
date so a missing source row cannot be mistaken for a genuine zero-spend day.
The maximum range per request is 90 days.

## List Visible Buyers

```bash
curl https://YOUR_HOST/api/agent/v1/buyers \
  -H "Authorization: Bearer ${CATSCAN_AGENT_TOKEN}"
```

Returns the buyer seats this identity can query, with metadata (display
name, bidder, active flag, currency). `scope.source` reports how visibility
was derived: `token_hard_scope` (single-buyer token), `seat_grants`
(all-granted-buyers token), or `sudo_unscoped_token` (legacy tokens only).

## Check Data Quality

```bash
curl "https://YOUR_HOST/api/agent/v1/data-quality?buyer_id=1111111111&start_date=2026-07-01&end_date=2026-07-31" \
  -H "Authorization: Bearer ${CATSCAN_AGENT_TOKEN}"
```

Compares canonical buyer spend (`rtb_buyer_spend_daily`) with
creative-allocated spend (`config_creative_daily`) per day and in total.
The two lanes have different grains, so creative-level dollar figures are
trustworthy only when `allocation.allocation_status` is `reconciled` for
the same buyer and window; otherwise treat creative spend as a relative
ranking signal. `tolerance_pct` (default 1.0) controls the reconciliation
threshold. The response carries per-day rows, totals, warnings, and a
`provenance` block.

## Search Creatives

```bash
curl "https://YOUR_HOST/api/agent/v1/creatives?buyer_id=buyer-1&start_date=2026-07-01&end_date=2026-07-31&limit=50" \
  -H "Authorization: Bearer ${CATSCAN_AGENT_TOKEN}"
```

`GET /api/agent/v1/creatives` searches one buyer's creatives. It accepts an
inclusive date window of up to 90 days and optional `domain`, `format`,
`approval_filter`, `activity`, and `search` filters. `domain` matches the
stored final or display URL host, including subdomains. `activity=active`
means the creative has positive precomputed spend or impressions in the
requested window. Free text searches creative ID, name, advertiser, and UTM
campaign.

Results are ordered by spend descending and creative ID ascending. `sort_by`
accepts only `spend`; clicks are not present in this precompute. Pages contain
at most 100 creatives. Pass the opaque `next_cursor` unchanged to resume this
stable ordering.

Each compact result includes destination and resolved-destination evidence,
an asset-reference URL, spend rank, and metric provenance. The endpoint reads
`creatives` and `config_creative_daily` only.

## Read Creative Detail

```bash
curl "https://YOUR_HOST/api/agent/v1/creatives/creative-1" \
  -H "Authorization: Bearer ${CATSCAN_AGENT_TOKEN}"
```

`GET /api/agent/v1/creatives/{creative_id}` returns stored creative detail and
destination diagnostics. A creative outside the token's buyer access returns
the same not-found response as a nonexistent creative. The endpoint reads
`creatives` only.

## Read Creative Asset References

```bash
curl "https://YOUR_HOST/api/agent/v1/creatives/creative-1/assets" \
  -H "Authorization: Bearer ${CATSCAN_AGENT_TOKEN}"
```

`GET /api/agent/v1/creatives/{creative_id}/assets` returns thumbnail, video,
HTML, and native image references produced by the preview builder. The payload
contains references only, never asset bytes. A creative outside the token's
buyer access uses the same not-found response as a nonexistent creative. The
endpoint reads `creatives` only; preview construction performs no database
query.

## Batch Creative Performance

```bash
curl -X POST "https://YOUR_HOST/api/agent/v1/creative-performance/batch" \
  -H "Authorization: Bearer ${CATSCAN_AGENT_TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{
    "buyer_id": "buyer-1",
    "creative_ids": ["creative-1", "creative-2"],
    "start_date": "2026-07-01",
    "end_date": "2026-07-31"
  }'
```

`POST /api/agent/v1/creative-performance/batch` accepts 1–100 creative IDs for
one buyer and an inclusive date window of up to 90 days. Input order is
preserved after duplicate IDs are removed. The endpoint reads creative
ownership from `creatives`, then metrics from `config_creative_daily` and
`performance_metrics`. A creative with no row in either metric precompute has
`metric_source: "unavailable"`. `clicks_available` is always `false` and
`total_clicks` is always `null`.

Every row carries metric provenance and an allocation reconciliation block.
That reconciliation uses the same data-quality contract and additionally
reads `buyer_seats`, `rtb_buyer_spend_daily`, and `config_creative_daily` for
the requested buyer and window.

## Metric Provenance

Every metrics response includes a `provenance` block:

- `metric_source`: the precomputed table behind the numbers
- `is_canonical`: true for the buyer-grain spend lane
- `buyer_scope`, `latest_complete_date`, `latest_source_date`,
  `missing_source_dates`
- `allocation`: reconciliation status plus canonical/allocated/difference
  micros (`not_applicable` when only one lane is involved)

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

Money fields use the buyer account's configured ISO-4217 currency:

- `buyer.currency` is the authoritative currency for the response.
- `totals.currency`, `totals.spend`, and `totals.avg_cpm` are the preferred
  fields for new `stats-summary` consumers.
- `totals.spend_micros` is one millionth of the buyer currency. It is not
  necessarily USD.
- `spend_usd` and `avg_cpm_usd` are compatibility aliases. They contain values
  only for USD seats and are `null` for EUR or unconfigured seats.
- Entries in `top_apps` follow the same currency contract.
- Email summaries prefix monetary amounts with the ISO code, for example
  `EUR 4,159.98`, and never add a dollar sign to non-USD spend.

Example currency portion for a EUR-configured seat (`2222222222`):

```json
{
  "buyer": {
    "buyer_id": "2222222222",
    "currency": "EUR"
  },
  "totals": {
    "spend_micros": 4159980000,
    "currency": "EUR",
    "spend": 4159.98,
    "spend_usd": null
  }
}
```

`GET /api/agent/v1/daily-spend` returns:

- `buyer.currency` and `data_source.currency`
- one date-explicit row per requested day by default
- `source_status`: `present` or `missing` for each row
- `summary.complete`, `summary.missing_dates`, and
  `summary.latest_complete_date`
- totals in `summary.total_spend_micros`, denominated in
  `data_source.currency`

Do not infer currency from CSV symbols or from a field name containing `usd`.
The Authorized Buyers source column is `Spend (buyer currency)`, while the
currency code is seat metadata. If a seat is not configured,
`buyer.currency` and `data_source.currency` are `null`; consumers must not
guess.

Both endpoints read only precomputed tables and never raw report tables:

- `GET /api/agent/v1/daily-spend` reads `rtb_buyer_spend_daily` (canonical
  buyer-grain spend/impressions/clicks; the response self-declares this in
  `data_source.table`) plus `rtb_app_daily` for the app/billing dimension
  counts.
- `GET /api/agent/v1/stats-summary` reads `home_seat_daily`,
  `home_publisher_daily`, `home_geo_daily`, `home_config_daily`,
  `rtb_buyer_spend_daily`, and `rtb_app_daily`.

Neither endpoint mutates report state.

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

## Configure Buyer Currency

Seat admins and sudo users can set or correct the currency independently of an
agent token:

```bash
curl -X PATCH https://YOUR_HOST/api/seats/2222222222 \
  -H 'Content-Type: application/json' \
  -H 'Cookie: rtbcat_session=<seat-admin-session>' \
  -d '{"currency":"EUR"}'
```

The value is normalized to uppercase and must be a three-letter ISO-4217 code.
Migration `071_buyer_seat_currency.sql` backfills the seats known at the time
it shipped with their configured currencies. New or unknown seats remain
unconfigured until an operator sets their currency.

## Operational Notes

- Use one token per external agent or workflow.
- Prefer one buyer-scoped app user per client-facing agent.
- Rotate tokens at least every 90 days.
- Store tokens only in a secrets manager.
- Audit actions:
  - `agent_token_create`
  - `agent_token_revoke`
  - `agent_stats_summary_read`
  - `agent_daily_spend_read`
  - `agent_buyers_read`
  - `agent_data_quality_read`
  - `agent_creatives_read`
  - `agent_asset_read`
  - `agent_creative_performance_read`
