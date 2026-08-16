# RTBcat Read-Only MCP Server — Delivery Plan

> **Status:** In delivery — see §0 for exact resume state (last updated
> 2026-08-16).
> **Scope:** A read-only, buyer-scoped remote MCP server for RTBcat, developed
> and open-sourced inside this repository and deployed beside the production
> API on Hetzner.
> This document is public-safe. The incident write-up that motivated it lives
> in `docs/internal/` (gitignored) and must never be committed: it contains
> customer identifiers.

## 0. Status — resume here

Everything below is on `main` and pushed; CI (Security Checks, v1 Regression
Gate, Schema Compatibility) was green on every listed commit.

**Done:**

| When | Commit | What |
|---|---|---|
| 2026-08-08 | `666dc589` | This plan committed (Phase 0; root scratch notes moved to gitignored `docs/internal/MCP-INCIDENT-BASELINE-2026-08-08.md`) |
| 2026-08-09 | `563a94f7` | Unrelated but load-bearing: dependency-scan CI on `main` fixed (aiohttp/cryptography/postcss bumps) — Security Checks is trustworthy again |
| 2026-08-09 | `b778891d` | **Phase 1 complete** — four scopes + `require_agent_scope` factory; `get_allowed_buyer_ids` returns all seat grants (D2); `all_granted_buyers=true` token shape (D3); thumbnail route buyer-checked (D4); provisioning-script token path deprecated; agent auth suites added to the release-gating list |
| 2026-08-09 | `409b96ee` | **Phase 2 slice 1 complete** — `MetricProvenance` envelope (`api/schemas/agent_provenance.py`) attached to daily-spend; `GET /agent/v1/buyers`; `GET /agent/v1/data-quality` (canonical vs allocated reconciliation, `services/agent_data_quality_service.py`) |
| 2026-08-15 | `39453e07..0fef58d8` (5 commits) | **Phase 2 slice 2 complete** — the four creative read contracts under `/agent/v1`: creatives search (cursor-paginated, spend-sort from `config_creative_daily` only), creative detail (destination diagnostics via `creative_destination_resolver`), asset references (no bytes), creative-performance batch (`metric_source: "unavailable"` for precompute misses, `clicks_available: false`, allocation block attached). New: `api/routers/agent_creatives.py`, `services/agent_creatives_service.py`, `services/agent_creative_performance_service.py`; 22 tests in two files, both on the release-gating list; `docs/AGENT_API.md` updated. A static-guard test asserts the new modules never reference the raw RTB table |
| 2026-08-16 | `eb1cb6d6..da084634` (5 commits; merged `41b4873f`, released `1acb8bd8`) | **Phase 3 complete** — standalone stateless MCP adapter, seven read tools over `/agent/v1`, token forwarding, in-process rate limiting, kill switch, non-root container, public guide, 43 MCP tests on the release gate, and end-to-end behavior verification against the production Agent API. The endpoint remained undeployed. |

**Current delivery: Phase 4 — build and deploy wiring.** The repository now
defines the third digest-pinned image, loopback-only Compose service,
manifest/deploy/verify/rollback handling, and the fixed MCP ingress generator.
This is code completion, not production rollout: publishing the image,
installing host scripts, DNS, TLS, ingress application, and pilot enablement
remain operator actions.

**Open items not owned by code:**

- `REDACTION_DENYLIST` org secret still needs the incident's customer
  identifiers (names, emails) and ideally the real buyer seat IDs — secret
  owner action, cannot be done from the repo.
- Real buyer seat IDs still appear in `.github/workflows/live-major-smoke.yml`
  (default input) and migration `071_buyer_seat_currency.sql`; the docs were
  scrubbed in `b778891d`.
- Behavior change to watch: non-sudo multi-seat users must now pass an
  explicit `buyer_id` (no more silent first-seat selection). No complaints
  yet; revisit if a dashboard user hits it.
- Legacy unscoped sudo tokens (minted by the old provisioning script) still
  work; `GET /agent/v1/buyers` reports them as
  `scope.source: "sudo_unscoped_token"`. Consider inventorying
  (`GET /agent/v1/tokens`) and revoking them once the research identity is
  migrated to an `all_granted_buyers` token.

