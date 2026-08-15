# RTBcat Read-Only MCP Server

The RTBcat MCP server is a stateless Streamable HTTP adapter over the
buyer-scoped `/agent/v1` API. It forwards the caller's own bearer credential on
every tool call. The MCP process has no database connection, service secret,
credential store, or credential-minting capability.

## Tools

| Tool | Description and limits |
|---|---|
| `rtbcat_list_buyers` | Lists only buyers visible to the caller's token and seat grants. |
| `rtbcat_search_creatives` | Searches one buyer's creatives over an inclusive window of at most 90 days; pages contain at most 100 rows and opaque cursors must be returned unchanged. |
| `rtbcat_get_creative` | Returns buyer-checked creative detail and destination diagnostics; inaccessible and nonexistent creatives share the same not-found response. |
| `rtbcat_get_creative_asset` | Returns buyer-checked thumbnail, video, HTML, and native asset reference URLs only; it never fetches asset bytes. |
| `rtbcat_get_daily_spend` | Returns canonical buyer-grain daily spend for an inclusive window of at most 90 days, including explicit missing-date evidence. |
| `rtbcat_get_creative_performance` | Returns precomputed evidence for 1–100 creatives over an inclusive window of at most 90 days. |
| `rtbcat_check_data_quality` | Compares canonical buyer spend with creative allocation for one buyer over an inclusive window of at most 90 days. |

Every buyer argument is checked by the Agent API against both the token's hard
scope and the identity's seat grants. Creative-performance batches are rejected
as a whole if any requested creative is outside that buyer.

Clicks are never available in creative evidence:
`rtbcat_get_creative_performance` always returns `clicks_available: false` and
`total_clicks: null`. Canonical daily-spend rows can contain buyer-grain clicks
from `rtb_buyer_spend_daily`; they are not creative-level clicks.

## Authentication and revocation

Use one per-identity `cat_agent_*` bearer token per client or workflow. Paste
the plaintext value returned at issuance into the MCP client's secret-aware
configuration and send it as `Authorization: Bearer ...`. The MCP server passes
that value through for the current request only; it does not mint, cache, store,
or log credentials.

A sudo user session issues credentials through `POST /agent/v1/tokens` (or
`/api/agent/v1/tokens` through the production edge). The request selects the
identity, buyer scope or `all_granted_buyers`, required read scopes, and expiry.
The plaintext credential is returned once. See [Agent API](AGENT_API.md) for
the complete issuance body and supported scopes.

Revoke a credential with a sudo user session through
`DELETE /agent/v1/tokens/{id}`. Revocation takes effect on the next tool call;
no MCP server restart is required. Replacing a revoked value in the client's
configuration is the only workstation-side rotation step.

## Configuration

Configuration is read once when the MCP process starts.

| Environment variable | Default | Meaning |
|---|---:|---|
| `CATSCAN_MCP_ENABLED` | off | Enables `/mcp` for `1`, `true`, `yes`, or `on` (case-insensitive). The process and `/health` remain available while disabled. |
| `RTBCAT_API_BASE_URL` | `http://api:8000` | Base URL for the Agent API. |
| `CATSCAN_MCP_PORT` | `8010` | Listener port. |
| `CATSCAN_MCP_RATE_LIMIT_PER_MINUTE` | `60` | In-process token-bucket capacity and per-minute refill rate for each hashed credential. |

`GET /health` is public and always returns HTTP 200 with
`{"enabled": true}` or `{"enabled": false}`. When disabled, `/mcp` returns
HTTP 503. This supports a healthy-container, dark-edge rollout.

## Spend safety

Creative search and creative-performance evidence uses allocated spend. When a
non-canonical provenance block contains an `allocation_status` other than
`reconciled`, the MCP result replaces every `*spend_micros` and
`avg_cpm_micros` field outside the allocation evidence with `null`, adds
`spend_figures_withheld: true`, and copies the untouched `allocation` block to
the result's top level. Spend rank, ordering, impressions, freshness,
`latest_complete_date`, and `missing_source_dates` remain available.

Reconciled evidence passes through unchanged. Canonical daily spend also passes
through unchanged when its allocation status is `not_applicable`, because its
spend comes directly from the canonical buyer-grain lane.

## Client configuration

The production endpoint will be `https://mcp.rtb.cat/mcp` using Streamable
HTTP. It is not deployed yet: the server package ships ahead of its container
wiring, and this endpoint does not serve until the deployment phase lands.
Replace the placeholder with the per-identity value returned once by the token
endpoint, preferably through the client's supported secret substitution:

```json
{
  "mcpServers": {
    "rtbcat": {
      "type": "streamable-http",
      "url": "https://mcp.rtb.cat/mcp",
      "headers": {
        "Authorization": "Bearer <cat_agent_token_returned_once>"
      }
    }
  }
}
```
