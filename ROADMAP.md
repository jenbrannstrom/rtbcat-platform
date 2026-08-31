# Cat-Scan Roadmap

Last updated: August 31, 2026

This roadmap covers unfinished product and platform work. Completed migrations,
incident timelines, and release receipts belong in the changelog or internal
runbooks, not here.

## Delivered foundations

- Authorized Buyers ingestion through Gmail and manual CSV upload for the five
  core report types
- creative, seat, endpoint, and pretargeting synchronization and management
- QPS, waste, campaign-clustering, and creative-performance analysis
- multi-user authentication, roles, audit logging, and buyer-seat isolation
- conversion ingestion, attribution-join storage, AppsFlyer readiness
  diagnostics, and click-macro auditing
- optional AI-assisted language detection and geo-linguistic mismatch analysis
- Hetzner application and PostgreSQL production migration, backup and recovery
  tooling, scheduled precompute work, and operational health checks
- buyer-scoped Agent API, agent-token administration, and the deployed
  read-only MCP service with bounded tools and contract tests

The MCP service is live at `https://mcp.rtb.cat/mcp` for scoped pilot tokens.
It is deployed as a digest-pinned, non-root container behind TLS ingress, with
the origin bound to loopback and a runtime kill switch. Broader rollout still
depends on the abuse-prevention and capacity controls below.

## Active priorities

### 1. Harden and expand the read-only MCP service

Outcome: approved customers can query their own precomputed RTBcat evidence
without exposing the application, database, other buyers, or unbounded
infrastructure capacity.

Current production baseline:

- the digest-pinned MCP image, Compose, release manifest, deployment,
  rollback, and verification wiring described in
  [the MCP delivery plan](docs/MCP_READONLY_SERVER_PLAN.md)
  are complete and exercised by the normal GitHub CI release path
- `mcp.rtb.cat` has DNS, TLS, tracked Nginx ingress, and a loopback-only origin
- the kill switch is enabled and a scoped pilot tool call has been verified
  end to end; access has not been opened as a broad customer service

DoS and abuse-prevention launch gates:

- put the MCP hostname behind a layer-7 proxy or WAF and prevent clients from
  bypassing it to reach the Hetzner origin directly
- enforce edge limits for requests, connections, request-body size, header/body
  timeouts, and slow clients before traffic reaches the MCP process
- rate-limit initialization, tool discovery, health traffic, missing or invalid
  credentials, and tool calls; the current per-token tool limit alone is not an
  edge defense
- add global, per-IP, and per-token concurrency ceilings so a token-bucket burst
  cannot start dozens of expensive reads at once
- validate credentials before retaining long-lived limiter state; bound and
  expire limiter entries so rotating fake tokens cannot grow process memory
  without limit
- use a shared limiter when more than one process or replica is deployed so
  restarts and horizontal scaling do not multiply the effective allowance
- add PostgreSQL connection pooling and retain hard statement timeouts on every
  Agent API query
- record per-customer request counts, response bytes, latency, rejections, and
  database time; alert on authentication failures, rate limits, saturation,
  bandwidth, and database-connection pressure
- provide a fast operational block path for one credential, one source, or the
  entire MCP hostname, and rehearse the kill switch before public rollout

Rollout exit criteria:

- load and abuse tests prove that rejected traffic does not consume material
  API or database capacity
- one customer cannot exhaust global capacity or materially degrade the main
  Cat-Scan application
- quotas, revocation, dashboards, alerts, and incident ownership are documented
- the pilot remains within agreed latency, error-rate, and infrastructure-cost
  thresholds before access expands

### 2. Make optimization conversion-driven

Outcome: recommendations use conversion and value evidence instead of relying
mainly on bids, spend, win rate, and other proxy signals.

Next steps:

- validate AppsFlyer end to end with real buyer data
- finish exact and fallback attribution reporting in production workflows
- feed conversion and value evidence into optimizer scoring
- measure attribution coverage and confidence for every buyer
- keep hard automation behind explicit coverage, confidence, and rollback gates

AppsFlyer remains the first-class attribution path. Other connector types may
exist in code or taxonomy, but they should not be presented as equally mature
until they have equivalent production evidence.

### 3. Productize troubleshooting diagnostics

Outcome: operators can verify daily CSV data and investigate transient
exchange-side filtering, timeout, no-bid, and auction-loss signals without
presenting the Troubleshooting API as a reporting replacement.

Next steps:

- build a narrow collection flow for transient filter-set queries
- retain only dimensions and metrics that explain exchange-observed behavior or
  validate imported reports
- surface results as operator diagnostics and parity checks
- continue using daily Authorized Buyers reports for historical reporting and
  conversion sources for value analysis

### 4. Improve onboarding and day-two operations

Outcome: a self-hosted operator can install, verify, monitor, upgrade, and
recover Cat-Scan without needing undocumented platform knowledge.

Next steps:

- make installation and first-run verification linear
- improve actionable failure messages and secret-health checks
- simplify conversion and agent-token setup
- document backup restoration, upgrades, rollback, capacity signals, and
  scheduler ownership in one operator path

### 5. Mature language analysis as an optional subsystem

Outcome: language and geo-linguistic analysis is useful when explicitly enabled
and never becomes a hidden requirement for the core product.

Next steps:

- keep provider selection coherent across the UI, API, deployment, and docs
- evaluate provider quality, cost, latency, and failure behavior in real
  workflows
- preserve manual overrides and operator review
- keep external AI providers disabled until their credentials and policy are
  explicitly configured

### 6. Build evidence before expanding product claims

Outcome: product claims reflect measured customer outcomes rather than inferred
uplift.

Next steps:

- collect buyer-approved before-and-after evidence
- measure improvements only where attribution and baselines are defensible
- identify which buyer profiles benefit most from operator-side controls
- keep public claims narrow until results are repeatable

## Cross-cutting guardrails

- Every external read and write remains authenticated, buyer-scoped, audited,
  revocable, and least-privileged.
- Agent and MCP analytics read bounded, precomputed contracts rather than raw
  event tables.
- Read-only interfaces do not silently gain refreshes, mutations, or paid model
  calls.
- Optimizer automation requires evidence, confidence thresholds, a reversible
  action path, and an accountable operator.
- Optional integrations remain optional in installation, runtime, and public
  product descriptions.

## Open decisions

- choose the MCP edge/WAF and origin-locking design
- decide whether customer quotas are contractual, usage-based, or both
- decide whether MCP authentication remains scoped bearer tokens or adds an
  OAuth authorization-code and PKCE flow after the pilot
- determine which fallback attribution methods are reliable enough to influence
  recommendations
- determine which language-analysis providers are reliable enough for supported
  production use

## Definition of done

A roadmap item moves to delivered only when:

- the production code path exists
- an operator can use and recover it without guesswork
- tests cover its security boundary and primary failure modes
- monitoring and rollback are in place where the feature can affect production
- documentation matches deployed behavior
- public claims are no stronger than the available evidence
