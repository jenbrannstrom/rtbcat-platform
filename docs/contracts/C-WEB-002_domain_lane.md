# C-WEB-002: Domain Lane Isolation & Cardinality Control

**Status:** Active (feature-flagged)
**Applies to:** `web_domain_daily` table and domain lane pipeline

## Rules

1. **Isolation:** Domain analytics come only from the optional domain lane — no mandatory/core report includes domain-level data by default.
2. **No mandatory domain reports:** No existing report endpoint returns domain data unless explicitly opted in.
3. **Top-N + `__OTHER__` aggregation:** The `rollup_domains()` function controls cardinality by keeping only the top N domains per (metric_date, buyer_account_id, billing_id) group, aggregating the remainder into a single `__OTHER__` row. Default N = 200 (configurable via `CATSCAN_DOMAIN_TOP_N`).
4. **Buyer-level disable (default: disabled):** The domain lane is disabled per buyer by default. Only buyers listed in `CATSCAN_WEB_LANE_BUYERS` can import domain data.
5. **Buyer-level allowlist:** `CATSCAN_WEB_LANE_BUYERS` is a comma-separated list of buyer IDs. If unset while the global flag is enabled, all buyers are eligible.

## Feature Flags

| Env Var | Default | Purpose |
|---------|---------|---------|
| `CATSCAN_WEB_LANE_ENABLED` | unset (disabled) | Global kill switch |
| `CATSCAN_WEB_LANE_BUYERS` | unset | Comma-separated buyer allowlist |
| `CATSCAN_DOMAIN_TOP_N` | `200` | Max distinct domains per group |

## Contract Check

`check_web_002()` validates that distinct domains per (metric_date, buyer_account_id, billing_id) group does not exceed N+1 (top N + `__OTHER__`). SKIP if global flag is disabled.

## Enforcement

- **Importer:** `import_to_web_domain_daily()` rejects imports for non-allowlisted buyers
- **Rollup:** `rollup_domains()` enforces top-N before DB insert
- **Contract check:** `check_web_002()` validates the invariant post-import
