# Cat-Scan Agent API Skill

Use this when an external agent needs read-only Cat-Scan reporting data over
HTTP.

## Access Model

The supported `/api/agent/v1` token model is one read-only token per Authorized
Buyers seat.

Do not use a single admin/all-account HTTP token for this API. Token creation in
the app requires a concrete `buyer_id` when the target user is `sudo` or has
multiple buyer grants, and the provisioning script also refuses to mint an API
token without a buyer hard-scope. A direct Postgres `agent_read` role can be
granted all-buyer access for trusted internal SQL jobs, but that is a different
credential type and not the HTTP Agent API contract.

Do not use the legacy `CATSCAN_API_KEY` for outside agents. It authenticates as
sudo automation and is not the buyer-scoped Agent API token.

## Production Tokens

Fresh 90-day `agent:stats:read` tokens were minted on 2026-07-02 and stored in
Google Secret Manager. Plaintext tokens are not stored in this file.

| Buyer ID | Buyer | App user | GSM secret |
|---|---|---|---|
| `1487810529` | Amazing Design Tools LLC | `creative-audit-agent-1487810529@example.com` | `catscan-agent-api-token-1487810529` |
| `6574658621` | Amazing Moboost | `stats-agent-6574658621@agents.local` | `catscan-agent-api-token-6574658621` |
| `6634662463` | Amazing MobYoung | `stats-agent-6634662463@agents.local` | `catscan-agent-api-token-6634662463` |
| `7942355670` | Amazing Start | `stats-agent-7942355670@agents.local` | `catscan-agent-api-token-7942355670` |
| `8087233591` | Tuky internet | `stats-agent-8087233591@agents.local` | `catscan-agent-api-token-8087233591` |

All five tokens expire on 2026-09-30 around 17:10 UTC.

Earlier active tokens for `1487810529` and `6574658621` were left active. Revoke
older token rows only after confirming no current consumer still uses them.

## Retrieve A Token

```bash
gcloud --account=billing@amazingdo.com \
  --project=catscan-prod-202601 \
  secrets versions access latest \
  --secret=catscan-agent-api-token-BUYER_ID
```

Store the returned value only in the calling agent's secret store or runtime
environment.

## Call The API

Validate a token:

```bash
curl https://scan.rtb.cat/api/agent/v1/me \
  -H "Authorization: Bearer ${CATSCAN_AGENT_TOKEN}"
```

Read a stats summary:

```bash
curl "https://scan.rtb.cat/api/agent/v1/stats-summary?buyer_id=BUYER_ID&days=7&top_limit=10" \
  -H "Authorization: Bearer ${CATSCAN_AGENT_TOKEN}"
```

Read daily spend:

```bash
curl "https://scan.rtb.cat/api/agent/v1/daily-spend?buyer_id=BUYER_ID&start_date=2026-07-01&end_date=2026-07-01" \
  -H "Authorization: Bearer ${CATSCAN_AGENT_TOKEN}"
```

If the edge Basic Auth gate is enabled, use Basic Auth for the edge and pass the
agent token in `X-CatScan-Agent-Token` instead of `Authorization`.

## Rotation

Rotate per buyer. Create a new token, add a new GSM secret version, update the
consumer, then revoke the old token row once the consumer is confirmed healthy.

Token metadata is safe to list; plaintext is returned only once at creation.
