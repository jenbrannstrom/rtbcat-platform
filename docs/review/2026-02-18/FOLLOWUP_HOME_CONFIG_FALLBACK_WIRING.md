# Follow-up: Wire Breakdown Fallback Metadata to Home Config Panel

## Context
Production release `sha-e45cad0` is GO. Backend/API fallback behavior is correct for config breakdowns:
- `requested_days=7`
- `effective_days=30`
- `fallback_applied=true`
- `fallback_reason=no_rows_7d_used_30d`

Current home dashboard path reads precomputed data from `/api/analytics/home/configs`, so the fallback banner in `config-breakdown-panel.tsx` is not reached on that flow.

## Goal
Expose fallback state to the home config panel so users can see when the requested window had no rows and a wider window was used.

## Scope
- Decide one integration path:
1. Return fallback metadata on `/api/analytics/home/configs`, or
2. Switch the panel data source to the breakdown endpoint where fallback metadata already exists.

- Ensure UI banner displays when fallback is active:
`Showing last {effective_days} days because no rows were found in the requested {requested_days} day window.`

## Acceptance Criteria
- Home page config panel shows fallback banner when `7d` has no rows and `30d` fallback is used.
- Banner does not show when `7d` has data.
- API contracts documented for whichever endpoint is chosen.
- Browser validation on VM2 and VM1 confirms expected behavior and no regressions.

## Out of Scope
- Changing fallback policy logic itself.
- Reworking recommendation components or unrelated dashboard pages.

## References
- `services/rtb_bidstream_service.py`
- `dashboard/src/components/rtb/config-breakdown-panel.tsx`
- `docs/review/2026-02-16/VM2_ACCEPTANCE_B3.md`
