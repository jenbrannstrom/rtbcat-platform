# Chapter 16: User and Permission Administration

*Audience: DevOps, system administrators*

## Admin panel (`/admin`)

The admin panel is only visible to users with the `is_sudo` flag. It provides
user management, system configuration, and audit logging.

## User management (`/admin/users`)

### Creating users

Two methods:

| Method | When to use |
|--------|-------------|
| **Local account** | For users who will log in with email and password. You set the initial password. |
| **OAuth pre-create** | For users who will log in with Google OAuth. Pre-creating the record lets you assign permissions before their first login. |

Fields: email (required), display name, role, auth method, password (local
only).

### Roles and permissions

**Global permissions** control what a user can do system-wide:
- Standard user: access to main features
- Restricted user: limited sidebar (no settings, admin, or QPS sections)
- Admin (`is_sudo`): full access including admin panel

**Per-seat permissions** control which buyer accounts a user can see:
- Grant access to specific `buyer_account_id` values
- Access levels can vary per seat
- A user with no seat permissions sees no data

### Managing permissions

1. Go to `/admin/users`
2. Select a user
3. Under "Seat Permissions": grant or revoke access to buyer seats
4. Under "Global Permissions": grant or revoke system-level access
5. Changes take effect on the user's next page load

### Deactivating users

Deactivating a user preserves their record (for audit trail) but prevents
login. It does not delete their data or permissions; they can be reactivated.

## Service accounts (`/settings/accounts`)

Service accounts represent GCP credentials that enable Cat-Scan to
communicate with Google APIs.

### Uploading credentials

1. Go to `/settings/accounts` > API Connection tab
2. Upload the GCP service account JSON key file
3. Cat-Scan validates the credentials and shows connection status

**Security note:** Only add the service account JSON key at the end of setup
to minimize exposure risk.

### What service accounts unlock

- **Seat discovery**: find buyer accounts associated with the credentials
- **Pretargeting sync**: pull current config state from Google
- **RTB endpoint sync**: discover bidder endpoints
- **Creative collection**: gather creative metadata

## Audit log (`/admin/audit-log`)

Every significant action is logged:

| Action | What triggers it |
|--------|-----------------|
| `login` | Successful authentication |
| `login_failed` | Failed authentication attempt |
| `login_blocked` | Login rejected (deactivated user, etc.) |
| `create_user` | New user created |
| `update_user` | User profile modified |
| `deactivate_user` | User deactivated |
| `reset_password` | Password reset |
| `change_password` | Password changed |
| `grant_permission` | Permission granted |
| `revoke_permission` | Permission revoked |
| `update_setting` | System setting changed |
| `create_initial_admin` | First admin created during setup |

Filters: by user, action type, resource type, time window (days), with
pagination.

## System configuration (`/admin/configuration`)

Global key-value settings that control system behavior. Editable by admins.
Changes are recorded in the audit log.

## Related

- [Logging In](01-logging-in.md): user-facing auth experience
- [Architecture Overview](11-architecture.md): auth trust chain details
