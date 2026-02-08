# Efficiency Metrics Plan: Allocated QPS vs Observed RTB Load

Date: 2026-02-07
Owner: RTBcat engineering
Status: Draft implementation spec

## 1) Problem Statement

Current UI displays endpoint `maximum_qps` from Google endpoint config (`rtb_endpoints.maximum_qps`) as "QPS". Users interpret this as real incoming load, but this value is only invited/allocated capacity. Actual request volume is spend-constrained and controlled by Google's throttling.

Observed mismatch example:
- CatScan endpoints: Asia `100,000`, Europe `4,428`, US East `100,000` (total `204,428` allocated)
- Google UI appears to show: US East `100,000`, Asia `200,000`, no EU row

This creates decision risk:
- Overestimating real load
- Misdiagnosing pretargeting efficiency
- Missing endpoint mapping/config drift

## 2) Goals

1. Make metric semantics explicit in UI.
2. Reconcile endpoint inventory between CatScan-synced endpoints and Google-observed delivery rows.
3. Provide efficiency KPIs based on observed traffic, not invited caps.
4. Detect and surface mapping/config drift (missing endpoint/region rows).
5. Keep decisions tied to spend-constrained reality.

## 3) Non-Goals

1. Infer true bidder-side ingress QPS (not available by constraint).
2. Replace Google breakout as source of truth for top-of-funnel inventory.
3. Auto-edit endpoint max QPS; this plan only recommends/operator-guides.

## 4) Metric Semantics (UI + API source-of-truth)

Use these canonical definitions everywhere:

- `allocated_qps`: Configured endpoint max QPS invited from Google (`rtb_endpoints.maximum_qps`).
- `observed_query_rate_qps_avg`: `total_reached_queries / window_seconds` from RTB funnel/breakout aggregates.
- `observed_query_rate_qps_p95` (optional phase 2): P95 daily or hourly observed query rate.
- `qps_utilization_pct`: `observed_query_rate_qps_avg / allocated_qps * 100`.
- `allocation_overshoot_x`: `allocated_qps / observed_query_rate_qps_avg`.
- `pretargeting_loss_pct`: `filtered_impressions / available_impressions * 100` (from breakout when available).
- `supply_capture_pct`: `inventory_matches / available_impressions * 100` (from breakout when available).

Display rule:
- Never label `allocated_qps` as "incoming" or "actual".
- Show `allocated` and `observed` side by side with ratio.

## 5) Ballpark Validation Using RTB Breakout

Yes, breakout can be used as ballpark sanity check.

For 7d window example in screenshots:
- Reached queries: `605.2M`
- Window seconds: `7 * 24 * 3600 = 604,800`
- Avg observed query rate: `~1000.7 QPS`
- Allocated cap: `204,428 QPS`
- Utilization: `~0.49%`
- Overshoot: `~204x`

Interpretation: low utilization can be normal at low spend; it is only a problem if persistently low relative to spend trend and pretargeting opportunities.

### Breakout data point mapping to CatScan

| Breakout data point | Screenshot value | Reconstructable in CatScan? | How | Useful for efficiency (Y/N) |
|---|---:|---|---|---|
| Date range | 4.22tn | Yes | UI filter/window | Y |
| Available impressions | 4.22tn | Partial (proxy) | Use `rtb_bidstream.bid_requests` aggregate as top-of-funnel proxy | Y |
| Filtered impressions | 3.57tn | Partial (derived proxy) | `available_impressions_proxy - inventory_matches` | Y |
| Filtered impressions rate | 84.7% | Partial (derived proxy) | `filtered_impressions_proxy / available_impressions_proxy` | Y |
| Filter reason: Pre-targeting configurations | 84.7% | No (exact), maybe partial | Not a direct field in current core tables; only approximate inference | Y |
| Inventory matches | 646bn | Yes (if RTB funnel CSV imported) | `rtb_bidstream.inventory_matches` | Y |
| Inventory match rate | 15.3% | Yes (derived) | `inventory_matches / available_impressions_proxy` | Y |
| Auctions won | 392m | Yes (if RTB funnel CSV imported) | `rtb_bidstream.auctions_won` | Y |
| Win rate | 17% | Yes (conditional) | Prefer `auctions_won / bids_in_auction`; fallback proxy if missing | Y |
| Filtered bids | 109m | Yes (if Bid Filtering CSV imported) | `rtb_bid_filtering.bids` (filtered reasons rollup) | Y |
| Filtered bid rate | 5% | Yes (conditional) | From filtered bids over bid base (definition must be fixed in UI) | Y |

## 6) Backend Implementation Plan

## 6.1 Add endpoint efficiency API (new)

