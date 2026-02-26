# Claude Spec: Creative Modal Performance Summary (Clicks + CPM/CPC/CTR) Full Fix

```text
Implement a proper, source-correct fix for Creative Preview Modal performance metrics so clicks/CTR/CPC are accurate (not fake zeros) while preserving seat scoping and data provenance.

This is NOT a cosmetic "show N/A" hotfix. Do the full backend+frontend handling properly.

Problem (confirmed)
- Creative preview modal can show:
  - `Clicks: 0`
  - non-zero `CPM` (e.g. `$0.44`)
- Current behavior is caused by the performance summary source path using `pretarg_creative_daily`, which has no clicks column:
  - `storage/postgres_store.py::get_creative_performance_summary(...)`
  - hardcodes `total_clicks = 0`, `avg_cpc_micros = None`, `ctr_percent = None`
- CPM is still computed from spend/impressions, so the UI can show CPM alongside fake zero clicks.

Important context
- We DO have click data in imported CSV-derived tables (e.g. `rtb_daily`).
- There is already repository code that reads clicks from `rtb_daily`:
  - `storage/postgres_repositories/creative_performance_repo.py`
- The current modal/batch summary path is using the wrong aggregation source for click-capable summaries.

Goal
Replace the creative performance summary path used by the Preview Modal (single + batch) with a click-capable, buyer-scoped aggregation source, and expose data availability/provenance explicitly so the UI never shows misleading zeros due to source limitations.

Scope (must cover)
1. Backend summary source (single creative and batch)
2. Buyer/seat scoping correctness
3. Response schema/data provenance
4. Preview Modal rendering semantics
5. Tests + validation

Non-goals (for this pass)
- Rebuilding unrelated campaign pages unless they use the same broken summary path
- Reimporting data (unless you prove raw click data is actually missing)

Current code paths (confirmed)
- UI:
  - `dashboard/src/components/preview-modal/PreviewModal.tsx`
- Batch endpoint (used by creatives page and modal prefetched summaries):
  - `api/routers/performance.py::get_batch_performance`
- Single creative summary endpoint:
  - `api/routers/performance.py::get_creative_performance`
- Broken source path:
  - `storage/postgres_store.py::get_creative_performance_summary`

Architecture requirements (proper fix)

1) Use a click-capable source for creative summaries
- Primary source should be `rtb_daily` (or another click-capable table if better justified)
- Aggregate at least:
  - impressions
  - clicks
  - spend_micros
  - reached_queries (if available and useful)
  - days_with_data
  - min/max metric_date
- Derive:
  - CPM
  - CPC (only when clicks > 0)
  - CTR (only when impressions > 0)

2) Enforce buyer/seat scoping in summary queries (important correctness fix)
- Do NOT aggregate by `creative_id` alone if the route already knows the creative's `buyer_id`
- Summary query methods must accept `buyer_id` (or equivalent seat scope) and filter by it
- This avoids potential cross-seat contamination if creative IDs are not globally unique

3) Add explicit metrics availability/provenance metadata (no more fake zeros)
- Response should tell the UI whether clicks are:
  - available from source
  - unavailable due to source limitation
  - legitimately zero
- Add metadata fields (exact naming is your choice, but keep it clear), e.g.:
  - `metric_source: "rtb_daily"`
  - `availability: { clicks: true, cpc: true, ctr: true }`
  - optional `data_notes` / `limitations`
- Keep backward compatibility for existing fields where possible, but do not keep misleading semantics

4) Batch path must be efficient (avoid N+1 if possible)
- Current batch endpoint loops creative-by-creative and calls summary per creative
- Implement a batch repository query that aggregates for many creative_ids in one SQL call
- Return a mapping keyed by creative_id
- Preserve access checks before returning results

5) Frontend modal semantics
- If clicks are available:
  - show real clicks/CTR/CPC
- If clicks are unavailable (should not happen after backend fix, but support it):
  - display `N/A` and a small data-note indicator, not `0`
- Keep CPM display only when spend/impressions support it
- Do not silently coerce unavailable metrics to zero

Implementation plan (phased)

PHASE A — Backend summary V2 (repository/service)
1. Add/extend repository methods (likely `storage/postgres_repositories/creative_performance_repo.py`)
- `get_creative_summaries(creative_ids: list[str], buyer_id_by_creative?: dict[str, str], days: int) -> rows`
  OR
- `get_creative_summary(creative_id: str, buyer_id: str | None, days: int)`
  and batch variant

Required SQL behavior:
- Filter by `metric_date >= CURRENT_DATE - make_interval(days => %s)`
- Filter by `creative_id`
- Filter by `buyer_account_id = %s` when buyer is known
- Aggregate `SUM(impressions), SUM(clicks), SUM(spend_micros)`, `COUNT(DISTINCT metric_date)`

2. Add a service-layer formatter (new service or existing `PerformanceService`)
- Centralize derived metrics and availability flags
- Avoid duplicating metric math in routers

3. Keep `PostgresStore.get_creative_performance_summary(...)` behavior stable for now or deprecate it
- Preferred: route paths stop using it
- If you keep it, mark it legacy and do not extend the broken semantics further

PHASE B — API endpoints (single + batch)
1. `api/routers/performance.py::get_creative_performance`
- Continue access validation using creative -> buyer mapping
- Pass scoped `buyer_id` into the new summary service
- Return real clicks/CTR/CPC
- Add availability/provenance metadata to response model (optional fields for compatibility)

2. `api/routers/performance.py::get_batch_performance`
- Validate all creatives are within allowed buyers (existing behavior)
- Use batch aggregation path (not per-creative N+1 if avoidable)
- Ensure each creative summary uses the correct buyer scope
- Preserve `has_data` semantics

3. Schemas/types
- Update:
  - `api/schemas/performance.py`
  - `dashboard/src/types/api.ts`
  - any frontend types consuming batch/single summaries
- Add optional metadata fields (availability/provenance)

PHASE C — Frontend Preview Modal (full handling)
1. Update `dashboard/src/components/preview-modal/PreviewModal.tsx`
- Render clicks/CTR/CPC based on availability metadata
- Use `N/A` (or localized equivalent) when unavailable
- Preserve zero as a valid value only when availability says metric exists

2. Update `dashboard/src/components/preview-modal/utils.ts` data-note logic
- Zero-click anomaly warning should trigger only when clicks data is available
- Do not warn on "zero clicks" if clicks are unavailable

3. Add i18n strings if needed
- e.g. `metricUnavailable`, `clickDataUnavailable`

PHASE D — Validation + tests
1. Unit/integration tests (backend)
- Creative summary with non-zero clicks returns correct clicks/CTR/CPC
- Creative summary with impressions+spend+zero clicks returns clicks=0 and CPC=None/CTR=0 (or your defined semantics)
- Buyer-scoped query does not leak across seats
- Batch endpoint returns consistent results with single endpoint

2. Frontend behavior checks
- Modal shows:
  - real clicks when available
  - `N/A` only when unavailable
- No fake `0 clicks` due to missing source columns

3. Manual validation target (user-reported case)
- Creative ID: `2016792147219165185`
- Confirm clicks value in modal matches `rtb_daily` aggregate for selected period
- CPM remains consistent

Data model / compatibility notes
- Avoid breaking existing consumers by adding fields rather than renaming/removing in the same commit
- But do not preserve incorrect backend behavior behind the same semantics

Deliverables
1. Code changes (backend + frontend)
2. Tests (or at least targeted validation scripts/queries if no tests exist in that area)
3. Brief doc note under `docs/review/2026-02-25/audit/`:
   - `CREATIVE_MODAL_PERFORMANCE_CLICKS_PARITY_FIX.md`
   Include:
   - root cause
   - source tables used before/after
   - scoping correction note
   - validation result for the reported creative

Commit strategy (preferred)
1. Backend summary source + API schema
2. Frontend modal handling + i18n
3. Tests/docs

Acceptance criteria (must pass)
- Preview Modal never shows fake zero clicks due to source limitations
- CPM/CPC/CTR and clicks are computed from a click-capable source
- Single and batch performance endpoints use buyer-scoped queries
- Reported creative (`2016792147219165185`) reconciles against DB aggregates
```