**To verify state on reopen:**

```bash
git log --oneline -8                     # expect 0fef58d8 at or near HEAD
venv/bin/python -m pytest \
  tests/test_agent_api.py tests/test_agent_token_service.py \
  tests/test_agent_scope_and_seat_enforcement.py \
  tests/test_agent_data_quality.py \
  tests/test_agent_daily_spend_service.py \
  tests/test_agent_creatives.py \
  tests/test_agent_creative_performance.py -q   # 79 tests, all green
gh run list --branch main --limit 3      # CI conclusions for recent pushes
```

## 1. Summary

Agent clients (Codex, Claude Code, and other approved MCP clients) should be
able to answer routine RTBcat research questions — "which creatives is buyer X
running, what do they promote, how does spend rank them" — through **one MCP
connection**, with no gcloud, no browser login, no copied global API key, and
no knowledge of RTBcat's internal endpoint layout.

The build order is deliberate and matches the incident findings:

1. **Fix authorization first** — a dedicated, scoped, buyer-restricted research
   identity on the existing Agent API token model.
2. **Fix the HTTP contracts second** — stable `/agent/v1` read endpoints with
   explicit metric provenance and spend reconciliation status.
3. **Only then build the MCP server** — as a thin adapter over those
   contracts. The MCP layer must not paper over the current creative-spend
   reconciliation gap or inherit the global dashboard API key.

## 2. Goals and non-goals

**Goals**

- One remote MCP endpoint: `https://mcp.rtb.cat/mcp` (Streamable HTTP).
- Buyer isolation enforced on every tool call; scopes narrower than the
  existing all-or-nothing model.
- Every metrics response declares its source table, freshness, missing dates,
  and whether figures are canonical or allocated.
- Full audit trail per identity, buyer, tool, and timestamp.
- The MCP server ships as part of this public repo (MIT), built and deployed
  through the existing GHCR → `deploy_app_release.sh` pipeline.
- Production path depends only on the live Hetzner deployment — never on the
  frozen GCP stack.

**Non-goals**

- No mutation tools of any kind in this project.
- No new database access layer: the MCP server reuses the Agent API over HTTP;
  it holds no SQL.
- Product-intelligence classification (promotion type, OCR, landing-page
  categorisation) is a later, separately gated phase — not the MVP.
- No dependency on the global dashboard API key (`CATSCAN_API_KEY`) anywhere
  in the MCP path.

## 3. Current state (what the repo already gives us)

Findings from a code audit on 2026-08-08; file references are current as of
that date.

- **Agent API exists**: `api/routers/agent.py` under prefix `/agent/v1`
  (the `/api` segment is an edge rewrite, not an app route). Endpoints:
  `/me`, `/stats-summary`, `/daily-spend`, plus sudo-session token CRUD.
- **Token model exists**: `services/agent_token_service.py` +
  `agent_api_tokens` table (migration 068). `cat_agent_*` tokens, SHA-256
  stored, per-token expiry/revocation/last-used telemetry, per-token single
  `buyer_id` narrowing, comma-separated scopes. Today only one scope exists
  (`agent:stats:read`) and token creation rejects any other
  (`agent.py` scope allowlist).
- **Audit log exists**: `audit_log` table; the four agent actions are audited
  explicitly in-handler. There is no generic access-audit middleware.
- **Precompute discipline exists**: `config_creative_daily`,
  `performance_metrics`, `rtb_buyer_spend_daily`, `rtb_app_daily` are the
  approved batch lanes; `rtb_daily` (460M+ rows) is forbidden for batch reads
  (`CLAUDE.md`).
- **MCP prior art exists**: `scripts/catscan_mcp_db_smoke.py` +
  `docs/CATSCAN_MCP_DB_SMOKE.md` + `tests/test_catscan_mcp_db_smoke.py`
  (already gating releases in `build-and-push-ghcr.yml`) define the DB read
  contracts "deliberately close to future MCP tools". These remain the DB
  contract beneath the MCP server.
