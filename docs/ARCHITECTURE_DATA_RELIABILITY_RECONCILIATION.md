# Architecture: Data Reliability and Pipeline Reconciliation

Date: 2026-02-08  
Context inputs: `docs/ai_logs/ai_log_2026-02-07.md` entries at `2026-02-08 01:30` and `2026-02-08 02:00`

## 1) Problem to solve

Current failures are structural, not UI-only:

1. Runtime drift and deploy fragility caused outages (service/process mismatch, hidden config drift).
2. Metrics pipeline is split into disconnected sources:
   - CSV path (`rtb_daily`) feeds config-level tables.
   - API path (`rtb_geo_daily`) feeds home-level tables.
3. Missing dimensions in CSV (country/publisher) become empty-string rows and are filtered out downstream, yielding empty config tabs.
4. UI receives "0 rows" without quality context, so users cannot distinguish "no traffic" from "data unavailable".

## 2) Target architecture

Use a **three-layer data architecture** with explicit data contracts:

1. **Source layer** (raw, immutable, provenance-preserving)
2. **Canonical layer** (reconciled facts, one schema for analytics)
3. **Serving layer** (precompute/materialized tables for UI)

All UI endpoints must read from serving tables that are derived from canonical tables only.

## 3) Layer design

### 3.1 Source layer (keep both pipelines)

Keep existing raw source tables but standardize ingestion metadata:

- `rtb_daily` (CSV)
- `rtb_bidstream` (CSV)
- `rtb_bid_filtering` (CSV)
- `rtb_geo_daily` (API)
- `rtb_publisher_daily` (API, when available)

Add metadata tables:

- `ingestion_runs`
  - `run_id`, `source_type` (`csv`,`api`), `buyer_id`, `started_at`, `finished_at`, `status`, `row_count`, `error_summary`
- `source_coverage_daily`
  - `metric_date`, `buyer_id`, `source_type`, `has_country`, `has_publisher`, `has_billing_id`, `coverage_score`

Purpose: quantify missing dimensions as first-class signals.

### 3.2 Canonical layer (new)

Create canonical fact tables with provenance and quality:

- `fact_delivery_daily`
  - Grain: `metric_date, buyer_id, billing_id, creative_id, country, publisher_id, source_priority`
  - Metrics: `reached_queries, impressions, clicks, spend_micros, bids, auctions_won`
  - Provenance: `source_used` (`csv`,`api`,`blended`), `imputed_fields` (jsonb), `confidence`
  - Quality flags: `country_quality`, `publisher_quality`, `billing_quality`

- `fact_dimension_gaps_daily`
  - Grain: `metric_date, buyer_id`
  - Missingness % by field (`country_missing_pct`, `publisher_missing_pct`, etc.)
  - `availability_state` (`healthy`,`degraded`,`unavailable`)

Reconciliation rules:

1. Prefer CSV for billing/config granularity when dimension exists.
2. Supplement missing dimensions from API aggregates only when join-safe:
   - Safe: buyer/day geo totals, buyer/day publisher totals.
   - Unsafe: inventing billing_id-level geo split from buyer-level API.
3. Never fabricate billing_id joins. If not available, publish degraded quality with reason.

### 3.3 Serving layer

Serving tables derive from canonical facts:

- `home_*_daily` from canonical buyer/day aggregates.
- `config_*_daily` from canonical config/billing aggregates.

For config geo/publisher views:

1. Primary: canonical rows with real billing_id + dimension.
2. Fallback: buyer-level geo/publisher aggregates tagged `scope=buyer_fallback`.
3. Response includes `data_scope` and `quality_state`; UI shows warning banner.

## 4) API contract changes

Every analytics response must include status metadata:

- `data_state`: `healthy | degraded | unavailable`
- `data_sources`: list (`csv`,`api`,`blended`)
- `coverage`: dimension completeness object
- `fallback_applied`: boolean
- `fallback_reason`: enum string
- `last_fresh_at`: timestamp

This avoids "silent empty" responses.

## 5) UI behavior contract

For any table/card:

1. If `unavailable`: show explicit "Data unavailable" state with reason and last successful date.
2. If `degraded`: show data plus warning badge and tooltip describing scope limits.
3. If fallback scope is buyer-level for config detail, label rows as `Estimated (buyer-level)`.
4. Keep one-click refresh/recompute actions and show freshness age.

## 6) Orchestration and reliability

Use a deterministic DAG:

1. Ingest (CSV/API) -> write source tables + `ingestion_runs`
2. Coverage profiler -> `source_coverage_daily`
3. Reconciliation job -> canonical facts
4. Precompute job -> serving tables
5. Validation job -> quality/freshness assertions

Job invariants:

- No precompute run without completed reconciliation for target window.
- If validation fails, mark state degraded/unavailable and keep last known-good data.

## 7) Validation and guardrails

Add hard checks:

1. Dimension presence checks by buyer/day before precompute.
2. Join integrity checks (`billing_id` never inferred from seat_id).
3. Freshness SLA checks (e.g. source <= 24h, serving <= 6h).
4. Null/empty rate thresholds for critical dimensions.

Expose via:

- `GET /system/data-health`
- `GET /analytics/...` embedded `data_state` metadata

## 8) Ops architecture constraints

1. Postgres-only runtime remains mandatory (SQLite fully decommissioned).
2. Secrets manager remains source of truth with startup validation (`SECRETS_HEALTH_STRICT`).
3. Version must be SHA-based everywhere (API + dashboard) for release traceability.
4. Scheduler credentials/token health must be monitored (Gmail token status, scheduler auth failures).

## 9) Implementation phases

### Phase A: Observability first
- Add `ingestion_runs`, `source_coverage_daily`, and `/system/data-health`.
- Add `data_state` metadata to existing analytics responses.

Phase A task list (implementation order):

1. Create migration for reliability metadata tables (`ingestion_runs`, `source_coverage_daily`).
2. Build `DataHealthService` computing:
   - source freshness (`rtb_daily`, `rtb_geo_daily`)
   - serving freshness (`home_geo_daily`, `config_geo_daily`, `config_publisher_daily`)
   - recent dimension missingness from `rtb_daily`
   - ingestion run summary.
3. Expose `GET /system/data-health?days=&buyer_id=` (non-sensitive, auth-gated).
4. Extend home analytics payloads with:
   - `data_state`
   - `fallback_applied`
   - `fallback_reason`
   - `coverage`.
5. Update frontend API typings for new metadata fields.

### Phase B: Canonical reconciliation
- Build `fact_delivery_daily` and `fact_dimension_gaps_daily`.
- Refactor precompute jobs to consume canonical layer only.

### Phase C: UI reconciliation UX
- Add degraded/unavailable rendering paths in config geo/publisher/creative drilldowns.
- Add quality tooltips and fallback-scope labels.

### Phase D: strictness and enforcement
- Enforce validation gates in scheduler pipeline.
- Alert on stale/unavailable states and ingestion failures.

## 10) Decision outcomes for current incident class

With this architecture:

1. Empty config geo/publisher tables become explicit `degraded` with reason (missing CSV dimensions), not silent zeroes.
2. Home/config discrepancies are expected and labeled by scope/provenance.
3. Pipeline failures surface quickly via data-health and run metadata.
4. Runtime drift is reduced by strict startup checks, SHA versioning, and Postgres-only invariants.
