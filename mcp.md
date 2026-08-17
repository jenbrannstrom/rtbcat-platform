# RTBcat MCP — Handover & Customer-Setup Roadmap

> Status date: 2026-08-17. Part 1 records what is live and how to operate
> it. Part 2 is the roadmap for making customer setup self-serve — a plan,
> not a build order that has started.
>
> This file is public-safe by design: no customer identifiers, no tokens,
> no private infrastructure details. Operational specifics live in the
> gitignored internal handover.

---

## Part 1 — Handover: what is live today

### The service

- **`https://mcp.rtb.cat/mcp`** is serving in production (Streamable
  HTTP), deployed 2026-08-16 as part of release `f00f0a4b`.
- It is a **stateless, read-only adapter** over the `/agent/v1` Agent API:
  seven read tools (buyers, daily spend, data quality, creative search,
  creative detail, creative performance, asset references). It holds no
  database credentials and no secrets — it forwards the caller's
  `cat_agent_*` bearer token to the API, which enforces all authorization.
- **Buyer isolation is the API's**: a token scoped to one buyer sees
  exactly that buyer; cross-buyer requests 403/404 exactly as the Agent
  API does. Spend figures are withheld outside the canonical allocation
  lane; clicks are never served; every data source is precompute-only.
- **Rate limit**: in-app token bucket, 60 calls/min per token (429 with
  `retry_after_seconds`). There is currently **no edge rate limit**.
- Verified end-to-end from the open internet with a scoped pilot token on
  rollout day: correct single-buyer scoping, failure matrix, and live
  revocation.

### Operating levers

| Action | How |
|---|---|
| Dark the endpoint instantly | Redeploy with `--mcp-enabled false` (kill switch; `/health` stays up reporting `enabled:false`, `/mcp` returns 503) |
| Re-enable | Redeploy with `--mcp-enabled true` — recreates only the MCP container, zero API/dashboard downtime |
| Mint / revoke a token | `/admin/agent-tokens` dashboard page (sudo). Revocation takes effect on the token's next call |
| Verify a live tool call | `mcp-call` helper on the operator workstation |
| Roll back | Standard `rollback_app_release.sh`; pre-MCP releases render their archived compose and remove the MCP container automatically |

### Dates and duties

- **TLS certificate expires 2026-11-14.** Issuance is manual DNS-01; there
  is **no auto-renewal**. Re-issue in early November (procedure and ACME
  state location are in the internal handover).
- Token expiries are set at mint time (pilot: 30 days). Rotation is
  manual today.

### Known follow-ups (engineering, not started)

1. `"${MCP_IMAGE:-}"` unbound-variable fix in the three activate/rehearse
   release scripts (latent, off the deploy path).
2. Retry/settle delay in the ingress script's post-reload self-test.
3. Phase 5 hardening from `docs/MCP_READONLY_SERVER_PLAN.md`: contract
   tests, metrics/counters, stale-precompute surfacing.
4. OAuth decision gate (see M3 below).

---

## Part 2 — Roadmap: customer self-serve setup

**Goal:** a customer goes from "we want our AI tools to see our RTBcat
data" to a working MCP connection in minutes, without an RTBcat operator
in the loop — while keeping today's hard guarantee: a customer can only
ever see their own buyer's data.

**Where the friction is today:** an operator must mint the token in a
sudo-only page, deliver the plaintext out-of-band, and hand-hold the
client configuration. Docs are written for engineers of this repo, not
customers. Tokens are static secrets with manual rotation. No customer
can see their own usage.

### M1 — Polished manual onboarding (now; docs only, no code)

Make the operator-in-the-loop flow so smooth it feels self-serve.

- Public **quickstart guide** (one page): what the MCP server offers, who
  to ask for a token, and copy-paste config blocks for the major clients
  (Claude Desktop / Claude Code, Cursor, generic Streamable HTTP client),
  each with the token referenced via the client's secret mechanism —
  never inline.
- **Operator mint-and-deliver runbook**: naming convention, scope
  defaults, expiry defaults, secure one-time delivery of the plaintext
  (one-time-secret link, never chat/email), and a post-setup verification
  step the customer runs themselves.
