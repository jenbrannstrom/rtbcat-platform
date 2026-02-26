# RBAC Three-Tier Implementation Audit

**Date:** 2026-02-25
**Author:** Claude (AI Dev)
**Status:** Implemented

## Old Model (Binary)

| Role | Behavior |
|------|----------|
| `users.role = 'admin'` | Global god mode: all seats, all admin endpoints, all settings |
| `users.role = 'user'` | Seat-restricted via explicit buyer seat permissions or legacy service-account fallback |

- `user_buyer_seat_permissions.access_level` existed but was a **no-op** for authorization decisions
- `dea` had `role='admin'`, which gave full access to all seats + system admin

## New Model (Three-Tier)

| Effective Type | DB Representation | Behavior |
|---|---|---|
| **sudo** | `users.role = 'admin'` | Full global access (all seats, all admin features, all settings) |
| **local-admin** | `users.role = 'user'` + seat permission `access_level='admin'` | Admin for assigned seats only: settings mutations, seat user management |
| **read-only** | `users.role = 'user'` + seat permission `access_level='read'` | View-only for assigned seats |

No schema migration was needed - reuses existing `users.role` + `user_buyer_seat_permissions.access_level` fields.

## Endpoint Tiering

### sudo-only (`require_admin`)
- Global user management: `/admin/users*`
- Service-account management: `/admin/users/{user_id}/permissions`
- Buyer seat permission management (global): `/admin/users/{user_id}/seat-permissions`
- Global configuration: `/admin/configuration`
- Audit log: `/admin/audit-log`

### seat-local-admin (`require_seat_admin_or_sudo`)
- RTB settings mutations: `/settings/endpoints/`, `/settings/pretargeting/`
- All settings sub-routers (endpoints, pretargeting, snapshots, changes, actions)

### seat-local-admin per-seat (`require_buyer_admin_access`)
- Seat user management: `/seat-admin/seats/{buyer_id}/users`
- Grant/revoke seat access: `/seat-admin/seats/{buyer_id}/users/{user_id}/permission`

### seat-read-only (existing `get_allowed_buyer_ids` filtering)
- Analytics, QPS, home reads
- Creatives, campaigns reads
- Import history reads

## New Backend Primitives (`api/dependencies.py`)

| Function | Purpose |
|---|---|
| `is_sudo(user)` | Check if user is global admin |
| `get_user_buyer_access_map(user)` | Returns `None` for sudo, `{buyer_id: level}` for others |
| `require_buyer_access_level(buyer_id, min_level, user)` | Enforce per-seat access level |
| `require_buyer_admin_access(buyer_id, user)` | Shorthand for admin-level seat access |
| `require_seat_admin_or_sudo(user)` | Require sudo or admin access to any seat |

## New API Surface (`/seat-admin/`)

| Endpoint | Method | Description |
|---|---|---|
| `/seat-admin/seats/{buyer_id}/users` | GET | List users with access to a seat |
| `/seat-admin/seats/{buyer_id}/users/{user_id}/permission` | POST | Grant/update seat access |
| `/seat-admin/seats/{buyer_id}/users/{user_id}/permission` | DELETE | Revoke seat access |

Security constraints:
- Caller must be sudo or local-admin for the target buyer_id
- Local-admin cannot revoke sudo user's seat access
- Local-admin cannot modify global roles

## Auth Payload Changes

### `/api/auth/me` response (new fields)
- `global_role`: `"sudo"` or `"user"` (mapped from `users.role`)
- `seat_permissions`: `{buyer_id: "read" | "admin"}` (empty for sudo)

### `/api/auth/check` response (new field)
- `user.global_role`: `"sudo"` or `"user"`

### Frontend Auth Context (new exports)
- `isSudo`: boolean (replaces `isAdmin` for admin nav gating)
- `seatPermissions`: `Record<string, string>`
- `isSeatAdmin(buyerId)`: helper function

## Frontend Changes

- **Sidebar:** System Administration section gated by `isSudo` (was `isAdmin`)
- **withAdminAuth HOC:** Now checks `isSudo` instead of `isAdmin`
- **Auth context:** Stores `seatPermissions` from `/auth/me` response

## Migration Notes for `dea`

To convert `dea` from global admin to TUKY-only local-admin:

```sql
-- Step 1: Demote from global admin
UPDATE users SET role = 'user', updated_at = NOW()
WHERE email = 'dea@rtb.cat';

-- Step 2: Ensure explicit seat admin permission exists
INSERT INTO user_buyer_seat_permissions (id, user_id, buyer_id, access_level, granted_by, granted_at)
SELECT gen_random_uuid()::text, u.id, '299038253', 'admin', 'migration', NOW()
FROM users u WHERE u.email = 'dea@rtb.cat'
ON CONFLICT (user_id, buyer_id) DO UPDATE SET access_level = 'admin';
```

**Important:** After running migration, user must re-login (session refresh) for frontend to pick up new role.

## Backward Compatibility

- `users.role='admin'` continues to work as sudo (no existing admins broken)
- Legacy `is_admin` field preserved in API responses
- Legacy `permissions` (service account IDs) still returned
- Service-account fallback for read scope preserved during transition
- New fields (`global_role`, `seat_permissions`) are additive

## Verification Checklist

- [ ] `cat-scan@rtb.cat` (sudo): sees all seats, System Administration nav, full access
- [ ] `dea` (after migration, local-admin TUKY): sees only TUKY, no System Administration nav, can manage TUKY settings
- [ ] Read-only user: sees assigned seat(s), no mutation UI, 403 on settings mutations
- [ ] Local-admin cannot access `/admin/*` endpoints (403)
- [ ] Local-admin can access `/seat-admin/seats/{buyer_id}/users` for their seat
- [ ] Local-admin cannot revoke sudo user access (403)
