# Analytics Router Auth & Scope Audit

**Date:** 2026-02-25
**Scope:** All 28 routes across 6 analytics router files

---

## Summary of Findings

| Issue | Count | Status |
|-------|-------|--------|
| Unauthenticated routes | 14 | Fixed |
| Missing billing_id ownership validation | 5 routes | Fixed |
| `except Exception` swallowing `HTTPException` status codes | 20 routes | Fixed |
| Silent error swallowing (spend endpoint returning fallback dict) | 1 route | Fixed |

---

## Route Inventory (28 routes)

### home.py (4 routes) -- Already correct, no changes

| Route | Auth | Scope | HTTPException passthrough |
|-------|------|-------|--------------------------|
| `GET /analytics/home/funnel` | `get_current_user` | `resolve_buyer_id` | Yes |
| `GET /analytics/home/configs` | `get_current_user` | `resolve_buyer_id` | Yes |
| `GET /analytics/home/endpoint-efficiency` | `get_current_user` | `resolve_buyer_id` | Yes |
| `POST /analytics/home/refresh` | `get_current_user` | admin check + `resolve_buyer_id` | N/A |

### traffic.py (2 routes) -- Already correct auth, passthrough added to 1

| Route | Auth | Scope | HTTPException passthrough |
|-------|------|-------|--------------------------|
| `POST /analytics/import-traffic` | `get_current_user` | `get_allowed_buyer_ids` | Already had |
| `POST /analytics/generate-mock-traffic` | `get_current_user` | `resolve_buyer_id` | **Added** |

### qps.py (10 routes) -- 7 auth fixes, 9 passthrough fixes, 1 ownership fix

| Route | Auth | Scope | HTTPException passthrough | Billing ownership |
|-------|------|-------|--------------------------|-------------------|
| `GET /analytics/size-coverage` | Already had | `resolve_buyer_id` (billing_id path forces ownership; no-billing_id path scopes via billing_ids) | Already had | **Added** |
| `GET /analytics/geo-waste` | Already had | `resolve_buyer_id` | **Added** | N/A |
| `GET /analytics/pretargeting-recommendations` | **Added** | auth-only | **Added** | N/A |
| `GET /analytics/qps-summary` | Already had | `resolve_buyer_id` | **Added** | N/A |
| `GET /analytics/geo-pretargeting-config` | **Added** | auth-only | **Added** | N/A |
| `GET /analytics/qps-optimization` | **Added** | `resolve_bidder_id` | **Added** | N/A |
| `GET /analytics/publisher-waste` | **Added** | `resolve_bidder_id` | **Added** | N/A |
| `GET /analytics/bid-filtering` | **Added** | `resolve_bidder_id` | **Added** | N/A |
| `GET /analytics/platform-efficiency` | **Added** | `resolve_bidder_id` | **Added** | N/A |
| `GET /analytics/hourly-patterns` | **Added** | `resolve_bidder_id` | **Added** | N/A |

### rtb_bidstream.py (8 routes) -- 4 auth fixes, 6 passthrough fixes, 3 ownership fixes

| Route | Auth | Scope | HTTPException passthrough | Billing ownership |
|-------|------|-------|--------------------------|-------------------|
| `GET /analytics/rtb-funnel` | Already had | `resolve_buyer_id` | **Added** | N/A |
| `GET /analytics/rtb-funnel/publishers` | **Added** | `resolve_buyer_id` | **Added** | N/A |
| `GET /analytics/rtb-funnel/geos` | **Added** | `resolve_buyer_id` | **Added** | N/A |
| `GET /analytics/rtb-funnel/configs` | Already had | `resolve_buyer_id` | **Added** | N/A |
| `GET /analytics/rtb-funnel/configs/{billing_id}/breakdown` | Already had | `resolve_buyer_id` | Already had | **Added** |
| `GET /analytics/rtb-funnel/configs/{billing_id}/creatives` | Already had | `resolve_buyer_id` | Already had | **Added** |
| `GET /analytics/rtb-funnel/creatives` | **Added** | `resolve_buyer_id` | **Added** | N/A |
| `GET /analytics/app-drilldown` | **Added** | `resolve_buyer_id` + billing ownership when `billing_id` provided | **Added** | **Added** |

