# C-EPT-001 Endpoint Freshness RCA (2026-02-25)

## Summary

On February 25, 2026, production deploys were using a temporary contract bypass (`ALLOW_CONTRACT_FAILURE=true`) because contract `C-EPT-001` was failing with stale endpoint observation rows (`rtb_endpoints_current`).

Root cause was not missing endpoint data logic. The issue was scheduler-path drift: the active scheduled refresh paths refreshed precompute tables but did not refresh endpoint observations.

Fix was deployed in commit `cabab81`, and contract enforcement was restored the same day.

## Symptom

- Contract check failure: `C-EPT-001` (`rtb_endpoints_current populated`)
- Reported state before fix: `11/11 stale endpoints`
- Deploys were proceeding only because `ALLOW_CONTRACT_FAILURE=true` was enabled in the deploy workflow.

## Root Cause

There were multiple refresh entry points in the codebase:

- `scripts/refresh_precompute.py` (does refresh endpoint observations)
- `scripts/refresh_home_cache.py` (did not refresh endpoint observations before fix)
- `POST /api/precompute/refresh/scheduled` (did not refresh endpoint observations before fix)

Production scheduler usage included paths that refreshed home/config/RTB precompute tables but skipped `EndpointsService.refresh_endpoints_current()`. As a result, `rtb_endpoints_current.observed_at` aged past the 24-hour threshold and `C-EPT-001` failed.

## Fix

Commit: `cabab81` (`Refresh endpoint observations in scheduled precompute paths`)

Changes:

- `api/routers/precompute.py`
  - Added `EndpointsService.refresh_endpoints_current()` to `/precompute/refresh/scheduled`
  - Added `endpoints_current_rows` to the scheduled refresh response for visibility
- `scripts/refresh_home_cache.py`
  - Added `EndpointsService.refresh_endpoints_current()` after home cache refresh
  - Prints refreshed endpoint observation row count

## Deployment + Verification (February 25, 2026)

1. Redeployed backend with `cabab81`
2. Triggered refresh (post-deploy)
3. Verified `rtb_endpoints_current` refreshed for all 11 endpoints across 4 bidders
4. Re-ran contracts: `5 PASS`, `0 FAIL`, including `C-EPT-001`
5. Removed `ALLOW_CONTRACT_FAILURE=true` bypass and confirmed deploy gate enforcement remained clean

## Preventive Notes

- Keep endpoint-observation refresh coupled to all scheduled precompute/home refresh entry points.
- When adding new scheduler routes/scripts, include `rtb_endpoints_current` freshness in acceptance checks.
- `C-EPT-001` should remain a hard deploy gate (no bypass) unless there is an active incident with explicit RCA and rollback plan.