Add route:
- `GET /analytics/home/endpoint-efficiency?days=7&buyer_id=...`

Response shape:

```json
{
  "period_days": 7,
  "window": {
    "start_date": "2026-01-31",
    "end_date": "2026-02-06",
    "seconds": 604800
  },
  "summary": {
    "allocated_qps": 204428,
    "observed_query_rate_qps_avg": 1000.7,
    "qps_utilization_pct": 0.49,
    "allocation_overshoot_x": 204.3,
    "total_reached_queries": 605200000,
    "total_impressions": 263000000,
    "win_rate_pct": 43.5
  },
  "endpoint_reconciliation": {
    "status": "warning",
    "counts": {
      "catscan_endpoints": 3,
      "google_delivery_rows": 2,
      "mapped": 2,
      "missing_in_google": 1,
      "extra_in_google": 0
    },
    "rows": [
      {
        "catscan_endpoint_id": ".../endpoints/asia",
        "catscan_location": "ASIA",
        "allocated_qps": 100000,
        "google_location": "ASIA",
        "mapping_status": "mapped"
      },
      {
        "catscan_endpoint_id": ".../endpoints/eu",
        "catscan_location": "EUROPE",
        "allocated_qps": 4428,
        "google_location": null,
        "mapping_status": "missing_in_google"
      }
    ]
  },
  "funnel_breakout": {
    "available_impressions": 4220000000000,
    "inventory_matches": 646000000000,
    "filtered_impressions": 3570000000000,
    "pretargeting_loss_pct": 84.7,
    "supply_capture_pct": 15.3
  },
  "alerts": [
    {
      "code": "ENDPOINT_MAPPING_MISSING",
      "severity": "high",
      "message": "1 endpoint configured in CatScan has no matching Google delivery row in selected period"
    }
  ]
}
```

Implementation notes:
- Keep route under existing home analytics namespace to reuse selected seat flow.
- Compute `observed_query_rate_qps_avg` from existing funnel totals (`home_seat_daily.reached_queries`) for same period.
- Use `rtb_endpoints` for allocated caps grouped by bidder.

## 6.2 Data reconciliation model (phase 1 minimal)

No hard migration required initially; compute in-memory mapping by normalized location key:
- `ASIA` <-> `ASIA`
- `US_EAST` <-> `US East`
- `EUROPE` <-> `Europe`

Add a small normalization utility in service layer. Unknown values -> `UNMAPPED`.

Phase 2 (if needed): add persisted mapping table for manual overrides.

Proposed table:
- `endpoint_location_mapping`
- columns: `bidder_id`, `catscan_endpoint_id`, `catscan_location`, `google_location_label`, `status`, `confidence`, `updated_at`, `updated_by`

## 6.3 Files to touch

Backend:
- `api/routers/analytics/home.py` (new route)
- `services/home_analytics_service.py` (new method `get_endpoint_efficiency_payload`)
- `storage/postgres_repositories/home_repo.py` (query helpers for allocated_qps + totals)
- `api/schemas/analytics.py` (response model)

Frontend API:
- `dashboard/src/lib/api/analytics.ts` (new `EndpointEfficiencyResponse` + fetcher)

## 7) Frontend Implementation Plan

## 7.1 Update endpoint card semantics

In `dashboard/src/components/rtb/account-endpoints-header.tsx`:
- Rename label from `Total QPS Allocated` -> `Allocated QPS Cap`.
- Tooltip text update:
  - "Allocated QPS is a ceiling you invite from Google, not guaranteed incoming traffic."
  - "Actual load is spend-constrained and shown in Observed Query Rate."

## 7.2 Add efficiency summary cards

In home page (`dashboard/src/app/page.tsx` near endpoint header), add compact cards:
- `Allocated QPS Cap`
- `Observed Query Rate (avg)`
- `Utilization %`
- `Overshoot x`

Color rules:
- utilization `< 1%` -> neutral/yellow (not red by default)
- utilization `< 0.2%` and spend stable -> warning
- mapping missing -> red badge regardless of utilization

## 7.3 Add endpoint reconciliation table

New component suggested:
- `dashboard/src/components/rtb/endpoint-reconciliation-panel.tsx`

Columns:
- Location
- CatScan allocated QPS
- Google delivery row
- Mapping status (`mapped`, `missing_in_google`, `extra_in_google`)

Behavior:
- Default collapsed on small screens
- Always visible warning row when any `missing_in_google`

## 7.4 Add funnel bridge panel

Show breakout-to-funnel bridge with explicit context:
- `Available impressions`
- `Inventory matches`
- `Filtered impressions`
- `Reached queries`
- `Impressions`

Purpose: connect top-funnel loss to real observed load and outcomes.

