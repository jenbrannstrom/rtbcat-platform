# Data Pipeline Recovery Plan (App-Wide)

**Date:** 2026-02-11  
**Owner:** Engineering (Codex + Claude execution)  
**Scope:** All buyer seats, all user-facing analytics paths  
**Priority:** P0 (core product integrity)

---

## 1) Problem Statement

The app is a data-analysis product, but core analytical integrity is currently compromised by:

- Incomplete ingestion coverage across buyers/report types
- Missing critical source feed(s) (notably endpoint observed feed)
- Partial/uneven precompute coverage across buyers/tables
- Weak observability (missing run logs/coverage assertions)
- UI/API behavior that can be fast but semantically misleading when feeds are missing

This is not a performance-only issue. It is a **data contract and control-plane issue**.

---

## 2) Non-Negotiable End-State (Definition of Done)

The recovery is complete only when all are true:

1. Every required report type is ingested for every active buyer seat on every scheduled day.
2. Every required serving/precompute table is fresh and populated per buyer for windows 7/14/30.
3. Critical feed availability is explicit and monitored (`endpoint delivery` included).
4. Every ingestion/precompute run is logged in `ingestion_runs` with buyer, report type, status, row counts, timings, error.
5. User-facing APIs never silently substitute misleading proxies for missing critical feeds.
6. App has automated verification that blocks deploys when data contracts fail.

---

## 3) Target Architecture (End-State)

```text
                  +-----------------------------+
                  | Gmail + GCS Report Sources |
                  +-------------+---------------+
                                |
                                v
                 +------------------------------+
                 | Import Orchestrator Worker   |
                 | (detached, buyer-aware)      |
                 +------+-----------------------+
                        |
                        | writes ingestion_runs (required)
                        v
    +---------------------------------------------------------+
    | Raw/Staging Facts (Postgres)                            |
    | - rtb_daily                                              |
    | - rtb_bidstream / rtb_bid_filtering / quality-derived   |
    | - endpoint observed feed (rtb_endpoints_current source) |
    +--------------------+------------------------------------+
                         |
                         | deterministic precompute jobs
                         v
    +---------------------------------------------------------+
    | Serving / Precompute Layer (buyer + window scoped)      |
    | - home_seat_daily / home_config_daily / home_geo_daily  |
    | - config_creative_daily / config_size_daily / ...       |
    | - serve_*_window tables for 7/14/30                     |
    +--------------------+------------------------------------+
                         |
                         | read-only user APIs
                         v
    +---------------------------------------------------------+
    | API Layer                                                |
    | - /analytics/home/*                                      |
    | - /analytics/rtb-funnel/*                                |
    | returns: data_state, last_refreshed_at, source metadata |
    +--------------------+------------------------------------+
                         |
                         v
                  +------------------+
                  | Dashboard UI     |
                  | explicit states: |
                  | ready/refreshing |
                  | missing_feed     |
                  +------------------+
```

---

## 4) Canonical Data Contracts

## 4.1 Buyer-Coverage Contract
For each active buyer and each day D in window:
- Required report groups present: `pipeline`, `quality`, `geo`, `bid-filtering`, `bids-in-auction` (as applicable)
- Required raw facts populated
- Required precompute tables populated

## 4.2 Critical Feed Contract
- Endpoint observed feed is mandatory for endpoint-efficiency observed metrics.
- If missing, API must return explicit `endpoint_delivery_state=missing` and set observed-only fields to `null`.

## 4.3 Serving Contract
- User APIs read serving/precompute only.
- Windows fixed to 7/14/30 where possible.
- Responses include:
  - `data_state`
  - `last_refreshed_at`
  - `freshness_window`
  - `missing_feed_reason` (if applicable)

---

## 5) Execution Plan (Phases)

## Phase 0 — Incident Baseline and Freeze (P0)
Goal: stop further divergence while capturing baseline truth.

Tasks:
- Freeze non-essential feature changes touching ingestion/precompute/analytics.
- Generate app-wide buyer x table coverage matrix (last 30 days).
- Capture baseline for all critical endpoints and table freshness.

Deliverables:
- `docs/recovery/baseline_coverage_matrix_<date>.md`
- `docs/recovery/baseline_endpoint_snapshot_<date>.json`

Exit criteria:
- One baseline artifact approved by owner.

---

## Phase 1 — Ingestion Reliability + Observability Backbone (P0)
Goal: make runs visible and auditable.

Tasks:
- Enforce write to `ingestion_runs` for every import run and each buyer/report-type substep.
- Required fields: `run_id`, `job_id`, `buyer_id`, `report_type`, `source`, `started_at`, `finished_at`, `status`, `rows`, `error_code`, `error_text`.
- Add idempotent upsert/insert policy to prevent duplicate ambiguity.
- Add `/system/data-health` extension to expose ingestion lag by buyer/report type.

Tests:
- Trigger test import: verify one parent run and sub-runs per report type per buyer.
- Intentionally fail one source: verify `failed` row with error populated.

Exit criteria:
- 100% of imports in last 24h have corresponding `ingestion_runs` rows.

---

## Phase 2 — Source Feed Completeness (P0)
Goal: ensure all required feeds exist for all buyers.

Tasks:
- Validate Gmail/GCS retrieval coverage by buyer and report type.
- Resolve endpoint observed feed population path to `rtb_endpoints_current` (or replacement canonical table).
- Add mandatory feed checker job (hourly) that records missing feeds per buyer.

Tests:
- For each active buyer, assert non-zero row existence in expected raw tables for last N days.
- Assert `rtb_endpoints_current` non-zero global and per-bidder where endpoints configured.

