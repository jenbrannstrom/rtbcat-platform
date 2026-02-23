# RTBcat Platform — Codebase Review vs QPS Efficiency Spec

**Date:** 2026-02-16
**Build:** `sha-f3ce6ed` (API version string: `0.9.0` per `api/main.py:47`)
**Scope:** Full codebase review against spec for a QPS efficiency app for Google Authorized Buyers

---

## Executive Summary

The platform (~450 files) is a QPS efficiency and creative intelligence tool for Google Authorized Buyers, built on FastAPI + Next.js 16 + PostgreSQL. All analytics are constructed from CSV imports (no reporting API). The architecture is well-separated across API/services/storage/analytics layers with a flexible CSV importer, precompute tables, and a recommendation engine.

Three categories of issues block production readiness:

1. **Data accuracy bugs** — undefined variables causing runtime crashes, inconsistent waste calculations, QPS averaging that misrepresents peak load
2. **UI table loading failures** — race conditions with buyer ID initialization, 15s timeouts with no retry, missing query cache keys causing cross-buyer contamination
3. **UX gaps for media buyers** — language mismatch detection exists in backend but is never surfaced in the dashboard, currency mismatch not implemented, no actionable inline optimizations
4. UX has become very messy, empty sections in the UI, clogged sections on other places. Similar control features are scattered in diff places

---

## 1. Spec Alignment: QPS Efficiency for Google Auth Buyers

### Feature Matrix

| Spec Requirement | Status | Location |
|---|---|---|
| QPS waste identification | **Done** | `analytics/waste_analyzer.py`, `analytics/qps_optimizer.py` |
| CSV-based data construction | **Done** | `importers/unified_importer.py`, `importers/flexible_mapper.py` |
| Creative language mismatch detection | **Backend only** | `services/creative_language_service.py`, `utils/language_country_map.py` |
| Currency mismatch to country targeting | **Not implemented** | No currency field in creative model |
| In-app optimization actions | **Partial** | Recommendations generated, no "Apply" buttons |
| Pretargeting config management | **Done** | Full CRUD + performance overlay |
| Multi-seat support | **Done** | Buyer seat selection, permission model |
| RTB funnel visualization | **Done** | Reached > Impressions > Clicks with config breakdown |

### Gap Details

#### A. Currency Mismatch — Not Implemented

No `currency_code` field exists in the creative model (`storage/models.py`) or CSV import pipeline. Needed:
- `currency_code` field on creatives (or inferred from billing account)
- Country-to-currency mapping (similar pattern to existing `utils/language_country_map.py`)
- Mismatch detection logic in the analytics layer
- Dashboard surfacing with alert badges

#### B. Language Mismatch — Backend Done, Dashboard Not Wired

Backend is complete:
- `utils/language_country_map.py` — 40+ language-to-country mappings, `check_language_country_match()`, `get_mismatch_alert()`
- `services/creative_language_service.py:115-157` — `get_geo_mismatch()` cross-references detected language with serving countries
- `api/analysis/language_analyzer.py` — Gemini-based language detection

The dashboard never calls the geo-mismatch endpoint. The creatives page shows `detected_language` but does not flag mismatches.

---

## 2. Data Accuracy Issues

### 2a. CRITICAL: Undefined Variables — Runtime Crashes

**`analytics/creative_analyzer.py:379`**
```python
CAST(...) / COALESCE(...) < ?
""", (f"-{days} days", LOW_WIN_RATE_THRESHOLD))
```
`LOW_WIN_RATE_THRESHOLD` is **never defined** in this module. Calling `_check_low_win_rate()` throws `NameError`.

**`analytics/geo_analyzer.py:211`**
```python
if waste_rate > HIGH_WASTE_RATE_THRESHOLD:
```
`HIGH_WASTE_RATE_THRESHOLD` is **never defined** in this module. `_check_high_waste_geos()` crashes.

Both methods are guarded by comments saying they require `reached_queries` data, but there is no proper safeguard — if the data exists, the code runs and crashes.

### 2b. Inconsistent Waste Percentage Calculations

Two different formulas across the codebase:

| Module | Formula | Denominator |
|---|---|---|
| `analytics/rtb_bidstream_analyzer.py` ~line 349 | `waste_pct = 100 - (impressions / reached_queries * 100)` | reached_queries |
| `analytics/qps_optimizer.py` ~line 72 | `waste_pct = 100 * (bid_requests - auctions_won) / bid_requests` | bid_requests |

Different denominators (`reached_queries` vs `bid_requests`) and different numerators (`impressions` vs `auctions_won`). Home page config cards show one source; QPS report shows the other. A media buyer comparing these sees contradictory waste percentages.

### 2c. QPS Calculation Misrepresents Peak Load

**`analytics/waste_analyzer.py:339-340`**
```python
daily_requests = request_count / days
estimated_qps = daily_requests / SECONDS_PER_DAY  # 86400
```

Calculates **average QPS** assuming uniform 24-hour distribution. Real RTB traffic is heavily skewed — 60-70% of traffic in 8-12 peak hours. Displayed QPS can be 2-3x lower than actual peak QPS, causing media buyers to underestimate waste impact.