## 8) Alerting and Decision Rules

Start with deterministic rules:

1. `ENDPOINT_MAPPING_MISSING` (High)
- Trigger: `missing_in_google > 0` for selected period.

2. `ALLOCATED_VS_OBSERVED_GAP` (Medium)
- Trigger: utilization `< 0.2%` for 7d and spend/day not falling.

3. `PRETARGETING_LOSS_HIGH` (Medium)
- Trigger: `pretargeting_loss_pct > 70%` and impressions meaningful.

4. `NO_ACTION_EXPECTED_LOW_SPEND` (Info)
- Trigger: low spend tier and stable win outcomes.

## 9) Rollout Phases

Phase 1 (1 sprint):
- Metric semantic fixes
- New endpoint efficiency API
- Summary cards + reconciliation table
- Missing endpoint alerts

Phase 2 (1 sprint):
- Persisted mapping overrides
- P95 observed query rates
- Trend chart (28d utilization vs spend)

Phase 3:
- Recommendation engine integration (auto-suggest cap reductions or pretargeting cleanup)

## 10) Acceptance Criteria

1. UI no longer implies allocated QPS equals actual incoming traffic.
2. For any seat and period, users can see:
- allocated cap,
- observed average rate,
- utilization/overshoot,
- endpoint mapping status.
3. Missing endpoint rows (like EU absent in Google view) are surfaced automatically.
4. Ballpark reconciliation uses same period boundaries across all compared metrics.
5. No regression to existing funnel/config cards.

## 11) QA Plan

1. Unit test formula helpers:
- utilization/overshoot/rounding/zero division.

2. API integration tests:
- seat with full mapping,
- seat with missing endpoint,
- no data period.

3. UI tests:
- tooltip semantics,
- warning badge for missing mapping,
- card values for known fixture.

4. Manual validation script (given screenshot period):
- Verify 7d query-rate conversion from reached queries,
- verify allocated total equals sum of endpoint caps,
- verify expected warning for EU-missing case.

## 12) Risks and Mitigations

1. Breakout fields may not always be present.
- Mitigation: mark fields as nullable; degrade gracefully to funnel-only efficiency.

2. Location-based mapping may misclassify non-standard endpoint labels.
- Mitigation: phase 2 manual mapping overrides.

3. Users may interpret low utilization as always bad.
- Mitigation: include spend-aware helper text and neutral threshold defaults.