- **Deployment shape exists**: two digest-pinned GHCR images (`catscan-api`,
  `catscan-dashboard`) in `deploy/hetzner/compose.yml`, released by
  `scripts/hetzner/deploy_app_release.sh` from a `hetzner-release.env`
  manifest, verified by `verify_app_release.sh`.

**Known defects the plan must fix (not work around):**

| # | Defect | Where | Status |
|---|--------|-------|--------|
| D1 | Only one scope exists and `require_agent_context` hardcodes it for all reads | `agent.py`, `agent_token_service.py` | **Fixed** `b778891d` |
| D2 | Non-sudo users with >1 buyer seat are silently truncated to one seat | `api/dependencies.py` (`get_allowed_buyer_ids`) | **Fixed** `b778891d` (explicit `buyer_id` now required when multi-seat) |
| D3 | All-buyer tokens exist only via a provisioning script that bypasses API validation | `scripts/provision_creative_audit_agent.py` | **Fixed** `b778891d` (`all_granted_buyers` API shape; script path deprecated, legacy tokens still to be revoked) |
| D4 | Thumbnail route serves creative bytes with no buyer authorization | `api/routers/system.py` (`/thumbnails/{id}.jpg`) | **Fixed** `b778891d` |
| D5 | Batch performance falls back to `rtb_daily` for creatives missing from precompute; `sort_by=clicks` batch-queries `rtb_daily` | `creative_performance_repo.py`, `postgres_store.py` | Open (dashboard endpoints); the `/agent/v1` batch endpoint shipped without it (`7f07eeb4`) — precompute misses return `metric_source: "unavailable"`, enforced by test |
| D6 | Three spend lanes with different grains and no reconciliation: `rtb_buyer_spend_daily` (canonical, buyer grain), `config_creative_daily` (allocated, creative×config grain — double-counts across configs), `rtb_app_daily` (app lane) | services + repos | **Exposed** `409b96ee` (`/agent/v1/data-quality` reports it; the ETL gap itself remains) |
| D7 | Clicks exist only in `rtb_daily`; precompute lane returns `clicks_available=false` | `creative_performance_repo.py` | Open by design — the `/agent/v1` batch pins `clicks_available: false` / `total_clicks: null` in its schema (`7f07eeb4`) |
| D8 | No rate limiting anywhere except `/auth/bootstrap` | — | Open (planned in the MCP server, Phase 3) |
| D9 | Every `pg_query` opens a fresh psycopg connection (no pooling) | `storage/postgres_database.py` | Open (independent platform fix, see R1) |
| D10 | `docs/AGENT_API.md` documents the wrong source tables for `daily-spend` | docs | **Fixed** `b778891d` |

## 4. Target architecture

```
MCP client (Codex / Claude / other)
        │  Streamable HTTP + Bearer token (per-identity, scoped)
        ▼
https://mcp.rtb.cat/mcp        ← host nginx vhost (TLS, timeouts, buffering off)
        ▼
rtbcat-mcp container           ← new, third compose service, loopback-published
        │  forwards the caller's token on every request
        ▼
http://rtbcat-api:8000/agent/v1/*   ← compose network, existing API container
        ▼
services / repositories → precompute tables only
```

**Design decisions**

1. **Thin adapter over the Agent API, not direct DB access.** The MCP server
   forwards the caller's bearer token to `/agent/v1/*` on every call. Token
   validation, scope checks, buyer isolation, auditing, and revocation all
   stay in exactly one codebase (the API). The MCP process holds no DSN and
   no secrets beyond its own listener config. This also makes MCP↔API
   contract tests meaningful.
2. **Auth is phased.** MVP: per-identity `cat_agent_*` tokens (scoped,
   expiring, revocable, audited — pasted once into client config). This is
   explicitly *not* the global dashboard key. Full OAuth 2.1
   (authorization-code + PKCE per the MCP auth spec) is a hardening phase
   with a build-vs-integrate decision gate — it is the only acceptance
   criterion the MVP defers.
3. **Official Python MCP SDK** (`mcp` package, FastMCP server API),
   Streamable HTTP transport, stateless mode (no session affinity needed
   behind nginx). Python 3.11, matching the repo.
