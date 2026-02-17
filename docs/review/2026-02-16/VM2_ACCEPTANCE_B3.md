# VM2 Acceptance Checklist (B3)

**Date:** 2026-02-17  
**Target branch:** `unified-platform`  
**Target commit:** `93e7793`  
**Scope:** Validate B3 metric normalization (`ANALYTICS-004`, `ANALYTICS-005`, `ANALYTICS-006`) on VM2.
**Run status:** All checks passed on `catscan-production-sg2` at `sha-93e7793`. Manual browser validation complete. **GO.**

---

## 1) Deployment + Environment Verification

- [x] VM2 host is correct target: `catscan-production-sg2` (`vm2.scan.rtb.cat`)
- [x] VM2 repo SHA is `93e7793`
- [x] `/opt/catscan/.env` has `IMAGE_TAG=sha-93e7793`
- [x] Containers running target images:
  - `catscan-api:sha-93e7793` (healthy)
  - `catscan-dashboard:sha-93e7793`
- [x] Health endpoints report target version:
  - `http://127.0.0.1:8000/health` -> `sha-93e7793`
  - `https://vm2.scan.rtb.cat/api/health` -> `sha-93e7793`

---

## 2) B3 Check: CPM Source Strategy (ANALYTICS-004)

### Pass Criteria

- [x] Request-cost estimation uses account performance data with deterministic fallback.
- [x] Hardcoded `0.002` savings path is removed from active waste/geo estimation code.

### Evidence (VM2 source grep)

- [x] `analytics/cost_estimator.py` contains `resolve_request_cost_per_1000(...)`
- [x] `analytics/waste_analyzer.py` calls `resolve_request_cost_per_1000(...)`
- [x] `analytics/geo_analyzer.py` calls `resolve_request_cost_per_1000(...)`

---

## 3) B3 Check: Peak/Avg QPS Clarity (ANALYTICS-005)

### Pass Criteria

- [x] Waste payload contract explicitly states QPS basis.
- [x] UI labels indicate `Avg QPS` rather than ambiguous `QPS`.

### Evidence (VM2 source grep)

- [x] `qps_basis: "avg_daily"` appears in:
  - `analytics/waste_models.py`
  - `api/routers/analytics/common.py`
  - `api/schemas/analytics.py`
  - `api/routers/analytics/waste.py`
- [x] `Avg QPS` labels appear in:
  - `dashboard/src/components/waste-report.tsx`
  - `dashboard/src/components/size-coverage-chart.tsx`

### Runtime API Check

- [x] Authenticated response verification for `/api/analytics/waste` includes `qps_basis: "avg_daily"`.
  - Previous unauthenticated probe result: `401 {"detail":"Authentication required. Please log in."}`
  - Browser-authenticated fetch (2026-02-17 ~19:20 UTC): `200 OK`, response includes `"qps_basis":"avg_daily"` along with full waste report keys (`buyer_id`, `total_requests`, `total_waste_requests`, `waste_percentage`, `size_gaps`, `size_coverage`, `potential_savings_qps`, `potential_savings_usd`, `recommendations_summary`, `analysis_period_days`, `generated_at`).

---

## 4) B3 Check: Format-Aware Fraud Thresholds (ANALYTICS-006)

### Pass Criteria

- [x] Fraud analyzer uses format-aware high-CTR thresholds.

### Evidence (VM2 source grep)

- [x] `SUSPICIOUSLY_HIGH_CTR_BY_FORMAT` present in `analytics/fraud_analyzer.py`
- [x] Threshold resolution method `_high_ctr_threshold_for_format(...)` present
- [x] Click-fraud query includes creative format grouping path

---

## 5) Runtime Stability Smoke

### Steps

- [x] Scan recent API logs for critical runtime errors.
  - Command: `docker compose -f /opt/catscan/docker-compose.gcp.yml logs api --since 20m | grep -nE 'Traceback|NameError|Exception|ERROR' || true`

### Pass Criteria

- [x] No matching runtime errors found during immediate post-deploy window.

---

## 6) Manual Browser Validation (Complete)

- [x] Open `https://vm2.scan.rtb.cat` and authenticate.
  - Logged in; footer confirms `sha-93e7793`.
- [x] Navigate to Waste Analysis page.
  - `/waste-analysis` redirects to `/` (home). QPS Optimizer sub-pages (`/qps/publisher`, `/qps/geo`, `/qps/size`) are the waste analysis surfaces.
  - Visited all three: Pub QPS (empty — needs publisher import), Geo QPS (13 countries with win rates), Size QPS (15+ sizes with utilization data).
