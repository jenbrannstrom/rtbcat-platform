# Production Acceptance Report - sha-5ad446c

Date: 2026-02-18
Environment: VM1 (`catscan-production-sg`), Production URL (`https://scan.rtb.cat`)
Branch: `unified-platform`
Commit: `5ad446c`
Verdict: GO

## Executive Summary
Production VM1 is running `sha-5ad446c` across API, dashboard, and footer version display. Local git on `unified-platform` matches production. Core routes (`/`, `/campaigns`, `/creatives`) load correctly with zero console errors. Home-config fallback wiring is confirmed in production responses: `/api/analytics/home/configs` now includes `requested_days`, `effective_days`, `fallback_applied`, `fallback_reason`, and `data_state`. Fallback was not triggered for buyer `1487810529` because 7-day data exists; this is data-dependent and not a regression.

## Results
- `Local branch + SHA`: PASS
  - Evidence: `unified-platform` at `5ad446c`
- `API health version`: PASS
  - Evidence: `/health` reports `version=sha-5ad446c`, `status=healthy`, `database_exists=true`
- `API image tag`: PASS
  - Evidence: `catscan-api:sha-5ad446c`
- `Dashboard image tag`: PASS
  - Evidence: `catscan-dashboard:sha-5ad446c`
- `Footer SHA`: PASS
  - Evidence: UI footer shows `sha-5ad446c`
- `Home page loads`: PASS
  - Evidence: pretargeting configs, endpoints, efficiency section rendered
- `Campaigns page loads`: PASS
  - Evidence: clusters + totals rendered
- `Creatives page loads`: PASS
  - Evidence: creatives list + filters + thumbnails rendered
- `Console errors`: PASS
  - Evidence: no red console errors across tested pages
- `/api/analytics/home/funnel`: PASS
  - Evidence: HTTP 200
- `/api/analytics/home/configs`: PASS
  - Evidence: HTTP 200
- `/api/seats`: PASS
  - Evidence: HTTP 200
- `home/configs days=7 includes new fields`: PASS
  - Evidence: `requested_days=7`, `effective_days=7`, `fallback_applied=false`, `fallback_reason=null`, `data_state=healthy`
- `home/configs days=30 includes new fields`: PASS
  - Evidence: `requested_days=30`, `effective_days=30`, `fallback_applied=false`, `fallback_reason=null`, `data_state=healthy`
- `Fallback exercised`: N/A
  - Evidence: buyer `1487810529` has current 7d data, so fallback path is not activated

## Blockers
None.

## Conclusion
GO. Release `sha-5ad446c` is healthy in production with SHA parity and expected runtime behavior. The fallback contract wiring is present and validated; non-triggered fallback path is due to data state, not code failure.