4. **Third container, same release discipline.** New GHCR image
   `catscan-mcp`, digest-pinned in the same manifest, deployed and verified
   by the same scripts. Nothing serves traffic that isn't a pushed,
   sha-tagged image.
5. **Precompute-first is enforced at the endpoint level.** The new
   `/agent/v1` read endpoints never touch `rtb_daily`. Where that means a
   field is unavailable (clicks), the contract says so
   (`clicks_available: false`) instead of silently switching lanes.
6. **Provenance is part of the contract.** Every metrics response carries:
   `metric_source`, `latest_complete_date`, `missing_source_dates`,
   `buyer_scope`, `precompute_freshness`, `is_canonical`, and
   `allocation_status` (`reconciled | non_reconciling | not_applicable`)
   with `canonical_spend_micros` / `allocated_spend_micros` /
   `difference_micros` when both lanes are involved.

## 5. Delivery phases

### Phase 0 — Repo hygiene (immediate, prerequisite)

- [x] Move the incident write-up out of the repo root into gitignored
      `docs/internal/` (done alongside this plan; the root `mcp.md` scratch
      file is removed).
- [ ] Add the incident's customer identifiers (names, personal email
      addresses) to the `REDACTION_DENYLIST` org secret so the CI redaction
      boundary catches any future reintroduction. (Secret owner action —
      cannot be done from the repo. **Still open as of 2026-08-09.**)
- [x] Commit this plan to `main` (`666dc589`).

### Phase 1 — Authorization foundation (fixes D1–D4) — SHIPPED `b778891d`

All changes in existing files; no new service yet.

1. **New scopes** in `services/agent_token_service.py`:
   `agent:creatives:read`, `agent:creative-performance:read`,
   `agent:assets:read` (keep `agent:stats:read`). Replace the single-constant
   check in `require_agent_context` with a per-route required-scope
   parameter; extend the creation allowlist in `agent.py`.
2. **Fix multi-seat truncation** (D2): `get_allowed_buyer_ids` must return
   *all* active seat grants for non-sudo users. Audit existing callers for
   assumptions about a single buyer before changing behavior; add a
   regression test.
3. **Sanctioned research identity** (D3): replace direct-INSERT provisioning
   with a supported path — either per-token multi-buyer grants via the
   user's seat permissions (now correct after step 2) or an explicit
   `buyer_ids` list column. A dedicated non-sudo user (e.g.
   `research-agent@rtb.cat` equivalent) holds seat grants for exactly the
   buyers research is allowed to see; tokens are minted against it through
   the normal sudo-session endpoint. Deprecate the bypass script.
4. **Buyer check on assets** (D4): the thumbnail route (and any new asset
   route) enforces `require_buyer_access` before serving bytes.
5. **Audit events** for each new read operation, following the existing
   `_audit_agent_read` pattern (`agent_creatives_read`,
   `agent_creative_performance_read`, `agent_asset_read`,
   `agent_data_quality_read`).
6. **Docs**: correct `docs/AGENT_API.md` source-table documentation (D10) and
   document the new scopes, rotation, and revocation (no workstation changes
   required: revoke = `DELETE /agent/v1/tokens/{id}`).

### Phase 2 — Agent API contract repair (fixes D5–D7 at the contract level)

**Slice 1 SHIPPED `409b96ee`** (buyers, daily-spend envelope, data-quality).
**Slice 2 SHIPPED `39453e07..0fef58d8`** (the four creative rows below) —
Phase 2 is complete.

New buyer-scoped read endpoints in `api/routers/agent.py` (or a sibling
`agent_creatives.py` router with the same prefix), each service-backed per
the router→service→repository convention:

