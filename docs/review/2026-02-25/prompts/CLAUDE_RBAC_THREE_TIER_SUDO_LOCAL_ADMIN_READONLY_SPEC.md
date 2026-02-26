# Claude Spec: RBAC Redesign for `sudo` / Seat `local-admin` / Seat `read-only`

```text
Design and implement a proper three-tier authorization model:

1. `sudo` (global super-admin / installer)
2. `local-admin` (seat-scoped admin for specific buyer seat(s))
3. `read-only` (seat-scoped read access for specific buyer seat(s))

This must be a real backend-enforced RBAC model, not just frontend hiding.

Context (confirmed by audit)
- Current system is effectively binary:
  - `users.role = 'admin'` => global god mode (all seats, all admin endpoints)
  - `users.role = 'user'` => seat-restricted via explicit buyer seat permissions or legacy service-account fallback
- `user_buyer_seat_permissions.access_level = 'admin'` exists in schema but is currently a no-op for authorization
- `dea` seeing all seats and admin nav is because `dea.role='admin'`, which bypasses seat filtering entirely
- Audit doc:
  - `docs/review/2026-02-25/audit/DEA_LOCAL_ADMIN_SCOPE_RCA.md`

User requirement (target behavior)
- `sudo`: full global access (all seats, all system/admin features)
- `local-admin` for seat(s): can manage seat-scoped settings and manage user access for those seat(s) only
- `read-only` for seat(s): can view seat data only, no mutations

Examples
- `cat-scan@rtb.cat` (or equivalent installer account) => `sudo`
- `dea` => `local-admin` for TUKY (`buyer_id=299038253`) only

Important design constraints
- Prefer reusing existing schema capabilities where possible (especially `user_buyer_seat_permissions.access_level`)
- Avoid broad role churn if not needed
- Must preserve backward compatibility/migration path for current users
- Backend enforcement first; frontend follows

Recommended architecture (use this unless you find a blocker)

Authorization model (effective permissions)
- Global role (`users.role`):
  - `admin` = `sudo`
  - `user` = non-sudo (seat-scoped permissions apply)
- Seat access (`user_buyer_seat_permissions.access_level`):
  - `read`
  - `admin`

Resulting effective user types
- `sudo` = `users.role='admin'`
- `local-admin` = `users.role='user'` + seat permission `access_level='admin'`
- `read-only` = `users.role='user'` + seat permission `access_level='read'`

This achieves the required 3 user types without a schema migration for a new role enum.
If you want to expose the label `sudo` in UI/API, map `role='admin'` -> display label `sudo`.

Implementation scope (full fix)
1. Backend authorization primitives (new dependencies/helpers)
2. Seat-scoped admin endpoint enforcement
3. Seat-user management APIs (local-admin can manage users for their seats only)
4. Frontend auth payload + UI gating for local-admin
5. Migration/operational rollout for existing users (including `dea`)
6. Tests + audit documentation

PHASE A — Backend RBAC primitives (core)

1) Add seat access-level aware permission helpers in `api/dependencies.py`
Add (or equivalent):
- `get_allowed_buyer_access_levels(...) -> Optional[dict[str, str]]`
  - returns `None` for sudo/global admin
  - returns map `{buyer_id: access_level}` for non-sudo users
- `require_buyer_access_level(buyer_id: str, min_access_level: "read"|"admin", ...)`
- `require_buyer_admin_access(buyer_id: str, ...)` (wrapper for `min_access_level="admin"`)
- `resolve_buyer_id(... )` can stay for read-level access, but add a seat-admin variant if needed

Rules:
- `sudo` bypasses all seat checks
- non-sudo must have explicit buyer seat permission to access a seat
- `access_level='admin'` implies read + admin for that seat
- `access_level='read'` implies read only

Important:
- Continue supporting current explicit-seat-first behavior in `get_allowed_buyer_ids(...)`
- Legacy service-account fallback may remain for read scope during migration, but document it and gate admin actions on explicit seat admin permissions

2) Auth service / repo helpers
Reuse existing APIs where possible:
- `AuthService.get_user_buyer_seat_permissions(...)`
- `AuthService.get_user_buyer_seat_ids(min_access_level=...)`

If missing, add:
- `get_user_buyer_seat_access_map(user_id)` returning `{buyer_id: access_level}`

PHASE B — Endpoint authorization tiering (backend)

Classify endpoints into:
1. `sudo`-only (global/system)
2. seat-`local-admin` (seat-scoped mutations/admin)
3. seat-`read-only` (seat-scoped reads)

Start with the highest-risk paths (must enforce correctly)

`sudo`-only (examples; verify and document exact list)
- global user management (`/admin/users*`) except seat-scoped delegations if split out
- service-account management / credentials
- global configuration
- global audit log
- system-wide sync operations (if they affect all seats)

seat-`local-admin` (examples)
- seat-scoped settings (endpoint QPS edits, pretargeting mutations, seat sync)
- seat-scoped import actions (manual imports, if mutation)
- seat-scoped user access management (new endpoints in Phase C)

seat-`read-only`
- analytics/home/rtb/qps reads (already mostly buyer-scoped)
- creatives/campaigns reads
- import history reads

Implementation requirement
- Do NOT rely on frontend checks
- Replace `require_admin` with `require_buyer_admin_access` on seat-scoped admin actions
- Keep `require_admin` (sudo-only) for global admin actions

PHASE C — Seat-local-admin user management (new backend APIs)
User requirement says local-admin can "add users to that seat only".

Design this as a separate seat-admin API surface (recommended) to avoid weakening global `/admin/*` routes.

Add new router (recommended):
- `api/routers/seat_admin.py` (or equivalent)

Capabilities for local-admin (and sudo)
1. List users with access to a managed seat
- `GET /seat-admin/seats/{buyer_id}/users`
2. Grant seat access (`read` or `admin`) for that seat
- `POST /seat-admin/seats/{buyer_id}/users/{user_id}/permission`
3. Revoke seat access for that seat
- `DELETE /seat-admin/seats/{buyer_id}/users/{user_id}/permission`
4. Optional: invite/create a basic user (`role='user'`) and immediately grant seat access
- If implemented now, must be constrained so local-admin cannot create `sudo` users

Security requirements
- Caller must be `sudo` or seat-local-admin for `buyer_id`
- Local-admin may only manage permissions for the specific seat(s) they admin
- Local-admin cannot:
  - change global roles
  - grant `sudo`
  - manage service-account permissions
  - revoke `sudo` access

Audit logging
- Log seat-admin grants/revokes distinctly (resource_type `buyer_seat_permission`)
- Include target seat and target user

PHASE D — Auth payload + frontend capability model

Current issue
- Frontend only knows `user.is_admin` (global) and service-account permission IDs
- It has no seat access-level map, so it cannot represent local-admin correctly

1) Extend `/api/auth/me` and `/api/auth/check` responses
Add fields (exact names OK if consistent), e.g.:
- `global_role`: `"sudo"` | `"user"`  (or map from existing `role`)
- `seat_permissions`: `{ buyer_id: "read" | "admin" }`
- `effective_capabilities` (optional) for convenience

Keep backward-compatible fields for now:
- `role`
- `is_admin`

2) Update frontend auth context (`dashboard/src/contexts/auth-context.tsx`)
- Store:
  - `globalRole`
  - `seatPermissions`
- Derive:
  - `isSudo`
  - `isSeatAdmin(buyerId)`

3) Sidebar/admin UI split
- Keep System Administration nav visible only for `sudo`
- Add Seat Administration UI section for local-admin when current seat access is `admin`
- Ensure seat dropdown still comes from `/seats` and is filtered server-side

4) User management UI
- Global admin (`sudo`) keeps existing `/admin/users` flows
- Add a seat-admin user management screen or panel using the new `/seat-admin/*` APIs
- Local-admin can manage only users/permissions for current seat(s)

PHASE E — Migration / rollout plan (important)

1. Immediate operational change for `dea` (documented, can be executed separately)
- Set `dea.role = 'user'`
- Keep explicit `user_buyer_seat_permissions` row:
  - `buyer_id=299038253`, `access_level='admin'`
- Ensure session refresh/login after role change

2. Backward compatibility
- Keep existing `users.role='admin'` semantics as `sudo`
- Do not break existing global admins
- Preserve read fallback from service-account permissions for non-sudo during transition (or add a feature flag to disable later)

3. Future hardening (optional, document)
- Disable legacy service-account fallback for UI seat scoping after all users are migrated to explicit seat permissions

PHASE F — Tests (required)

Backend tests (must add)
1. Permission primitives
- sudo bypass
- read-only seat access can read, cannot admin-mutate
- local-admin seat access can admin-mutate for owned seat
- local-admin denied on other seat

2. Endpoint auth
- sample seat-scoped admin mutation returns:
  - 200 for seat-local-admin on owned seat
  - 403 for read-only
  - 403 for local-admin on unowned seat

3. Seat-admin user-management APIs
- local-admin can grant/revoke read/admin on managed seat only
- cannot grant sudo/global role

Frontend validation (manual is OK if no tests)
- `dea` (local-admin on TUKY):
  - sees only TUKY in dropdown
  - does NOT see System Administration nav
  - sees seat-admin functions for TUKY (if implemented this pass)
- `sudo`:
  - retains all seats + System Administration
- read-only user:
  - seat visible
  - no seat-admin mutation UI

Deliverables
1. Code changes (backend + frontend)
2. Tests and/or validation evidence
3. Audit/implementation note:
   - `docs/review/2026-02-25/audit/RBAC_THREE_TIER_SUDO_LOCAL_ADMIN_READONLY_IMPLEMENTATION.md`
   Include:
   - old model vs new model
   - endpoint tiering decisions
   - migration notes
   - verification results

Commit strategy (recommended)
1. Backend permission primitives + endpoint enforcement
2. Seat-admin API router
3. Auth payload + frontend capability model / sidebar gating
4. Seat-admin UI
5. Tests + docs

Acceptance criteria (must pass)
- `users.role='admin'` acts as global `sudo`
- `users.role='user'` + seat permission `admin` acts as seat-local-admin (real backend enforcement)
- `users.role='user'` + seat permission `read` is read-only
- `dea` (configured as local-admin TUKY-only) cannot see or access non-TUKY seats
- Local-admin can manage user access for owned seat(s) only, not global admin/system config
```

