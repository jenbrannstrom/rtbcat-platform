# Home Identifier Integrity Audit (2026-02-25)

## Scope

Roadmap Phase 1 item:

- "Identifier integrity — Never substitute `seat_id/buyer_id` for `billing_id`. Billing IDs scope pretargeting configs; seat IDs scope buyer seats. Keep them distinct in queries and APIs."

This audit focuses on Home/RTB analytics config-related paths where both identifiers can appear in the same request flow.

## What Was Reviewed

### API routes (analytics)

- `api/routers/analytics/rtb_bidstream.py`
  - `GET /analytics/rtb-funnel/configs/{billing_id}/breakdown`
  - `GET /analytics/rtb-funnel/configs/{billing_id}/creatives`
- `api/routers/analytics/qps.py`
  - `GET /analytics/size-coverage` (accepts optional `billing_id` and `buyer_id`)
- Shared helper module:
  - `api/routers/analytics/common.py`

### Service / repo propagation

- `services/rtb_bidstream_service.py`
- `storage/postgres_repositories/rtb_bidstream_repo.py`
- `services/home_analytics_service.py`
- `storage/postgres_repositories/home_repo.py`

### Frontend call sites (config breakdown UI)

- `dashboard/src/components/rtb/config-breakdown-panel.tsx`
- `dashboard/src/lib/api/analytics.ts`

## Findings

### 1. Parameter separation is already correct in audited paths

- `billing_id` remains a distinct path/query parameter for config-scoped routes.
- `buyer_id` is resolved independently via `resolve_buyer_id(...)` and passed as a separate seat filter.
- Frontend config breakdown panel passes `billing_id` and `selectedBuyerId` as separate arguments to API helpers (no substitution observed).

No direct `buyer_id -> billing_id` assignment/substitution was found in the audited Home/RTB analytics paths.

### 2. Missing API-boundary guard for obvious identifier mixups (fixed)

Before the fix, routes accepted both identifiers but did not reject obvious misuse such as passing the same string value for `billing_id` and `buyer_id`.

This could produce confusing "no data" responses instead of a clear client error when the caller accidentally used a seat ID in the `billing_id` slot.

## Hardening Applied

### Shared guard

Added `validate_identifier_integrity(...)` in:

- `api/routers/analytics/common.py`

Behavior:

- Normalizes/strips both IDs
- Raises `HTTP 400` if `buyer_id == billing_id`
- Error message explicitly states that the identifiers are different namespaces/types

### Route enforcement

Wired guard into routes that accept both identifiers:

- `GET /analytics/rtb-funnel/configs/{billing_id}/breakdown`
- `GET /analytics/rtb-funnel/configs/{billing_id}/creatives`
- `GET /analytics/size-coverage`

Also updated these handlers to preserve `HTTPException` status codes (so the new `400` does not get converted into a generic `500`).

## Outcome

- Identifier integrity is now enforced at the API boundary for the primary Home/RTB analytics config routes.
- Audited paths keep seat IDs and billing IDs distinct across frontend -> router -> service -> repository layers.

## Limits / Follow-up

- The guard catches obvious equality-based mixups (`buyer_id == billing_id`) but cannot prove semantic correctness for arbitrary strings.
- Broader format/schema validation for `billing_id` values (if a stable pattern is defined) can be added later as a stronger integrity check.
