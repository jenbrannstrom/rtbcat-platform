# Council Master Prompt — RTBcat Platform Codebase Review

**Date:** 2026-02-16
**Platform:** RTBcat — QPS efficiency and creative intelligence tool for Google Authorized Buyers
**Stack:** FastAPI + Next.js 16 + PostgreSQL + BigQuery
**Scale:** ~450 files, 124 API endpoints, 46 DB tables, 24 repositories

---

## SECTION 1: Architecture Summary

### System Purpose
RTBcat helps media buyers on Google Authorized Buyers optimize their QPS (Queries Per Second) allocation and creative inventory. It ingests CSV performance reports, analyzes waste patterns (bid requests that don't convert to impressions), and generates actionable recommendations for pretargeting configuration changes.

### Data Flow
```
Google Authorized Buyers API                    Gmail / Manual Upload
    ↓ (API collectors)                              ↓ (CSV parsers)
Creatives, Pretargeting Configs, Endpoints      Performance CSVs (5 report types)
    ↓                                               ↓
    └────────────→ PostgreSQL ←─────────────────────┘
                       ↓
              Precompute Pipeline (BQ → PG summary tables)
                       ↓
              Analytics Engine (waste, QPS, fraud, geo, creative)
                       ↓
              Recommendation Engine (structured actions with impact)
                       ↓
              FastAPI (124 endpoints, Pydantic schemas)
                       ↓
              Next.js 16 Dashboard (TanStack React Query, 120+ API functions)
```

### Key Layers
| Layer | Location | Role |
|-------|----------|------|
| Collectors | `collectors/` | Google API clients with exponential backoff |
| Importers | `importers/` | CSV report detection, flexible column mapping, deduplication |
| Storage | `storage/` | 46 PG tables, 24 repos, BQ bridge, 17 migrations |
| Analytics | `analytics/` | Waste, QPS, fraud, geo, creative analyzers |
| Services | `services/` | Business logic, precompute orchestration, 45+ files |
| API | `api/` | FastAPI with auth middleware, 124 endpoints |
| Dashboard | `dashboard/` | Next.js 16, React Query, account/auth contexts |

---

## SECTION 2: Validated Findings with Evidence

### P0 — Runtime Crashes & Data Integrity (Fix First)

| # | Finding | Evidence | Impact |
|---|---------|----------|--------|
| **F1** | `LOW_WIN_RATE_THRESHOLD` undefined — `NameError` crash | `analytics/creative_analyzer.py:379` uses it; lines 31-36 define 5 other constants but NOT this one | Runtime crash in `_check_low_win_rate()`. Latent — triggers only when reached_queries data exists. |
| **F2** | `HIGH_WASTE_RATE_THRESHOLD` undefined — `NameError` crash | `analytics/geo_analyzer.py:211` uses it; lines 31-36 define 4 other constants but NOT this one | Runtime crash in `_check_high_waste_geos()`. Same latent pattern as F1. |
| **F3** | `selectedBuyerId` missing from `qps-summary` query key | `dashboard/src/app/page.tsx:128` — `queryKey: ["qps-summary", days]` but line 129 passes `selectedBuyerId` to API | Cross-buyer cache contamination. User switches buyer → sees old buyer's QPS data. Confirmed: `rtb-funnel` on line 139 DOES include buyer ID correctly. |
| **F4** | Inconsistent waste formula across modules | `rtb_bidstream_analyzer.py:41-45`: `win_rate = impressions / reached_queries` vs `qps_optimizer.py:72`: `waste_pct = 100 * (bid_requests - auctions_won) / bid_requests` | Different pages show different waste percentages for same data. Denominators differ by pretargeting filter rate (20-40% variance). |

### P1 — Loading Reliability

| # | Finding | Evidence | Impact |
|---|---------|----------|--------|
| **F5** | No retry on critical queries (retry: 0) | `dashboard/src/app/page.tsx:162` (pretargeting-configs), `:176` (rtb-funnel-configs) | Single timeout → permanent error state. User must manually refresh page. |
| **F6** | 15s timeout too short for analytics | `dashboard/src/lib/api/core.ts:9` — `DEFAULT_API_TIMEOUT_MS = 15000` | Analytics queries on large datasets can exceed 15s. Timeout → error → no retry. |
| **F7** | Buyer ID race condition on page load | `dashboard/src/app/page.tsx:69-79` — useEffect auto-selects first seat after async fetch | Queries gated by `seatReady` (line 120) but seats query has no timeout/retry. Slow network → blank page. |
| **F8** | Partial failure shows zero data (not error) | `page.tsx:29-56` — `transformConfigToProps` falls back to `reached: 0, impressions: 0` | Config performance fails → cards show 0% waste, 0 reached — looks like valid data, not failure. |

### P2 — Data Accuracy

| # | Finding | Evidence | Impact |
|---|---------|----------|--------|
| **F9** | Hardcoded CPM ($0.002/1000) | `analytics/waste_analyzer.py:40` — `ESTIMATED_COST_PER_1000 = 0.002`; `geo_analyzer.py:238` uses same inline | Savings estimates off by 100x for high-CPM accounts. SpendStats API has real CPM data. |
| **F10** | QPS average misrepresents peak | `analytics/waste_analyzer.py:339-340` — divides by 86400 seconds | Real RTB traffic 60-70% in 8-12 hours. Displayed QPS 2-3x lower than actual peak. |
| **F11** | Size not canonicalized in import pipeline | `importers/` — grep for `canonical_size` returns no matches; `utils/size_normalization.py` has the function but importers don't call it | CSV stores raw size strings; analytics query canonical_size → join mismatches. |
| **F12** | Fraud thresholds not format-aware | `analytics/fraud_analyzer.py:44` — `SUSPICIOUSLY_HIGH_CTR = 0.10` (10%) flat | False positives for video (naturally higher CTR), false negatives for display. |

### P3 — Missing Features

| # | Finding | Evidence | Impact |
|---|---------|----------|--------|
| **F13** | Language mismatch — backend done, dashboard only partially surfaced | `services/creative_language_service.py:115-157` — `get_geo_mismatch()` complete; `dashboard/src/components/preview-modal/LanguageSection.tsx:29` calls `getCreativeGeoMismatch()`; `dashboard/src/components/creative-card.tsx:222` lacks mismatch alert surface | Feature exists but is mostly hidden in preview flow; mismatch context is missing from primary triage surfaces. |
| **F14** | Currency mismatch — not implemented | `storage/models.py` — no `currency_code` field; no currency-country mapping | Entirely missing feature from spec. |
| **F15** | No "Apply" buttons on recommendations | Recommendations generated with full `Action` objects but UI only shows "Resolve" (acknowledge) | User must manually implement recommendations in Google's UI. |

### P4 — UX Polish

| # | Finding | Evidence | Impact |
|---|---------|----------|--------|
| **F16** | No "Data as of" timestamp | Home page doesn't display last import date | User may not realize data is a week old. |
| **F17** | Filter state lost on navigation | Campaign pages use `useState` for filters, not URL params | Filters reset when navigating away and back. |
| **F18** | No import gap detection | `importers/unified_importer.py` doesn't check for missing date ranges | Day's data missing → silent gap in analytics. |

---

## SECTION 3: Unresolved Questions

### Questions Requiring Runtime Validation

1. **F8 (Partial failure display)**: Does the UI show an error badge when `configPerformanceError` is true? Need to trace the JSX rendering path in `page.tsx` below line 200.

2. **F7 (Race condition)**: When `selectedBuyerId` is loaded from localStorage on mount, does it trigger queries before the AccountContext is fully initialized? Need to check hydration timing.

3. **F15 (Apply workflow design)**: Recommendation cards currently expose "Resolve/Dismiss" only. Should recommendations invoke settings apply endpoints directly, or remain advisory with explicit handoff?

4. **Precompute staleness**: When BQ precompute fails silently, does the UI show stale data indicators prominently enough for the user to notice?

### Architectural Questions

5. **Waste formula alignment**: Should the canonical waste formula use `reached_queries` (post-pretargeting) or `bid_requests` (pre-pretargeting)? Each measures different things. The choice affects which waste is "your fault" vs "intentional pretargeting filter."

6. **QPS peak vs average**: Should the UI show peak QPS (95th percentile hourly) alongside average? Or replace average entirely? Peak is more actionable for capacity planning.

7. **CPM source**: Should hardcoded CPM be replaced with per-account CPM from SpendStats, or should it use a configurable constant the user can set?

8. **Recommendation lifecycle**: Should expired recommendations be auto-hidden, or shown with a "stale" badge? Current expiry mechanism unclear.

---

## SECTION 4: Decision Options + Tradeoffs

### Decision 1: Waste Formula Unification

| Option | Description | Tradeoff |
|--------|-------------|----------|
| **A: Use `reached_queries` everywhere** | `waste = 100 - (impressions / reached_queries * 100)` | Measures post-pretargeting efficiency. Ignores the intentional filter. Matches what the media buyer "sees." |
| **B: Use `bid_requests` everywhere** | `waste = 100 * (bid_requests - auctions_won) / bid_requests` | Measures total pipeline efficiency. Higher waste numbers. Includes pretargeting filter as "waste." |
| **C: Show both with clear labels** | "Post-filter waste: X%" and "Total pipeline waste: Y%" | Most transparent but adds UI complexity. |

**Recommendation:** Option A for the primary metric (media buyer cares about post-filter), Option C for drill-down views.

### Decision 2: CPM Replacement Strategy

| Option | Description | Tradeoff |
|--------|-------------|----------|
| **A: Per-account CPM from SpendStats** | `actual_cpm = total_spend / total_impressions * 1000` | Accurate per-account. Requires data. Shows $0 if no spend data imported. |
| **B: Configurable constant in settings** | User sets their expected CPM | User controls accuracy. Risk of stale setting. |
| **C: Tiered defaults + override** | Default by format (display=$1, video=$10, native=$3) with user override | Good out-of-box accuracy. Complex implementation. |

**Recommendation:** Option A with fallback to current constant when spend data unavailable.

### Decision 3: Implementation Order

| Option | Description | Tradeoff |
|--------|-------------|----------|
| **A: Fix P0 bugs first, then P1, sequentially** | Safe but slower. Each band validated before next. | Lower risk, longer timeline. |
| **B: P0 + P1 in parallel** | Two developers: one on analytics crashes, one on dashboard reliability. | Faster but requires coordination on shared files. |
| **C: All P0 in one commit** | Batch all trivial P0 fixes together. | Fast for P0 (3 are trivial), may miss testing. |

**Recommendation:** Option C for P0 (all trivial fixes), then B for P1+P2 (parallel tracks for backend and frontend).

---

## SECTION 5: Requested Council Output Format

### Please produce:

1. **Ranked Implementation Path**
   - Ordered list of findings to fix, with explicit dependency edges
   - For each: files to modify, complexity estimate, acceptance test
   - Group into deployable batches (each batch = one safe deploy)

2. **Risk Assessment**
   - For each batch: what could go wrong
   - Blast radius if deployed with a bug
   - Monitoring needed after deploy

3. **Rollback Plan**
   - For each batch: exact rollback steps
   - Data migration considerations (any schema changes that can't be undone?)
   - Feature flag requirements

4. **Testing Strategy**
   - Which findings can be verified with unit tests?
   - Which require integration tests (DB + API)?
   - Which require browser/E2E tests?
   - Which require runtime validation on VM2?

5. **Deploy Sequence**
   - Batch 1: VM2 (staging) — validate
   - Batch 2: VM1 (production) — only after VM2 passes
   - For each batch: pre-deploy checks, post-deploy smoke tests

### Output Schema

```json
{
  "implementation_path": [
    {
      "batch_id": "B1",
      "findings": ["F1", "F2", "F3"],
      "files": ["analytics/creative_analyzer.py", "analytics/geo_analyzer.py", "dashboard/src/app/page.tsx"],
      "complexity": "trivial",
      "deploy_target": "VM2 → VM1",
      "acceptance_tests": ["..."],
      "rollback": "git revert <sha>",
      "risk": "LOW — constant additions and query key fix, no schema change"
    }
  ],
  "dependency_graph": {
    "B1": [],
    "B2": ["B1"],
    "B3": ["B1", "B2"]
  },
  "unresolved_decisions": ["waste formula choice", "CPM source strategy"]
}
```

---

## SECTION 6: Constraints Reminder

- **VM1 = Production** — do NOT deploy without explicit approval
- **VM2 = Staging** — safe for validation
- **No app source code was changed in this review phase** — this prompt package is for planning only
- **All findings have evidence** (file:line) or are labeled `needs_runtime_validation`
- **Local PostgreSQL** available for testing schema changes
- **No active users currently** — temporary downtime acceptable on VM2

---

## SECTION 7: Quick Reference — File Locations

### Files needing P0 fixes (trivial)
```
analytics/creative_analyzer.py:34    # Add LOW_WIN_RATE_THRESHOLD = 0.05
analytics/geo_analyzer.py:36         # Add HIGH_WASTE_RATE_THRESHOLD = 0.80
dashboard/src/app/page.tsx:128       # Add selectedBuyerId to queryKey
```

### Files needing P1 fixes (moderate)
```
dashboard/src/app/page.tsx:162,176   # Change retry: 0 → retry: 2
dashboard/src/lib/api/core.ts:9      # Increase DEFAULT_API_TIMEOUT_MS to 30000
dashboard/src/app/page.tsx:29-56     # Add error-state rendering for partial failures
dashboard/src/app/page.tsx:69-79     # Add loading state for seats, retry on failure
```

### Files needing P2 fixes (larger scope)
```
analytics/waste_analyzer.py:40       # Replace ESTIMATED_COST_PER_1000 with real CPM
analytics/waste_analyzer.py:339-340  # Add peak QPS calculation
analytics/qps_optimizer.py:72        # Align waste formula with rtb_bidstream_analyzer
importers/unified_importer.py        # Add canonical_size() call before storage
analytics/fraud_analyzer.py:44       # Parameterize thresholds by creative format
```

### Files needing P3 features (new code)
```
dashboard/src/components/creative-card.tsx  # Wire geo-mismatch display
storage/models.py                            # Add currency_code field
dashboard/src/components/recommendations/    # Add "Apply" buttons
```