Exit criteria:
- No active buyer failing mandatory feed checks for 2 consecutive scheduler cycles.

---

## Phase 3 — Universal Precompute Completion (P0)
Goal: make precompute complete and symmetric across buyers.

Tasks:
- Build/finish serving windows (`7/14/30`) for all user-facing dimensions:
  - seat
  - config
  - geo
  - publisher
  - size
  - endpoint-efficiency support facts
- Ensure buyer-scoped refresh runs after import completion and scheduled cadence.
- Add per-table freshness records and row-count minima.

Tests:
- Buyer x table matrix for 7/14/30 must pass all required tables.
- Compare sampled serving values vs raw truth queries (tolerance 0 for counts/sums).

Exit criteria:
- 100% required serving tables fresh for all active buyers over 3 consecutive runs.

---

## Phase 4 — API Semantics Hardening (P0)
Goal: eliminate misleading outputs.

Tasks:
- Endpoint-efficiency: keep feed-observed metrics separate from funnel proxies.
- Never present proxy metric as observed endpoint metric.
- Standardize nullability and `missing_feed` states.
- All analytics endpoints include explicit source and freshness metadata.

Tests:
- Contract tests for each endpoint:
  - when feed present => observed fields populated
  - when feed missing => observed fields null + `missing_feed` reason
- Snapshot tests for response schema stability.

Exit criteria:
- All endpoint contract tests pass in CI.

---

## Phase 5 — UI Integrity and Operational UX (P1)
Goal: users clearly see data truth state.

Tasks:
- Keep fast shell + seat-gated query behavior.
- Show explicit banners by section:
  - `ready`
  - `refreshing`
  - `missing_feed`
  - `no_rows_for_seat_window`
- Remove ambiguous “no data” where specific cause is known.

Tests:
- Browser E2E tests for each state with fixtures.
- Visual checks: each banner appears only in matching backend state.

Exit criteria:
- No ambiguous empty state for top-level panels.

---

## Phase 6 — Guardrails and Release Gates (P0)
Goal: prevent recurrence.

Tasks:
- Add CI gate failing if any non-admin analytics endpoint introduces raw multi-day runtime aggregate path.
- Add daily automated data quality report (buyer x feed x table coverage).
- Add alerting:
  - missing endpoint feed
  - stale precompute
  - ingestion failure streak
  - buyer coverage regression

Tests:
- Simulated failure injection verifies alerts and blocked deploy.

Exit criteria:
- Guardrail suite green for 7 consecutive days.

---

## 6) Verification Checklist (100% Completion)

All must be checked:

- [ ] `ingestion_runs` populated for every import and substep
- [ ] `rtb_endpoints_current` populated and fresh
- [ ] buyer x required report-type coverage = 100%
- [ ] buyer x required precompute-table coverage = 100%
- [ ] `/analytics/home/*` and `/analytics/rtb-funnel/*` contract tests pass
- [ ] UI state tests pass (`ready/refreshing/missing_feed/no_rows`)
- [ ] CI gate for forbidden runtime aggregates active
- [ ] Daily quality report generated and archived
- [ ] Alerting wired and tested
- [ ] 7-day stability run completed without critical regression

---

## 7) SQL/Test Pack (must run every phase close)

## 7.1 Buyer coverage matrix (template)
```sql
-- Example template: extend per table/report type
SELECT buyer_account_id, COUNT(*) AS rows, MIN(metric_date) AS min_date, MAX(metric_date) AS max_date
FROM home_config_daily
GROUP BY buyer_account_id
ORDER BY buyer_account_id;
```

## 7.2 Endpoint feed existence
```sql
SELECT bidder_id, COUNT(*) AS rows, MAX(observed_at) AS last_observed
FROM rtb_endpoints_current
GROUP BY bidder_id
ORDER BY rows DESC;
```

## 7.3 Ingestion observability completeness
```sql
SELECT DATE(started_at) d, buyer_id, report_type, status, COUNT(*) runs
FROM ingestion_runs
WHERE started_at >= NOW() - INTERVAL '7 days'
GROUP BY 1,2,3,4
ORDER BY 1 DESC, 2, 3;
```

## 7.4 Contract check for missing feed semantics
- endpoint-efficiency observed metrics must be null when endpoint feed rows = 0
- endpoint-efficiency must include explicit `endpoint_delivery_state=missing`

---

## 8) Promptable Execution Units (for Claude/Codex)

Each phase should be executed with strict boundaries:

- **Prompt P0:** baseline generation only, no code changes
- **Prompt P1:** ingestion_runs instrumentation + tests only
- **Prompt P2:** source feed completeness + endpoint feed population only
- **Prompt P3:** precompute completion + buyer coverage tests only
- **Prompt P4:** API contract hardening + contract tests only
- **Prompt P5:** UI state clarity + E2E tests only
- **Prompt P6:** guardrails/alerts + failure injection tests only

Rule: each prompt must end with evidence artifacts and explicit pass/fail against exit criteria.

---

## 9) Immediate Next 48h Actions

1. Implement Phase 1 (`ingestion_runs` mandatory writes) and ship.
2. Implement Phase 2 feed checker and restore/verify endpoint observed feed population.
3. Run buyer x table matrix and publish first daily quality report.
4. Gate endpoint-efficiency semantics to never mix proxy as observed.

---

## 10) Ownership Cadence

- Daily 15-min data reliability standup until Phase 4 complete.
- Single owner for “data contract signoff” per release.
- No new analytics feature work merged unless Phase gate for current stage is green.