| Endpoint | Backing | Notes | Status |
|---|---|---|---|
| `GET /agent/v1/buyers` | `buyer_seats` via seat grants | identity's visible buyers only | ✅ `409b96ee` |
| `GET /agent/v1/creatives` | `creatives` + `config_creative_daily` | filters: buyer, date window, domain, format, approval, activity, text; spend-ranked sort from precompute only; **no clicks sort**; cursor pagination | ✅ `39453e07` |
| `GET /agent/v1/creatives/{id}` | `creatives` | detail + destination diagnostics | ✅ `bfa7f6a4` |
| `GET /agent/v1/creatives/{id}/assets` | preview builder + thumbnail store | image / video-thumbnail / HTML-snippet references; buyer-checked | ✅ `c6a78bf8` |
| `POST /agent/v1/creative-performance/batch` | `config_creative_daily` / `performance_metrics` **only** | no `rtb_daily` fallback: creatives missing from precompute return `metric_source: "unavailable"` rather than a silent lane switch; `clicks_available: false` | ✅ `7f07eeb4` |
| `GET /agent/v1/daily-spend` | exists (`rtb_buyer_spend_daily`) | extend with the provenance envelope | ✅ `409b96ee` |
| `GET /agent/v1/data-quality` | new reconciliation service | compares canonical buyer spend vs summed creative allocation for a buyer+window; returns `allocation_status` + deltas | ✅ `409b96ee` |

Cross-cutting:

- A shared Pydantic **provenance envelope** (Section 4, decision 6) applied
  to every metrics response, implemented once in `api/schemas/`.
- A small **reconciliation service** (`services/agent_data_quality_service.py`)
  encoding the three-lane reality (D6). It does not fix the ETL gaps; it
  makes them visible and machine-readable so no client discovers an
  overcount by diffing unrelated endpoints.
- Statement timeouts (`pg_query_with_timeout`) on every new repository query,
  following `AgentStatsRepository`.
- Existing dashboard endpoints (`/creatives`, `/performance/metrics/batch`,
  `/analytics/spend-stats`) are left untouched — the MCP path never calls
  them.

### Phase 3 — MCP server MVP

New top-level package `mcp_server/` (added to `pyproject.toml` packages):

```
mcp_server/
  __init__.py
  server.py          # FastMCP app, Streamable HTTP, /mcp mount, /health
  client.py          # httpx AsyncClient → RTBCAT_API_BASE_URL, token pass-through
  tools/
    buyers.py        # rtbcat_list_buyers
    creatives.py     # rtbcat_search_creatives, rtbcat_get_creative
    assets.py        # rtbcat_get_creative_asset (MCP resource, fetched on demand)
    performance.py   # rtbcat_get_daily_spend, rtbcat_get_creative_performance
    quality.py       # rtbcat_check_data_quality
  ratelimit.py       # in-process per-token bucket (D8: nothing exists upstream)
requirements-mcp.txt # mcp + httpx pins (separate file: keep the API image lean;
                     # must be added to the pip-audit matrix in security.yml)
Dockerfile.mcp       # python:3.11-slim, non-root uid 10001, HEALTHCHECK /health
```

Tool design rules (from the incident findings):

- Search results return **compact evidence**, not raw rows: creative id +
  buyer, destination and resolved destination, format, preview reference,
  relative performance rank, metric provenance, freshness/missing-data
  warnings, pagination cursor.
- Large images/video/HTML are MCP **resources** fetched on demand — never
  embedded in every search result.
- Dollar figures are blocked or explicitly flagged whenever
  `allocation_status != "reconciled"`; ranking signals stay available.
- Errors from the API pass through with their status semantics (401/403 from
  the API surface as MCP auth errors, not as tool text).

Configuration (env, matching repo conventions): `CATSCAN_MCP_ENABLED`
(kill switch, `scheduler_guard`-style truthiness), `RTBCAT_API_BASE_URL`
(compose-internal `http://api:8000`), `CATSCAN_MCP_PORT`,
`CATSCAN_MCP_RATE_LIMIT_PER_MINUTE`.

### Phase 4 — Build and deploy (the six-place checklist) — CODE COMPLETE

Adding a third image touches every one of these; missing any breaks the
release path:

1. `deploy/hetzner/compose.yml` — `mcp` service: `image: ${MCP_IMAGE:?}`,
   `pull_policy: never`, `127.0.0.1:8010:8010`, `cap_drop: ALL`,
   `no-new-privileges`, healthcheck on `/health`, `depends_on: api:
   service_healthy`, same logging limits. No DB volumes, no secret mounts.