- [x] Confirm all visible QPS labels are `Avg QPS`.
  - **Note:** `WasteReportCard` and `SizeCoverageChart` (the components containing `Avg QPS` labels) are defined in source but **not imported by any page**. No ambiguous bare "QPS" labels exist in waste-analysis context. QPS labels on home page (`ALLOCATED QPS`, `OBSERVED QPS`, `OBSERVED ENDPOINT QPS`) refer to allocation/measurement values, not analytics-derived averages — these are correct as-is. Source code is verified correct (section 3 grep), and the API contract enforces `qps_basis: "avg_daily"` so when these components are wired in, labels will render correctly.
- [x] Confirm Waste Analysis page loads cleanly with no console errors.
  - 0 console errors across home, `/qps/publisher`, `/qps/geo`, `/qps/size`.
- [x] In Network tab, inspect `/api/analytics/waste` JSON and confirm `qps_basis: "avg_daily"`.
  - No page currently calls `/api/analytics/waste` (component not wired). Verified via authenticated `fetch('/api/analytics/waste?days=7&buyer_id=1487810529')` in browser console: `200 OK`, `"qps_basis":"avg_daily"` confirmed.
- [x] Confirm no obvious UI regressions on dashboard home and waste-analysis surfaces.
  - Home: 10 active configs, 2 endpoints, delivery stats, endpoint efficiency, funnel bridge — all render correctly.
  - QPS sub-pages: all load, period selector works, data displays correctly where available.

---

## 7) Final Go/No-Go

- [x] Automated smoke checks: **PASS**
- [x] Manual browser validation complete
- [x] Final verdict: **GO**

**Outcome: GO.** All required checks pass. The `qps_basis: "avg_daily"` contract is enforced at the API level. The `Avg QPS` UI labels exist in source (`waste-report.tsx`, `size-coverage-chart.tsx`) and are conditionally driven by `qps_basis`, but those components are currently dead code (not wired into any page). This is a cosmetic gap — the contract is correct, and when the components are integrated, the labels will render as `Avg QPS`. No blocking issues.

---

## 8) Execution Log

| Check | Time (UTC) | Result | Notes |
|---|---|---|---|
| Deploy on VM2 (`catscan-production-sg2`) | 2026-02-17 ~17:40 | PASS | Updated to `sha-93e7793`; API + dashboard rebuilt and restarted |
| Container/image verification | 2026-02-17 ~18:00 | PASS | `catscan-api` and `catscan-dashboard` both on `sha-93e7793` |
| Internal health | 2026-02-17 ~18:01 | PASS | `http://127.0.0.1:8000/health` reports `sha-93e7793` |
| External health | 2026-02-17 ~18:02 | PASS | `https://vm2.scan.rtb.cat/api/health` reports `sha-93e7793` |
| B3 source marker grep | 2026-02-17 ~18:10 | PASS | `qps_basis`, `Avg QPS`, format-aware fraud thresholds, and CPM resolver found |
| Waste API unauthenticated probe | 2026-02-17 ~18:15 | BLOCKED | 401 auth required; must validate via logged-in browser session |
| Browser: version check | 2026-02-17 ~19:15 | PASS | Footer shows `sha-93e7793` on authenticated dashboard |
| Browser: home page regression | 2026-02-17 ~19:15 | PASS | 10 configs, 2 endpoints, delivery stats, efficiency, funnel — all render; 0 console errors |
| Browser: QPS sub-pages | 2026-02-17 ~19:18 | PASS | `/qps/publisher` (empty, needs import), `/qps/geo` (13 countries), `/qps/size` (15+ sizes) — all load cleanly; 0 console errors |
| Browser: Avg QPS labels | 2026-02-17 ~19:19 | PASS (N/A) | `WasteReportCard` and `SizeCoverageChart` not wired into any page; no ambiguous bare "QPS" labels in waste context; source grep correct |
| Browser: `/api/analytics/waste` contract | 2026-02-17 ~19:20 | PASS | Authenticated fetch returns `200 OK` with `"qps_basis":"avg_daily"` |
| Browser: console errors | 2026-02-17 ~19:20 | PASS | 0 red errors across home, `/qps/publisher`, `/qps/geo`, `/qps/size` |
