# RBAC Three-Role Implementation Plan (2026-02-28)

## Objective
Implement and enforce exactly three user types:
- `sudo`: global admin over all seats and system settings
- `admin`: admin only for explicitly assigned seats
- `read`: read-only only for explicitly assigned seats

## Problem Statement
Current production behavior lets some `admin` users see all seats even when only one seat is assigned. This happens because legacy `admin` is still treated as global/sudo in authorization and auth response mapping.

## Current State (Key Constraints)
- `users.role` is constrained to `('admin', 'user')` in `storage/postgres_migrations/030_auth_baseline_tables.sql`.
- Global bypass is currently tied to `role == "admin"` in:
  - `api/dependencies.py` (`require_admin`, `is_sudo`, `get_allowed_buyer_ids`, service-account checks)
  - `api/auth_oauth_proxy.py` (`global_role` and `is_admin` mapping)
- Seat permissions already exist and are usable in `user_buyer_seat_permissions` with `access_level in ('read','admin')` (`storage/postgres_migrations/049_user_buyer_seat_permissions.sql`).

## Target Authorization Model

### 1) Platform role (`users.role`)
- `sudo`: global system authority
- `admin`: non-global, seat-scoped
- `read`: non-global, seat-scoped

### 2) Seat scope (`user_buyer_seat_permissions`)
- `access_level = read`: seat view access
- `access_level = admin`: seat mutation/admin access

### 3) Effective permissions
- `sudo`: bypass seat checks and sees all buyers/bidders
- `admin`: only seats in explicit seat-permissions map; admin actions only where seat access is `admin`
- `read`: only seats in explicit seat-permissions map; no admin mutations

## Implementation Plan

### Phase A: Schema + migration safety
1. Add migration to extend role constraint to `('sudo','admin','read')`.
2. Backfill legacy roles:
   - legacy `admin` -> `sudo` (or explicit installer allowlist -> `sudo`, others -> `admin`, per rollout decision)
   - legacy `user` -> `read`
3. Keep migration idempotent and audited.

### Phase B: Backend authorization enforcement
1. Update role helpers in `api/dependencies.py`:
   - `is_sudo(user)` -> `user.role == "sudo"`
   - add helpers for `is_admin` and `is_read` if needed
2. Replace global checks:
   - `require_admin` behavior split into `require_sudo` (global-only routes)
   - keep seat-scoped checks on `require_buyer_admin_access` / `require_seat_admin_or_sudo`
3. Ensure seat/bidder resolution (`get_allowed_buyer_ids`, `resolve_buyer_id`, `resolve_bidder_id`) returns global access only for `sudo`.
4. Remove reliance on legacy service-account fallback for seat visibility once seat permissions are fully populated.

### Phase C: Auth/bootstrap/provider role mapping
1. First bootstrap-created user should be `sudo` (not `admin`).
2. First user auto-provision path (when allowed) should also map to `sudo`; subsequent users default to `read`.
3. `/auth/me` and `/auth/check` should expose role semantics without treating `is_admin` as sudo shorthand.

### Phase D: Endpoint policy hardening
1. Mark sudo-only endpoints (global admin and system settings):
   - `/admin/*`
   - `/config/*` global configuration
   - other global operations (for example manual import triggers)
2. Keep seat-scoped mutate routes as `sudo OR seat-admin`.
3. Keep read routes gated by buyer/bidder resolution and explicit seat permissions.

### Phase E: Frontend role model + UX
1. Update auth context so sudo derives from `global_role/role == sudo`, not `is_admin` fallback.
2. Update role picker and labels in Admin Users UI to `sudo/admin/read`.
3. Keep global admin nav only for sudo; show seat-scoped controls to seat-admin users where applicable.
4. Hide mutation actions for `read` users to avoid expected 403 loops.

### Phase F: Tests + rollout
1. Update/add unit and API tests for all three roles and seat-scope matrix.
2. Run staged rollout:
   - deploy migration + backend checks
   - invalidate/refresh sessions
   - deploy frontend role updates
3. Validate with three real accounts:
   - one `sudo`
   - one `admin` with one assigned seat
   - one `read` with one assigned seat

## Acceptance Criteria
- `sudo` sees all seats and can manage global settings/users.
- `admin` only sees assigned seats and can mutate only assigned `admin` seats.
- `read` only sees assigned seats and cannot perform admin mutations.
- No user with role `admin` (non-sudo) can list or access non-assigned seats.
- Auth endpoints and UI display the same role semantics as backend enforcement.