## 13) UX Wireframe

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│  RTBcat Platform — Home                                        [7d ▾] [Seat ▾] │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌── ALERTS ───────────────────────────────────────────────────────────────────┐ │
│  │ 🔴 HIGH  1 endpoint configured in CatScan has no matching Google          │ │
│  │          delivery row in selected period (EUROPE)                          │ │
│  │ 🟡 MED   Utilization < 0.2% for 7d while spend is stable                 │ │
│  │ 🟡 MED   Pretargeting loss at 84.7% — review pretargeting config          │ │
│  └────────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ╔═══════════════════════ EFFICIENCY SUMMARY CARDS ═══════════════════════════╗ │
│  ║                                                                           ║ │
│  ║  ┌──────────────────┐ ┌──────────────────┐ ┌───────────────┐ ┌──────────┐ ║ │
│  ║  │ Allocated QPS Cap│ │ Observed Query   │ │ Utilization   │ │Overshoot │ ║ │
│  ║  │                  │ │ Rate (avg)       │ │               │ │          │ ║ │
│  ║  │    204,428       │ │    1,000.7       │ │    0.49%      │ │  204x    │ ║ │
│  ║  │                  │ │    QPS           │ │   ● neutral   │ │          │ ║ │
│  ║  │ ⓘ Ceiling, not  │ │ ⓘ From reached  │ │               │ │          │ ║ │
│  ║  │   actual load    │ │   queries / 7d   │ │               │ │          │ ║ │
│  ║  └──────────────────┘ └──────────────────┘ └───────────────┘ └──────────┘ ║ │
│  ║                                                                           ║ │
│  ╚═══════════════════════════════════════════════════════════════════════════╝ │
│                                                                                 │
│  ┌── ENDPOINT RECONCILIATION ──────────────────────────────── [▾ Expand] ──┐   │
│  │                                                                         │   │
│  │  ● 3 CatScan endpoints  ● 2 Google delivery rows  ● 1 missing          │   │
│  │                                                                         │   │
│  │  ┌──────────┬───────────────────┬──────────────────┬───────────────────┐ │   │
│  │  │ Location │ CatScan Alloc QPS │ Google Delivery  │ Mapping Status   │ │   │
│  │  ├──────────┼───────────────────┼──────────────────┼───────────────────┤ │   │
│  │  │ ASIA     │        100,000    │ ASIA             │ ✅ mapped        │ │   │
│  │  ├──────────┼───────────────────┼──────────────────┼───────────────────┤ │   │
│  │  │ US EAST  │        100,000    │ US East          │ ✅ mapped        │ │   │
│  │  ├──────────┼───────────────────┼──────────────────┼───────────────────┤ │   │
│  │  │ EUROPE   │          4,428    │       —          │ 🔴 missing in    │ │   │
│  │  │          │                   │                  │    Google         │ │   │
│  │  └──────────┴───────────────────┴──────────────────┴───────────────────┘ │   │
│  │                                                                         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌── FUNNEL BRIDGE ───────────────────────────────────────────────────────────┐ │
│  │                                                                           │ │
│  │  Available         Inventory         Filtered          Reached    Impr.    │ │
│  │  Impressions       Matches           Impressions       Queries            │ │
│  │                                                                           │ │
│  │  4.22T ──────────► 646B ──────────► 3.57T ─────────► 605.2M ──► 263M     │ │
│  │  100%              15.3%             84.7% loss        ↓          ↓       │ │
│  │                    supply                              observed   win     │ │
│  │                    capture                             load       rate    │ │
│  │                                                        1,001 QPS  43.5%  │ │
│  │                                                                           │ │
│  │  ┌─────────────────────────────────────────────────────────────────────┐   │ │
│  │  │  ⓘ  Pretargeting loss: 84.7%                                     │   │ │
│  │  │     84.7% of available supply is filtered before reaching your    │   │ │
│  │  │     bidder. Review pretargeting config to capture more supply.    │   │ │
│  │  └─────────────────────────────────────────────────────────────────────┘   │ │
│  │                                                                           │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
│  ┌── EXISTING ENDPOINT CARDS (updated labels) ────────────────────────────────┐ │
│  │                                                                           │ │
│  │  ┌───────────────────────┐ ┌───────────────────────┐ ┌──────────────────┐ │ │
│  │  │ ASIA                  │ │ US EAST               │ │ EUROPE           │ │ │
│  │  │                       │ │                       │ │                  │ │ │
│  │  │ Allocated QPS Cap  ⓘ │ │ Allocated QPS Cap  ⓘ │ │ Allocated QPS ⓘ │ │ │
│  │  │      100,000         │ │      100,000         │ │       4,428     │ │ │
│  │  │                       │ │                       │ │                  │ │ │
│  │  │ ┌───────────────────┐ │ │ ┌───────────────────┐ │ │ 🔴 No Google   │ │ │
│  │  │ │ Tooltip:          │ │ │                       │ │    delivery row │ │ │
│  │  │ │ Allocated QPS is  │ │ │                       │ │                  │ │ │
│  │  │ │ a ceiling invited │ │ │                       │ │                  │ │ │
│  │  │ │ from Google, not  │ │ │                       │ │                  │ │ │
│  │  │ │ guaranteed load.  │ │ │                       │ │                  │ │ │
│  │  │ │ See Observed      │ │ │                       │ │                  │ │ │
│  │  │ │ Query Rate.       │ │ │                       │ │                  │ │ │
│  │  │ └───────────────────┘ │ │                       │ │                  │ │ │
│  │  └───────────────────────┘ └───────────────────────┘ └──────────────────┘ │ │
│  │                                                                           │ │
│  └───────────────────────────────────────────────────────────────────────────┘ │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

### Layout summary

| Section | Spec Reference | Key UX decisions |
|---|---|---|
| **Alerts banner** | §8 | Top of page, color-coded severity chips. Dismissible but persistent if unresolved. |
| **Efficiency summary cards** | §7.2 | 4 compact stat cards in a row. Utilization color: neutral/yellow at <1%, warning at <0.2%. Red badge on mapping issues. |
| **Endpoint reconciliation table** | §7.3 | Collapsible panel (collapsed by default on mobile). Summary pill counts above table. Red row highlight for `missing_in_google`. |
| **Funnel bridge** | §7.4 | Horizontal flow diagram connecting breakout stages to observed load and win rate. Inline helper text for pretargeting loss. |
| **Existing endpoint cards** | §7.1 | Label renamed to "Allocated QPS Cap". Tooltip clarifies it's a ceiling, not actual traffic. Missing-mapping badge on affected cards. |

### Color rules

- **Utilization < 1%** — yellow/neutral background (not alarming)
- **Utilization < 0.2% + stable spend** — orange warning
- **Missing endpoint mapping** — red badge, always shown regardless of utilization
- **Pretargeting loss > 70%** — medium-severity yellow callout