- A short **"what your AI can and cannot see"** page for customer trust:
  read-only, own buyer only, no clicks, spend rules, rate limits.
- **Done when:** a new customer connects in under 10 minutes with exactly
  one operator touch (the mint), and support questions are answered by
  the guide, not by chat.

### M2 — Self-serve tokens in the dashboard (removes the operator)

Extend the existing `/admin/agent-tokens` machinery to customers.

- A **"My agent tokens"** page for non-sudo dashboard users: mint,
  rotate, and revoke tokens **for their own seat grants only** — scope
  ceiling derived from their existing buyer permissions, never wider.
- Reuse the proven UX: one-time plaintext reveal with a ready
  `mcpServers` config block; plaintext confined to transient component
  state.
- Guard rails: per-user token cap, default + maximum expiry, mandatory
  buyer scoping (no unscoped tokens from this surface), full audit trail
  (who minted/revoked what, when), per-token last-used display.
- Admin oversight: the sudo page lists all tokens including
  customer-minted ones; revocation authority stays with admins too.
- **Done when:** a customer with a dashboard login can connect an MCP
  client with zero operator involvement, and every token's lifecycle is
  auditable.

### M3 — OAuth for MCP clients (the deferred decision gate, now scheduled)

Static bearer tokens work but are the weakest link (copy-paste secrets,
manual rotation). Modern MCP clients support OAuth natively.

- Decide **build vs integrate**: FastMCP auth-provider backed by our own
  user store, versus an external IdP. Note the dependency: the
  deployment's external login providers are currently disabled/pending
  repair — that repair likely precedes an IdP-based choice.
- Target flow: customer clicks "connect" in their MCP client →
  authorization-code + PKCE against RTBcat → grants map to their existing
  seat permissions → short-lived access tokens, refresh handled by the
  protocol. No plaintext secret ever shown.
- Keep bearer tokens as a supported fallback for headless/server
  integrations (the M2 surface stays).
- **Done when:** a supported client connects with no copied secret, and
  scope is provably identical to the bearer-token path.

### M4 — Operational maturity for external traffic (parallel to M2/M3)

What "customers depend on it" requires beyond "it works".

- **Edge protections**: rate limiting / connection caps at nginx (today
  only the in-app 60/min exists), plus request-size and timeout tuning
  reviewed for streaming.
- **Automated TLS renewal** (DNS-01 hook or managed path) — removes the
  quarterly manual re-issue and its outage risk.
- **Per-customer observability**: tool-usage and error counters per
  token/buyer (Prometheus text format is enough), surfaced two ways —
  operator dashboards, and a simple usage view for the customer in M2's
  page. Stale-precompute warnings surfaced to clients.
- **Contracts**: versioned tool schemas, a changelog customers can watch,
  deprecation policy; Phase 5 contract tests gate releases.
- Status page or at least a documented health endpoint customers may
  poll.
- **Done when:** a token leak, a traffic spike, or a stale cache is
  visible and containable without SSH-ing into the host, and customers
  can self-diagnose "is it me or the server".

### M5 — Distribution and value expansion (later)

- Server metadata/discovery (`.well-known`, registry listings) so clients
  can find and describe the server automatically.
- Per-ecosystem connector documentation as MCP client support evolves.
- Phase 6 product-intelligence tools (promotion/product-mix summaries)
  as the headline value-add — separately gated, with its precompute jobs
  going through the durable job queue as already mandated in the plan.

### Sequencing

```
M1 (docs)          ──────►  immediately, this week
M2 (self-serve)    ──────►  next build slot; reuses admin-tokens code
M3 (OAuth)         ──────►  after the build-vs-integrate decision + login repair
M4 (ops maturity)  ──────►  start edge limits + cert automation alongside M2
M5 (distribution)  ──────►  when M2+M4 are done
```

Hard constraints that apply to every milestone: buyer isolation is
non-negotiable and enforced server-side; the public repo stays free of
customer identifiers; tokens/secrets never appear in docs or configs
committed anywhere; the kill switch and per-token revocation must keep
working exactly as they do today; analytics reads stay precompute-only.