### spend.py (1 route) -- auth fix, passthrough fix, ownership fix

| Route | Auth | Scope | HTTPException passthrough | Billing ownership |
|-------|------|-------|--------------------------|-------------------|
| `GET /analytics/spend-stats` | **Added** | `resolve_buyer_id` + billing ownership when `billing_id` provided | **Added** (was silently swallowing) | **Added** |

### waste.py (7 routes) -- 2 auth fixes, 3 passthrough fixes

| Route | Auth | Scope | HTTPException passthrough | Billing ownership |
|-------|------|-------|--------------------------|-------------------|
| `GET /analytics/waste` | Already had | `resolve_buyer_id` | **Added** | N/A |
| `GET /analytics/waste-signals/{creative_id}` | Already had | `require_buyer_access` | N/A (no try/except) | N/A |
| `GET /analytics/problem-formats` | Already had | `resolve_buyer_id` | N/A (no try/except) | N/A |
| `POST /analytics/waste-signals/analyze` | **Added** | `require_admin` | N/A (no try/except) | N/A |
| `POST /analytics/waste-signals/{signal_id}/resolve` | **Added** | `require_admin` | N/A (no try/except) | N/A |
| `GET /analytics/viewability-waste` | Already had | `resolve_bidder_id` | **Added** | N/A |
| `GET /analytics/fraud-risk` | Already had | `resolve_bidder_id` | **Added** | N/A |

---

## Billing Ownership Validation

New helper `validate_billing_id_ownership()` in `api/routers/analytics/common.py`:
- Uses **direct repo calls** (`AnalyticsRepository.get_bidder_id_for_buyer()` and `.get_billing_ids_for_bidder()`) that propagate DB errors as 500s
- Does NOT use `get_valid_billing_ids_for_buyer()` which swallows all exceptions and returns `[]`
- Returns 404 (not 403) to avoid leaking config existence to non-owners
- Only validates when both `billing_id` and `buyer_id` are provided; skips when `buyer_id` is None (admin with no filter)

Applied to 5 routes:
1. `GET /analytics/size-coverage` (query param `billing_id`)
2. `GET /analytics/rtb-funnel/configs/{billing_id}/breakdown` (path param)
3. `GET /analytics/rtb-funnel/configs/{billing_id}/creatives` (path param)
4. `GET /analytics/app-drilldown` (query param `billing_id`)
5. `GET /analytics/spend-stats` (query param `billing_id`)

---

## Residual Scope Gaps (Status)

Follow-up hardening added query-level buyer scope to `publishers`, `geos`,
`app-drilldown`, `spend-stats`, and `rtb-funnel/creatives` (creative-win route now uses a
buyer-scoped DB/precompute path instead of the legacy CSV analyzer).

No remaining route-level analytics scope gaps are tracked in this audit note. Future work is
focused on broader data correctness programs (seat identity persistence, fresh-only serving).

---

## Files Modified

| File | Changes |
|------|---------|
| `api/routers/analytics/qps.py` | Auth deps on 7 routes, HTTPException passthrough on 9, billing ownership on 1 |
| `api/routers/analytics/rtb_bidstream.py` | Auth on 4 routes, passthrough on 6, billing ownership on 3 |
| `api/routers/analytics/spend.py` | Auth + buyer_id param, fix exception swallowing, billing ownership |
| `api/routers/analytics/waste.py` | Admin-only on 2 POST routes, passthrough on 3 |
| `api/routers/analytics/common.py` | Added `validate_billing_id_ownership()` using direct repo calls |
| `api/routers/analytics/traffic.py` | HTTPException passthrough on 1 route |
| `services/rtb_bidstream_service.py` | Buyer-scoped publishers/geos/app-drilldown queries and bid-filtering |
| `services/analytics_service.py` | Buyer-scoped spend-stats query path and precompute status filters |
| `storage/postgres_repositories/rtb_bidstream_repo.py` | Added `buyer_account_id` filters to app drilldown and bid-filtering queries |
| `storage/postgres_repositories/analytics_repo.py` | Added buyer-scoped spend stats queries (`buyer_account_id`) |