### 2d. Hardcoded Savings Estimate

**`analytics/waste_analyzer.py:40`**
```python
ESTIMATED_COST_PER_1000 = 0.002  # $0.002 per 1000 requests
```

Used for "potential monthly savings" calculations. This is an undocumented constant with no basis in actual account CPMs. Real cost varies by 100x depending on the account. The spendStats API already has actual CPM data — should be used instead.

### 2e. Size Canonicalization Inconsistency

CSV imports may store raw size strings (`"300x250"`, `"300 x 250"`, `"300x250 (Medium Rectangle)"`). The waste analyzer queries `rtb_traffic.canonical_size` but the CSV importer may not consistently canonicalize sizes through `utils/size_normalization.canonical_size()` before storage.

### 2f. Fraud Detection Thresholds Not Calibrated

`analytics/fraud_analyzer.py` uses fixed thresholds (10% CTR = suspicious) without accounting for creative format (video has naturally higher CTR), device type, or vertical. Generates false positives for video campaigns and misses fraud in low-CTR display campaigns.

---

## 3. UI Table Loading Failures

### 3a. Buyer ID Race Condition (Root Cause of Intermittent Failures)

**`dashboard/src/app/page.tsx:69-79`**
```tsx
const { data: seats } = useQuery({ queryKey: ["seats"], queryFn: ... });
useEffect(() => {
  if (!selectedBuyerId && seats && seats.length > 0) {
    setSelectedBuyerId(seats[0].buyer_id);
  }
}, [selectedBuyerId, seats, setSelectedBuyerId]);

const seatReady = !!selectedBuyerId;
// All queries: enabled: seatReady
```

**Failure modes:**
1. Seats query takes >15s on slow network → blank page, no loading indicator beyond "Select a seat"
2. `selectedBuyerId` set from localStorage before context initializes → queries fire with undefined → potential cross-buyer data
3. Buyer changes → old queries still in-flight → stale results arrive after new buyer is selected

### 3b. No Retry on API Timeout

**`dashboard/src/lib/api/core.ts:9`** — 15-second timeout with no retry:
```tsx
const DEFAULT_API_TIMEOUT_MS = 15000;
```

Some queries have custom shorter timeouts (12s for config performance). Combined with `retry: 0` on pretargeting and config performance queries (`page.tsx:163,177`), a single slow response means entire sections show error state with no recovery path.

### 3c. Missing `selectedBuyerId` in Query Keys

**`dashboard/src/app/page.tsx:128`**
```tsx
queryKey: ["qps-summary", days],
queryFn: () => getQPSSummary(days, selectedBuyerId || undefined),
```

`selectedBuyerId` is passed to the API call but is **not in the query key**. React Query serves cached data from the previous buyer when the buyer changes. Some queries include it (`["rtb-funnel", days, selectedBuyerId]` on line 139), others don't — leading to data from mixed buyers on the same page.

### 3d. Partial Data Display Without Clear Indicators

Home page makes 6 parallel queries. If config performance fails but pretargeting configs succeeds, config cards show 0% waste / 0 reached / 0 impressions — which looks like accurate data showing no performance, not a loading failure. The amber warning ("Config performance metrics are delayed") appears but is easily missed.

---

## 4. UX Evaluation for Media Buyers

### What Works Well
- Pretargeting config cards with sortable columns (waste rate, win rate, reached)
- Period selector (7d/14d/30d) is simple and effective
- RTB funnel visualization gives clear bidding pipeline picture
- Skeleton loading states provide visual feedback
- Config breakdown panel (expandable per-config) enables drill-down
- Drag-and-drop creative clustering on campaigns page

### Critical UX Problems

**No Actionable Optimization Flow.** The app identifies waste but doesn't let users fix it. The recommendation engine generates specific actions (e.g., "Block size 301x250 in pretargeting") but there are no "Apply" buttons. Media buyers must manually go to Google's UI to implement changes.

**Language Mismatch Not Visible.** Despite complete backend support, the dashboard doesn't show language mismatch alerts on creative cards or in recommendations. A media buyer running German-language creatives targeting Brazil gets no warning.

**Currency Mismatch Not Implemented.** No visibility into currency misalignment.

**Confusing Data Staleness.** When precompute data is stale, the UI shows a small amber badge but continues displaying stale numbers as current. No timestamp showing "Data as of X" on main metrics.

**Filter State Lost on Navigation.** Campaign page filters (country, sort) use local `useState` — reset when navigating away.

**No Data Freshness Indicators.** Home page doesn't show when data was last imported. A media buyer may not realize they're looking at week-old data.



NOTE from project owner: "The UX of any one pretargting table has become scattered and illogical.

OPening the hidden sizes is broken /home/x1-7/Pictures/Screenshots/Screenshot from 2026-02-13 23-40-49.png

