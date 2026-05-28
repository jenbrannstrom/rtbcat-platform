# Agent Interface Architecture

Cat-Scan should treat agents as first-class consumers of the compiled daily data
product, not as dashboard automation. The dashboard remains the human
visualization layer. Agents should use stable read contracts and audited action
contracts.

## Core Principle

Do not make prompts, skills, or agent instructions the security boundary.

Use:

- `agent_read` SQL views for high-volume analytical reads
- `/api/agent/v1` for outside HTTP agents that need precomputed report data
- authenticated APIs for refreshes, scans, and mutations
- `SKILL.md`-style instructions for workflow guidance only

## Data Flow

```text
Gmail CSV reports / GCS report URLs
        |
        v
Import, normalization, lineage, precompute
        |
        v
Postgres compiled data product
        |
        +--> Dashboard UI
        +--> agent_read SQL views
        +--> audited action APIs
```

## Read Contract

Agents that need direct SQL should connect with a Postgres role that has:

- `CONNECT` on the database
- `USAGE` on schema `agent_read`
- `SELECT` on `agent_read` views
- no default access to raw `public` tables

Buyer isolation for direct SQL is managed through
`agent_private.buyer_role_grants`, keyed by the database login role. The views
filter rows with that mapping.

Initial views:

| View | Purpose |
|------|---------|
| `agent_read.accessible_buyers` | Buyer seats visible to the current DB role |
| `agent_read.creative_language_country_signals` | Creative language, country, latest geo scan, and performance signals |
| `agent_read.creative_scan_queue` | Creatives needing language/geo scan, retry, refresh, or review |
| `agent_read.buyer_daily_report_summary` | Buyer-level report completeness and mismatch counts |
| `agent_read.creative_performance_issues` | Creative inefficiency candidates for reports |

Raw-table access is reserved for trusted internal debugging or one-off data
engineering work.

## HTTP Agent Contract

Outside agents that cannot use direct Postgres should use the versioned Agent
API documented in [AGENT_API.md](AGENT_API.md).

| Need | Contract |
|------|----------|
| Validate token | `GET /api/agent/v1/me` |
| Pull email-ready stats | `GET /api/agent/v1/stats-summary` |
| Create/revoke tokens | `POST/DELETE /api/agent/v1/tokens` as sudo |

Agent bearer tokens are stored hashed, are revocable, carry scopes, and remain
bound to normal Cat-Scan users and buyer-seat grants.

## Action Contract

Agents should call APIs for anything that changes state or triggers work.

| Action | Contract |
|--------|----------|
| Read mismatch rows | `GET /api/creatives/language-flag-coverage` |
| Queue language and geo scans | `POST /api/creatives/language-flag-coverage/refresh` |
| Refresh creative live cache | `POST /api/creatives/cache/refresh/scheduled` with scheduler secret |
| Refresh precomputed serving tables | `POST /api/precompute/refresh/scheduled` with scheduler secret |
| Edit pretargeting | existing pretargeting mutation APIs, seat-admin/sudo only |

Mutation APIs must remain authenticated, buyer-scoped where possible, validated,
and audited.

## Secrets And Identity

Use Google Secret Manager for production credentials.

Recommended identity model:

- per-buyer app user for client-specific report workflows
- per-buyer DB role for direct SQL report workflows
- separate internal all-buyer role only for trusted internal report generation
- separate scheduler secrets for refresh jobs
- no client access to raw-table credentials

Recommended secret names:

- `catscan-creative-audit-db-password-BUYER_ID`
- `catscan-creative-audit-app-password-BUYER_ID`
- `catscan-creative-audit-db-password-internal`
- existing `catscan-creative-cache-refresh-secret`
- existing `catscan-precompute-refresh-secret`

Grant each runtime service account `roles/secretmanager.secretAccessor` only on
the secrets it needs.

## What Skills Are For

A `SKILL.md` can tell an agent:

- which views to query
- which filters to apply
- when to refresh data
- how to structure a client report
- which actions are forbidden

A skill must not be relied on for:

- buyer isolation
- permission checks
- mutation validation
- audit logging
- secret handling

Those belong in database grants, views, APIs, and IAM.

## Versioning

Treat `agent_read` as a public contract:

- add columns without breaking existing columns
- add new views instead of changing existing semantics
- document deprecations before removing fields
- keep report-producing agents pinned to a view/API contract version when needed

If the agent interface grows materially, add `agent_read_v2` views or explicit
versioned API paths instead of changing report-critical behavior in place.