2. `.github/workflows/build-and-push-ghcr.yml` — third build step
   (`file: Dockerfile.mcp`, own GHA cache scope, digest output), MCP tests in
   the gating `test` job list, `MCP_IMAGE=…@sha256:…` line in the manifest
   writer, digest-validation loop entry.
3. `scripts/hetzner/deploy_app_release.sh` — parse/validate `MCP_IMAGE`,
   pull it, assert the `org.opencontainers.image.revision` label and uid
   10001, export it for compose, include it in the rendered-images
   cross-check.
4. `scripts/hetzner/verify_app_release.sh` — add `rtbcat-mcp` to the
   container loop, its image comparison, its PortBindings assertion, and its
   port in the loopback-only listener check.
5. `deploy/hetzner/release.env.example` + `docs/internal/DEPLOY_RUNBOOK.md`.
6. Host side (manual, documented in the runbook): scripts under
   `/opt/rtbcat/scripts/` are not a git checkout — updated deploy/verify
   scripts must be installed on the host before the first MCP release.

Edge (host nginx is currently hand-managed — bring this piece under version
control while we're here):

- New tracked generator `scripts/hetzner/apply_mcp_ingress.sh` (modeled on
  the existing temp-ingress script's vhost template) writing the
  `mcp.rtb.cat` vhost: TLS 1.2/1.3, certbot cert, proxy to
  `127.0.0.1:8010`, **explicit `proxy_read_timeout` (≥300s) and
  `proxy_buffering off`** — Streamable HTTP responses stream; the host's
  60-second default timeout has already caused one production incident on
  another route.
- DNS record via the existing `scripts/hetzner/update_production_dns.sh`
  flow.
- Rollout posture: deploy with `CATSCAN_MCP_ENABLED=false` first (container
  healthy, edge dark), then enable for a single pilot identity.

### Phase 5 — Hardening and rollout

- **Tests** (flat `tests/`, self-contained, per repo convention):
  - Buyer isolation: token scoped to buyer A must 403 on buyer B across
    every tool (the top acceptance criterion).
  - Scope enforcement: stats-only token cannot call creative tools.
  - Revocation: revoked token fails on the next call.
  - Contract tests: MCP tool output == Agent API response for the same
    inputs (run the MCP server against the FastAPI app in-process via the
    existing `SyncASGIClient` pattern).
  - Reconciliation fixtures: canonical vs allocated agree / disagree /
    partially missing.
  - Freshness and missing-source-date fixtures.
  - Pagination and rate-limit behavior.
  - Gate the release: add the new test files to the
    `build-and-push-ghcr.yml` test list (tests not on that list never gate
    a release).
- **Ops**: `/health` + latency/error/tool-usage/token-failure counters
  (Prometheus text format is enough), stale-precompute warning surfaced from
  `/precompute/health`, one line in `docs/internal/handover.md` per the
  operational-records rule.
- **Client config**: publish one MCP configuration snippet for approved
  clients in `docs/MCP_SERVER.md` (public), including token issuance and
  revocation steps.
- **OAuth decision gate**: pick build (FastMCP auth provider + our user
  store) vs integrate (external IdP) once the MVP is exercised. Until then
  the deviation from the OAuth acceptance criterion is documented, not
  hidden.

### Phase 6 — Product intelligence (deferred, separately gated)

Promotion-type/product-category/OCR/landing-page indexing persisted at
ingestion or cache-refresh time, exposed as `rtbcat_summarize_product_mix`
and `rtbcat_search_promotions`. Two hard constraints established now:

- Any full refresh **must be enqueued** through the durable job queue.
  Note: `enqueue_precompute_job()` currently dispatches one hardcoded
  refresh chain — a product-index job needs a job-type branch in the worker
  (or a sibling queue table), which is part of this phase's design work,
  not a shortcut around it.
- A product-mix response must separate the *message in the creative* (e.g. a
  welcome-credit banner) from the *products stocked at the destination*
  (e.g. cooling fans), with confidence and evidence source per field.

## 6. Open-sourcing requirements

The MCP server is developed in the open, in this repo, from day one:

- **License**: inherits repo MIT; no new license file needed.
- **No private references**: no private schema names, no customer
  identifiers, no host IPs, no real buyer IDs in code, tests, fixtures, or
  docs. Test fixtures use synthetic buyers/creatives only.
- **CI coverage**: new Python lands in existing gitleaks scope
  automatically; add `requirements-mcp.txt` to the `pip-audit` matrix in
  `security.yml`; the redaction-boundary job covers all tracked files; the
  new image build lives in the same public workflow.
- **Release preflight**: `oss-release-preflight.yml` already checks
  forbidden files and required root files — no change expected, verify once
  the package lands.
- **Docs**: public `docs/MCP_SERVER.md` (usage, tools, auth, limits) once
  Phase 3 ships; this plan stays as the design record.
- **Secrets**: the MCP container consumes no secret files; identity material
  is only ever the caller's own token. `.mcp.json` (local client config) is
  already gitignored.

## 7. Acceptance criteria

Carried from the internal baseline, restated public-safe:

1. A clean agent environment answers a "what products do buyers X and Y
   promote" question through one MCP connection.
2. After initial authorization, no gcloud command, browser login, copied
   global secret, or human Google account is needed.
3. An identity cannot access an unassigned buyer (test-enforced).
4. Every request appears in `audit_log` with identity, buyer, tool, and
   timestamp.
5. Credential rotation/revocation requires no workstation configuration
   changes.
6. Every metrics response reports scope, coverage, freshness, missing data,
   and canonical-vs-allocated status; dollar figures are blocked or flagged
   when allocation does not reconcile.
7. Common searches complete in ≈10 seconds.
8. Batch analytics never query `rtb_daily` (test-enforced at the repository
   layer, and `scripts/catscan_mcp_db_smoke.py` remains the DB contract).
9. The production path depends only on the Hetzner deployment.

## 8. Risks and open questions

| # | Risk / question | Mitigation |
|---|---|---|
| R1 | Per-call psycopg connection churn (D9) makes a hydrating search open a dozen+ connections; the 10s target is reachable but this bites first under concurrency | Keep MVP tools coarse (one API call each); add connection pooling to `postgres_database.py` as an independent, high-value fix — it benefits the whole platform |
| R2 | `mark_token_used` writes on every authenticated read — the Agent API is not literally read-only at the DB level | Acceptable on the writable production host; batch/duty-cycle the update if it ever shows in write metrics |
| R3 | Spend reconciliation is structural (three lanes, three grains), not a bug | Phase 2 exposes it honestly; actually closing the gap (e.g. the app-name ETL lane) is platform work outside this project |
| R4 | Widening `get_allowed_buyer_ids` (D2) changes behavior for existing multi-seat users | Audit all call sites first; feature-flag if any dashboard path depends on the truncation |
| R5 | OAuth build-vs-integrate could stall rollout | Decoupled: MVP ships on scoped tokens; OAuth is a gated follow-up with its own decision |
| R6 | Host nginx is unmanaged state | The tracked `apply_mcp_ingress.sh` generator starts reversing that for the new vhost |
| R7 | Streamable HTTP through nginx buffering/timeouts | Explicit `proxy_buffering off` + generous `proxy_read_timeout` in the vhost template from day one |

## 9. Sequencing and rough sizing

Phases 1→4 are strictly ordered; 5 overlaps 3–4; 6 is independent later work.

| Phase | Size | Depends on |
|---|---|---|
| 0 Hygiene | done / hours | — |
| 1 Authorization | S–M (2–4 days) | — |
| 2 Contracts | M–L (1–2 weeks) | 1 |
| 3 MCP MVP | M (≈1 week) | 2 |
| 4 Deploy | M (3–5 days incl. host work + DNS/TLS) | 3 |
| 5 Hardening/rollout | M (≈1 week, overlaps) | 3–4 |
| 6 Product intelligence | L (separate project) | 3 |

PRs target `main` (the integration branch). Each phase is independently
shippable and leaves production no worse if paused after it.
