# Home Seat-Scope Verification Audit (2026-02-25)

## Scope

Roadmap Phase 0 item:

- "Seat scope verification — Confirm all Home endpoints enforce `buyer_id` and user permissions"

This audit covers:

- Home analytics API routes under `api/routers/analytics/home.py`
- Buyer access resolution in `api/dependencies.py`
- Buyer propagation through `services/home_analytics_service.py` and `storage/postgres_repositories/home_repo.py`
- Frontend callers on the Home and QPS pages

## Endpoints Reviewed

Routes in `api/routers/analytics/home.py`:

- `GET /analytics/home/funnel`
- `GET /analytics/home/configs`
- `GET /analytics/home/endpoint-efficiency`
- `POST /analytics/home/refresh` (admin refresh path; not user-facing data read)

## Findings

### 1. User authentication and access control are present

- All Home analytics routes depend on `get_current_user`.
- Home GET routes call `resolve_buyer_id(...)`.
- `resolve_buyer_id()` enforces:
  - non-admins must use an allowed `buyer_id`
  - non-admins with multiple seats must provide `buyer_id`
  - forbidden seat access returns `403`

Files:

- `api/routers/analytics/home.py`
- `api/dependencies.py`

### 2. Buyer scope propagates into service/repo SQL paths

- `HomeAnalyticsService` methods accept `buyer_id` and pass it into repo calls.
- `HomeAnalyticsRepository` methods apply `buyer_id` filters to `seat_*`, `pretarg_*`, and `rtb_bidstream` reads.
- Endpoint-efficiency path maps `buyer_id -> bidder_id` and then filters endpoint reads by bidder.

Files:

- `services/home_analytics_service.py`
- `storage/postgres_repositories/home_repo.py`

### 3. Frontend Home/QPS callers pass selected seat IDs

- Home page (`dashboard/src/app/page.tsx`) issues Home analytics queries only when `seatReady = !!selectedBuyerId`.
- API calls pass `selectedBuyerId` to Home funnel/configs/endpoint-efficiency.
- QPS pages also call Home funnel helper with selected buyer IDs.

Files:

- `dashboard/src/app/page.tsx`
- `dashboard/src/app/qps/publisher/page.tsx`
- `dashboard/src/app/qps/geo/page.tsx`
- `dashboard/src/lib/api/analytics.ts`

## Gaps Found (and Fixed)

### A. Admin callers could omit `buyer_id` on Home GET endpoints

Before the fix, `resolve_buyer_id()` returns `None` for admins when `buyer_id` is omitted, which allowed all-seat aggregation on Home GET endpoints.

Fix applied (2026-02-25):

- Home GET endpoints now require an explicit resolved `buyer_id` (`_require_home_buyer_id(...)`)
- This keeps user-facing Home analytics seat-scoped for all roles

File:

- `api/routers/analytics/home.py`

### B. Route handlers converted access/validation errors into `500`

Before the fix, Home GET handlers used `except Exception` and could catch `HTTPException` raised by `resolve_buyer_id(...)`, returning a generic `500` instead of the intended `400/403`.

Fix applied (2026-02-25):

- Added `except HTTPException: raise` before generic exception handlers in Home GET routes

File:

- `api/routers/analytics/home.py`

## Outcome

Seat-scope verification is complete for Home analytics routes and primary frontend callers.

Notes:

- `POST /analytics/home/refresh` remains admin-capable and may still operate across all seats when `buyer_id` is omitted. This is acceptable as an admin refresh/control endpoint, not a user-facing analytics read.
- The separate roadmap item "Data source audit" (missing `bidder_id`/`billing_id` percentages) is still open.