The QPS setting says "unset" - it should say what the AB UI says. It's also in the wrong place, it should be at the top, not inside 'By Publisher'. Same with checkboxes: "Banner, Audio and Video, Native". These are impotrant control settings - there is massive real-estate taken up by empty space of the metrics.
/home/x1-7/Pictures/Screenshots/Screenshot from 2026-02-13 23-43-18.png

Th eui should be grouped logicaly: control buttons such as the Pause button, QPS setting, 'Banner, Audio and Video, Native' selectors, maybe others are all control butons and can be grouped together. Then group top-level metrics.

'By geo' there is no dropdown, only an empty field asking for country. make it a dropdown with all countries available and then cities within. Just like the Google UI. 

The "history" on the left and "open" on the right is not needed. Just place History on the right. no second buton needed.

Go back to the simple design: By Creative, By Size, By Geo, By Publisher - they show metrics and allow on/off.

Make wireframes in .md, in /home/x1-7/Documents/rtbcat-platform/docs/ui-publisher-list-management.md

Message: "Publisher mode is currently Blacklist. Use Block/Unblock to stage pending publisher targeting updates." this is great, but where do we switch to whitelist?

Missing workflow: I selected to BLOCK a publisher and left it PENDING. I switched to another pretargeting setting. Then switched back. The pending was still on that specific publisher but the modal to "committo Google" is missing. THat dialog box must stay at as bottom bar on screen "

---

## 5. CSV Data Pipeline Review

### Strengths
- Flexible column mapper with synonym support handles variations in Google's CSV exports
- Row-level deduplication via MD5 hash prevents double-counting
- Import history with detailed batch tracking (rows read/imported/skipped/duplicate)
- Parquet export pipeline for BigQuery archival

### Issues
- **No validation that imported data covers expected date ranges** — if a day's data is missing, analytics silently have a gap
- **No alerting on import anomalies** — if row counts drop 90% vs previous import, no warning
- **Spend precision loss**: `int(spend_usd * 1_000_000)` truncates sub-micro amounts (minor but compounds)
- **Date format assumption**: No timezone handling; assumes dates in CSV match system timezone

---

## 6. Prioritised Recommendations

### P0 — Bugs Causing Wrong Data (Fix Immediately)

| # | Issue | File | Line |
|---|---|---|---|
| 1 | Define `LOW_WIN_RATE_THRESHOLD` (e.g., `0.05`) | `analytics/creative_analyzer.py` | ~34 |
| 2 | Define `HIGH_WASTE_RATE_THRESHOLD` (e.g., `0.8`) | `analytics/geo_analyzer.py` | ~36 |
| 3 | Add `selectedBuyerId` to `qps-summary` query key | `dashboard/src/app/page.tsx` | 128 |
| 4 | Unify waste calculation formula across codebase | `analytics/rtb_bidstream_analyzer.py`, `analytics/qps_optimizer.py` | multiple |

### P1 — Table Loading Reliability

| # | Issue | Fix |
|---|---|---|
| 5 | No retry on timeout | Add `retry: 2` to critical queries (funnel, config performance, endpoint efficiency) |
| 6 | 15s timeout too short for analytics | Increase to 30s for analytics queries |
| 7 | Partial failure looks like zero data | Show explicit error state with "Retry" button when config performance fails |
| 8 | Buyer ID race condition | Don't render data sections until buyer context is fully initialized |

### P2 — Data Accuracy Improvements

| # | Issue | Fix |
|---|---|---|
| 9 | Size canonicalization gaps | Pass sizes through `canonical_size()` on CSV import |
| 10 | Hardcoded CPM ($0.002/1000) | Replace with actual account CPM from spend data |
| 11 | QPS average misleads on peak | Calculate and display 95th percentile hourly QPS alongside average |
| 12 | Fraud thresholds not format-aware | Separate thresholds for banner, video, native |

### P3 — Missing Spec Features

| # | Issue | Fix |
|---|---|---|
| 13 | Language mismatch not in dashboard | Add alert badges on creative cards, add "Mismatches" filter tab |
| 14 | Currency mismatch not implemented | Add `currency_code` to creative model, build country-to-currency map, add detection |
| 15 | No "Apply" actions on recommendations | Generate pretargeting config change requests, add action buttons |

### P4 — UX Polish

| # | Issue | Fix |
|---|---|---|
| 16 | No "Data as of" timestamp | Show last import date on home page |
| 17 | Filters reset on navigation | Persist filter state in URL params |
| 18 | No import gap detection | Warn when expected daily data is missing |
| 19 | Stale data not prominent | Show data age prominently when precompute is behind |

---

## Architecture Reference

```
CSV Imports -> Unified Importer -> PostgreSQL (rtb_daily, rtb_bidstream)
                                        |
                              Precompute Service -> Materialized Summaries
                                        |
                              Analytics Engine -> Waste/QPS/Fraud/Geo Analysis
                                        |
                              FastAPI Routes -> Recommendation Engine
                                        |
                              Next.js Dashboard <- React Query (30s stale time)
```

The architecture is well-structured. The remaining 10% of work concentrates in: fixing data accuracy bugs (P0), making the UI resilient to partial failures (P1), and surfacing language/currency mismatch features that already have backend support (P3).
